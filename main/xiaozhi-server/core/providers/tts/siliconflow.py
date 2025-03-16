# 导入os模块，用于处理文件和目录路径相关操作
import os
# 导入uuid模块，用于生成通用唯一识别码，可保证生成的文件名具有唯一性
import uuid
# 导入requests模块，用于发送HTTP请求，以与外部API进行交互
import requests
# 从datetime模块导入datetime类，用于获取当前日期，方便生成带日期的文件名
from datetime import datetime
# 从自定义模块中导入TTS提供者的基类，当前类将继承该基类
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于调用语音合成服务将文本转换为语音。

        :param config: 包含语音合成服务所需配置信息的字典，可能包含以下键值对：
            - model: 要使用的语音合成模型。
            - access_token: 用于访问API的令牌，进行身份验证。
            - voice: 选择的语音类型。
            - response_format: 响应的音频格式。
            - sample_rate: 音频的采样率。
            - speed: 语音的播放速度。
            - gain: 音频的增益。
        :param delete_audio_file: 布尔值，指示在完成语音合成任务后是否删除生成的音频文件。
        """
        # 调用父类的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取要使用的语音合成模型
        self.model = config.get("model")
        # 从配置字典中获取用于访问API的令牌
        self.access_token = config.get("access_token")
        # 从配置字典中获取选择的语音类型
        self.voice = config.get("voice")
        # 从配置字典中获取响应的音频格式
        self.response_format = config.get("response_format")
        # 从配置字典中获取音频的采样率
        self.sample_rate = config.get("sample_rate")
        # 从配置字典中获取语音的播放速度
        self.speed = config.get("speed")
        # 从配置字典中获取音频的增益
        self.gain = config.get("gain")

        # 定义API的主机地址
        self.host = "api.siliconflow.cn"
        # 构建API的请求URL
        self.api_url = f"https://{self.host}/v1/audio/speech"

    def generate_filename(self, extension=".wav"):
        """
        生成一个唯一的文件名，用于保存语音合成生成的音频文件。

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
        # 构建请求的JSON数据，包含模型、输入文本、语音类型和响应格式
        request_json = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": self.response_format,
        }
        # 定义请求头，包含授权信息和内容类型
        headers = {
            "Authorization": f"Bearer {self.access_token}",  # 使用访问令牌进行身份验证
            "Content-Type": "application/json"  # 请求内容类型为JSON
        }
        # 发送POST请求到API，携带请求的JSON数据和请求头
        response = requests.request("POST", self.api_url, json=request_json, headers=headers)
        # 获取响应的内容（即生成的音频数据）
        data = response.content
        # 以二进制写入模式打开指定的输出文件
        file_to_save = open(output_file, "wb")
        # 将音频数据写入文件
        file_to_save.write(data)