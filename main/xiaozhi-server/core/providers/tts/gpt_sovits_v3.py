# 导入操作系统相关模块，用于处理文件路径和操作系统相关功能
import os
# 导入uuid模块，用于生成通用唯一识别码，确保文件名的唯一性
import uuid
# 导入requests模块，用于发送HTTP请求，与TTS服务进行通信
import requests
# 从配置文件中导入日志设置函数，用于配置日志记录
from config.logger import setup_logging
# 从datetime模块导入日期时间类，用于生成包含当前日期的文件名
from datetime import datetime
# 从自定义模块中导入TTS提供者的基类，当前类继承自该基类
from core.providers.tts.base import TTSProviderBase

# 获取当前模块的名称作为标签，用于日志记录时标识来源
TAG = __name__
# 调用日志设置函数，获取日志记录器
logger = setup_logging()

class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于实现文本转语音（TTS）功能。

        :param config: 包含TTS服务配置信息的字典，包含以下可能的配置项：
            - url: TTS服务的请求URL，用于向TTS服务发送请求以获取语音数据。
            - text_lang: 输入文本的语言，默认为"audo"（可能是拼写错误，推测为"auto"），该参数可帮助TTS服务识别输入文本的语言类型。
            - ref_audio_path: 参考音频的路径，用于指定语音风格等，TTS服务可根据该参考音频的特征来生成具有相似风格的语音。
            - prompt_lang: 提示文本的语言，用于明确提示文本的语言种类，辅助TTS服务理解提示信息。
            - prompt_text: 提示文本，用于引导语音生成，例如可以指定语音的情感、语气等特征。
            - top_k: 采样时考虑的前k个候选，默认为5。在TTS服务生成语音的采样过程中，该参数控制每次采样时考虑的候选数量。
            - top_p: 采样时考虑的累积概率阈值，默认为1。该参数用于控制采样时考虑的候选范围，通过累积概率来筛选候选。
            - temperature: 采样时的温度参数，默认为1。温度参数影响采样的随机性，值越大，采样越随机；值越小，采样越倾向于概率高的候选。
            - sample_steps: 采样步骤数，默认为16。该参数决定了TTS服务在生成语音时的采样步数。
            - media_type: 生成音频的媒体类型，默认为"wav"，指定了生成的语音文件的格式。
            - streaming_mode: 是否使用流式模式，默认为False。流式模式可使TTS服务在生成语音的过程中逐步返回数据，而不是一次性返回。
            - threshold: 阈值，具体用途取决于TTS服务的实现，默认为30。该阈值可能用于控制某些语音生成的条件或判断。
        :param delete_audio_file: 布尔值，指示是否在完成TTS任务后删除生成的音频文件。若为True，则在任务完成后删除文件；若为False，则保留文件。
        """
        # 调用父类的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取TTS服务的请求URL
        self.url = config.get("url")
        # 从配置字典中获取参考音频的路径
        self.refer_wav_path = config.get("refer_wav_path")
        # 从配置字典中获取提示文本
        self.prompt_text = config.get("prompt_text")
        # 从配置字典中获取提示文本的语言
        self.prompt_language = config.get("prompt_language")
        # 从配置字典中获取输入文本的语言，若未提供则使用默认值"audo"
        self.text_language = config.get("text_language", "audo")
        # 从配置字典中获取采样时考虑的前k个候选，若未提供则使用默认值15
        self.top_k = config.get("top_k", 15)
        # 从配置字典中获取采样时的累积概率阈值，若未提供则使用默认值1.0
        self.top_p = config.get("top_p", 1.0)
        # 从配置字典中获取是否裁剪标点符号的配置，若未提供则使用空字符串
        self.cut_punc = config.get("cut_punc","")
        # 从配置字典中获取语音生成的速度，若未提供则使用默认值1.0
        self.speed = config.get("speed", 1.0)
        # 从配置字典中获取采样步骤数，若未提供则使用默认值1.0
        self.sample_steps = config.get("sample_steps", 1.0)
        # 从配置字典中获取输入参考信息列表，若未提供则使用空列表
        self.inp_refs = config.get("inp_refs",[])
        # 这里重复获取了"inp_refs"，推测应该是获取其他参数，可能是代码有误
        self.sample_steps = config.get("inp_refs",32)
        # 从配置字典中获取是否进行超分辨率处理的标志，若未提供则使用默认值False
        self.if_sr = config.get("if_sr",False)

    def generate_filename(self, extension=".wav"):
        """
        生成一个唯一的文件名，用于保存TTS生成的音频文件。

        :param extension: 音频文件的扩展名，默认为".wav"。
        :return: 包含完整路径和文件名的字符串，文件名由固定前缀、当前日期、唯一的UUID和文件扩展名组成。
        """
        # 使用os.path.join函数将输出文件路径、固定前缀、当前日期、唯一的UUID和文件扩展名组合成完整的文件名
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将输入的文本转换为语音，并将生成的音频保存到指定的文件中。

        :param text: 要转换为语音的文本内容。
        :param output_file: 保存生成音频文件的完整路径。
        """
        # 构建请求参数的字典，包含输入文本和之前初始化时获取的各项配置信息
        # 创建一个字典，用于存储向 TTS 服务发送请求时所需的参数
        request_params = {
            # 参考音频的路径，用于指定语音风格等，TTS 服务可根据该参考音频的特征来生成具有相似风格的语音
            "refer_wav_path": self.refer_wav_path,
            # 提示文本，用于引导语音生成，例如可以指定语音的情感、语气等特征
            "prompt_text": self.prompt_text,
            # 提示文本的语言，用于明确提示文本的语言种类，辅助 TTS 服务理解提示信息
            "prompt_language": self.prompt_language,
            # 待转换为语音的文本内容
            "text": text,
            #   输入文本的语言，可帮助 TTS 服务识别输入文本的语言类型
            "text_language": self.text_language,
            # 采样时考虑的前 k 个候选，在 TTS 服务生成语音的采样过程中，控制每次采样时考虑的候选数量
            "top_k": self.top_k,
            # 采样时考虑的累积概率阈值，用于控制采样时考虑的候选范围，通过累积概率来筛选候选
            "top_p": self.top_p,
            # 采样时的温度参数，影响采样的随机性，值越大，采样越随机；值越小，采样越倾向于概率高的候选
            "temperature": self.temperature,
            # 是否裁剪标点符号的配置
            "cut_punc": self.cut_punc,
            # 语音生成的速度
            "speed": self.speed,
            # 输入参考信息列表，可能包含一些额外的参考数据用于语音生成
            "inp_refs": self.inp_refs,
            # 采样步骤数，决定了 TTS 服务在生成语音时的采样步数
            "sample_steps": self.sample_steps,
            # 是否进行超分辨率处理的标志，若为 True 则进行超分辨率处理，否则不进行
            "if_sr": self.if_sr,
        }

        # 向TTS服务的URL发送GET请求，携带构建好的请求参数
        resp = requests.get(self.url, params=request_params)
        # 检查响应的状态码是否为200，表示请求成功
        if resp.status_code == 200:
            # 若请求成功，以二进制写入模式打开指定的输出文件
            with open(output_file, "wb") as file:
                # 将响应的内容（即生成的音频数据）写入文件
                file.write(resp.content)
        else:
            # 若请求失败，使用日志记录器记录错误信息，包括状态码和响应文本
            logger.bind(tag=TAG).error(f"GPT_SoVITS_V3 TTS请求失败: {resp.status_code} - {resp.text}")