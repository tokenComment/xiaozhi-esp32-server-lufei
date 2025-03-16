# 导入操作系统相关模块，用于处理文件路径和操作系统相关功能
import os
# 导入uuid模块，用于生成通用唯一识别码，确保生成的文件名具有唯一性
import uuid
# 导入json模块，用于处理JSON数据，在构建请求和解析响应时会用到
import json
# 导入requests模块，用于发送HTTP请求，与TTS服务的API进行通信
import requests
# 从datetime模块导入日期时间类，用于生成包含当前日期的文件名
from datetime import datetime
# 从自定义模块中导入TTS提供者的基类，当前类继承自该基类
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于实现文本转语音（TTS）功能。

        :param config: 包含TTS服务配置信息的字典，包含以下可能的配置项：
            - group_id: 分组ID，用于标识API请求所属的分组。
            - api_key: 用于访问API的密钥，用于身份验证。
            - model: 要使用的TTS模型名称。
            - voice_id: 语音ID，指定语音的类型。
            - voice_setting: 语音设置，如语速、音量、音调、情感等。
            - pronunciation_dict: 发音字典，用于自定义某些词汇的发音。
            - audio_setting: 音频设置，如采样率、比特率、音频格式、声道数等。
            - timber_weights: 音色权重列表，用于调整音色。
        :param delete_audio_file: 布尔值，指示是否在完成TTS任务后删除生成的音频文件。
        """
        # 调用父类的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取分组ID
        self.group_id = config.get("group_id")
        # 从配置字典中获取API密钥
        self.api_key = config.get("api_key")
        # 从配置字典中获取要使用的TTS模型名称
        self.model = config.get("model")
        # 从配置字典中获取语音ID
        self.voice_id = config.get("voice_id")

        # 定义默认的语音设置
        default_voice_setting = {
            "voice_id": "female-shaonv",  # 默认语音ID为女性少女音
            "speed": 1,  # 语速为1
            "vol": 1,  # 音量为1
            "pitch": 0,  # 音调为0
            "emotion": "happy"  # 情感为快乐
        }
        # 定义默认的发音字典
        default_pronunciation_dict = {
            "tone": [
                "处理/(chu3)(li3)",  # 自定义“处理”一词的发音
                "危险/dangerous"  # 自定义“危险”一词的发音
            ]
        }
        # 定义默认的音频设置
        defult_audio_setting = {
            "sample_rate": 32000,  # 采样率为32000Hz
            "bitrate": 128000,  # 比特率为128000
            "format": "mp3",  # 音频格式为mp3
            "channel": 1  # 声道数为1
        }
        # 合并默认语音设置和用户提供的语音设置，用户提供的设置会覆盖默认设置
        self.voice_setting = {**default_voice_setting, **config.get("voice_setting", {})}
        # 合并默认发音字典和用户提供的发音字典，用户提供的设置会覆盖默认设置
        self.pronunciation_dict = {**default_pronunciation_dict, **config.get("pronunciation_dict", {})}
        # 合并默认音频设置和用户提供的音频设置，用户提供的设置会覆盖默认设置
        self.audio_setting = {**defult_audio_setting, **config.get("audio_setting", {})}
        # 从配置字典中获取音色权重列表，若未提供则使用空列表
        self.timber_weights = config.get("timber_weights", [])

        # 如果提供了语音ID，则更新语音设置中的语音ID
        if self.voice_id:
            self.voice_setting["voice_id"] = self.voice_id

        # 定义API的主机地址
        self.host = "api.minimax.chat"
        # 构建API的请求URL，包含分组ID
        self.api_url = f"https://{self.host}/v1/t2a_v2?GroupId={self.group_id}"
        # 定义请求头，包含内容类型和授权信息
        self.header = {
            "Content-Type": "application/json",  # 请求内容类型为JSON
            "Authorization": f"Bearer {self.api_key}"  # 授权信息，使用API密钥
        }

    def generate_filename(self, extension=".mp3"):
        """
        生成一个唯一的文件名，用于保存TTS生成的音频文件。

        :param extension: 音频文件的扩展名，默认为".mp3"。
        :return: 包含完整路径和文件名的字符串，文件名由固定前缀、当前日期、唯一的UUID和文件扩展名组成。
        """
        # 使用os.path.join函数将输出文件路径、固定前缀、当前日期、唯一的UUID和文件扩展名组合成完整的文件名
        return os.path.join(self.output_file, f"tts-{__name__}{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将输入的文本转换为语音，并将生成的音频保存到指定的文件中。

        :param text: 要转换为语音的文本内容。
        :param output_file: 保存生成音频文件的完整路径。
        """
        # 构建请求的JSON数据，包含模型名称、输入文本、是否流式传输、语音设置、发音字典和音频设置
        request_json = {
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": self.voice_setting,
            "pronunciation_dict": self.pronunciation_dict,
            "audio_setting": self.audio_setting,
        }

        # 如果音色权重列表不为空，则将其添加到请求JSON数据中，并清空语音设置中的语音ID
        if type(self.timber_weights) is list and len(self.timber_weights) > 0:
            request_json["timber_weights"] = self.timber_weights
            request_json["voice_setting"]["voice_id"] = ""

        try:
            # 向API发送POST请求，携带请求JSON数据和请求头
            resp = requests.post(self.api_url, json.dumps(request_json), headers=self.header)
            # 检查返回请求数据的status_code是否为0，表示请求成功
            if resp.json()["base_resp"]["status_code"] == 0:
                # 从响应中提取音频数据
                data = resp.json()['data']['audio']
                # 以二进制写入模式打开输出文件
                file_to_save = open(output_file, "wb")
                # 将十六进制编码的音频数据转换为字节并写入文件
                file_to_save.write(bytes.fromhex(data))
            else:
                # 若请求失败，抛出异常，包含请求的状态码和响应内容
                raise Exception(f"{__name__} status_code: {resp.status_code} response: {resp.content}")
        except Exception as e:
            # 若发生异常，抛出新的异常，包含异常信息
            raise Exception(f"{__name__} error: {e}")