import os
import uuid
import json
import base64
import requests
from datetime import datetime
from core.providers.tts.base import TTSProviderBase

class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于实现文本转语音（TTS）功能。

        :param config: 包含TTS服务所需配置信息的字典，
                       其中应包含model（模型名称）、access_token（访问令牌）、
                       voice（语音类型）、response_format（响应格式）等配置项。
        :param delete_audio_file: 一个布尔值，用于指示是否在完成某些操作后删除生成的音频文件，
                                  该参数传递给父类的构造函数进行处理。
        """
        # 调用父类TTSProviderBase的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置中获取使用的TTS模型名称
        self.model = config.get("model")
        # 从配置中获取访问TTS服务所需的访问令牌
        self.access_token = config.get("access_token")
        # 从配置中获取语音类型，用于指定合成语音的风格
        self.voice = config.get("voice")
        # 从配置中获取响应的格式，例如音频文件的格式
        self.response_format = config.get("response_format")

        # 设置TTS服务的主机地址
        self.host = "api.coze.cn"
        # 构建TTS服务的API请求URL
        self.api_url = f"https://{self.host}/v1/audio/speech"

    def generate_filename(self, extension=".wav"):
        """
        生成用于保存合成音频文件的文件名。

        :param extension: 音频文件的扩展名，默认为".wav"。
        :return: 包含完整路径和文件名的字符串，文件名包含当前日期和唯一的UUID，以确保文件名的唯一性。
        """
        # 将输出文件路径、固定前缀、当前日期、唯一UUID和文件扩展名组合成完整的文件名
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将输入的文本转换为语音，并将生成的音频数据保存到指定的文件中。

        :param text: 要转换为语音的文本内容。
        :param output_file: 用于保存生成音频数据的文件路径。
        """
        # 构建请求的JSON数据，包含模型名称、输入文本、语音类型和响应格式
        request_json = {
            "model": self.model,
            "input": text,
            "voice_id": self.voice,
            "response_format": self.response_format,
        }
        # 构建请求头，包含授权信息和内容类型
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        # 发送POST请求到TTS服务的API，传递请求的JSON数据和请求头
        response = requests.request("POST", self.api_url, json=request_json, headers=headers)
        # 获取响应的二进制内容，即生成的音频数据
        data = response.content
        # 以二进制写入模式打开指定的输出文件
        file_to_save = open(output_file, "wb")
        # 将音频数据写入文件
        file_to_save.write(data)