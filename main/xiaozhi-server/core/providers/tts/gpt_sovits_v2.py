# 导入操作系统相关功能模块，用于文件路径操作等
import os
# 导入uuid模块，用于生成通用唯一识别码，保证文件名的唯一性
import uuid
# 导入json模块，用于处理JSON数据，在构建请求和解析响应时会用到
import json
# 导入base64模块，可用于处理Base64编码的数据，不过此代码中未实际使用
import base64
# 导入requests模块，用于发送HTTP请求，实现与TTS服务的通信
import requests
# 从自定义配置模块中导入设置日志的函数，用于记录程序运行信息
from config.logger import setup_logging
# 从datetime模块导入日期时间类，用于生成包含当前日期的文件名
from datetime import datetime
# 从自定义模块中导入TTS提供者的基类，当前类继承自该基类
from core.providers.tts.base import TTSProviderBase

# 获取当前模块的名称作为标签，方便在日志中标识
TAG = __name__
# 调用设置日志的函数并获取日志记录器，用于后续记录日志
logger = setup_logging()

class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于实现文本转语音（TTS）功能。

        :param config: 一个包含TTS服务配置信息的字典，包含以下可能的键值对：
            - url: TTS服务的请求URL，用于发送转换请求。
            - text_lang: 输入文本的语言，默认为中文（"zh"）。
            - ref_audio_path: 参考音频的路径，用于指定语音风格等。
            - prompt_text: 提示文本，可能用于引导语音生成。
            - prompt_lang: 提示文本的语言，默认为中文（"zh"）。
            - top_k: 采样时考虑的前k个候选，用于控制语音生成的随机性，默认为5。
            - top_p: 采样时考虑的累积概率阈值，用于控制语音生成的随机性，默认为1。
            - temperature: 采样时的温度参数，用于控制语音生成的随机性，默认为1。
            - text_split_method: 文本分割方法，默认为"cut0"。
            - batch_size: 批量处理的大小，默认为1。
            - batch_threshold: 批量处理的阈值，默认为0.75。
            - split_bucket: 是否使用分割桶，默认为True。
            - return_fragment: 是否返回片段，默认为False。
            - speed_factor: 语音速度因子，默认为1.0。
            - streaming_mode: 是否使用流式模式，默认为False。
            - seed: 随机数种子，默认为 -1。
            - parallel_infer: 是否并行推理，默认为True。
            - repetition_penalty: 重复惩罚因子，默认为1.35。
            - aux_ref_audio_paths: 辅助参考音频路径列表，默认为空列表。
        :param delete_audio_file: 一个布尔值，指示是否在完成TTS任务后删除生成的音频文件。
        """
        # 调用父类的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取TTS服务的请求URL
        self.url = config.get("url")
        # 从配置字典中获取输入文本的语言，若未提供则默认为中文
        self.text_lang = config.get("text_lang", "zh")
        # 从配置字典中获取参考音频的路径
        self.ref_audio_path = config.get("ref_audio_path")
        # 从配置字典中获取提示文本
        self.prompt_text = config.get("prompt_text")
        # 从配置字典中获取提示文本的语言，若未提供则默认为中文
        self.prompt_lang = config.get("prompt_lang", "zh")
        # 从配置字典中获取采样时考虑的前k个候选，若未提供则默认为5
        self.top_k = config.get("top_k", 5)
        # 从配置字典中获取采样时考虑的累积概率阈值，若未提供则默认为1
        self.top_p = config.get("top_p", 1)
        # 从配置字典中获取采样时的温度参数，若未提供则默认为1
        self.temperature = config.get("temperature", 1)
        # 从配置字典中获取文本分割方法，若未提供则默认为"cut0"
        self.text_split_method = config.get("text_split_method", "cut0")
        # 从配置字典中获取批量处理的大小，若未提供则默认为1
        self.batch_size = config.get("batch_size", 1)
        # 从配置字典中获取批量处理的阈值，若未提供则默认为0.75
        self.batch_threshold = config.get("batch_threshold", 0.75)
        # 从配置字典中获取是否使用分割桶，若未提供则默认为True
        self.split_bucket = config.get("split_bucket", True)
        # 从配置字典中获取是否返回片段，若未提供则默认为False
        self.return_fragment = config.get("return_fragment", False)
        # 从配置字典中获取语音速度因子，若未提供则默认为1.0
        self.speed_factor = config.get("speed_factor", 1.0)
        # 从配置字典中获取是否使用流式模式，若未提供则默认为False
        self.streaming_mode = config.get("streaming_mode", False)
        # 从配置字典中获取随机数种子，若未提供则默认为 -1
        self.seed = config.get("seed", -1)
        # 从配置字典中获取是否并行推理，若未提供则默认为True
        self.parallel_infer = config.get("parallel_infer", True)
        # 从配置字典中获取重复惩罚因子，若未提供则默认为1.35
        self.repetition_penalty = config.get("repetition_penalty", 1.35)
        # 从配置字典中获取辅助参考音频路径列表，若未提供则默认为空列表
        self.aux_ref_audio_paths = config.get("aux_ref_audio_paths", [])

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
        # 构建请求的JSON数据，包含输入文本以及之前初始化时获取的各项配置信息
        request_json = {
            "text": text,
            "text_lang": self.text_lang,
            "ref_audio_path": self.ref_audio_path,
            "aux_ref_audio_paths": self.aux_ref_audio_paths,
            "prompt_text": self.prompt_text,
            "prompt_lang": self.prompt_lang,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "text_split_method": self.text_split_method,
            "batch_size": self.batch_size,
            "batch_threshold": self.batch_threshold,
            "split_bucket": self.split_bucket,
            "return_fragment": self.return_fragment,
            "speed_factor": self.speed_factor,
            "streaming_mode": self.streaming_mode,
            "seed": self.seed,
            "parallel_infer": self.parallel_infer,
            "repetition_penalty": self.repetition_penalty
        }

        # 向TTS服务的URL发送POST请求，携带构建好的JSON数据
        resp = requests.post(self.url, json=request_json)
        # 检查响应的状态码是否为200，表示请求成功
        if resp.status_code == 200:
            # 若请求成功，以二进制写入模式打开指定的输出文件
            with open(output_file, "wb") as file:
                # 将响应的内容（即生成的音频数据）写入文件
                file.write(resp.content)
        else:
            # 若请求失败，使用日志记录器记录错误信息，包括状态码和响应文本
            logger.bind(tag=TAG).error(f"GPT_SoVITS_V2 TTS请求失败: {resp.status_code} - {resp.text}")