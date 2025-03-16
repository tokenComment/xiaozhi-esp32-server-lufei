# 导入os模块，用于处理文件路径和操作系统相关功能
import os
# 导入uuid模块，用于生成通用唯一识别码，确保生成的文件名具有唯一性
import uuid
# 导入requests模块，用于发送HTTP请求，与OpenAI的TTS服务进行通信
import requests
# 从datetime模块导入日期时间类，用于生成包含当前日期的文件名
from datetime import datetime
# 从自定义模块中导入检查模型密钥的函数，用于验证API密钥的有效性
from core.utils.util import check_model_key
# 从自定义模块中导入TTS提供者的基类，当前类继承自该基类
from core.providers.tts.base import TTSProviderBase

class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于调用OpenAI的TTS服务将文本转换为语音。

        :param config: 包含TTS服务配置信息的字典，包含以下可能的配置项：
            - api_key: 用于访问OpenAI API的密钥，用于身份验证。
            - api_url: 调用TTS服务的API URL，默认为OpenAI的TTS服务URL。
            - model: 要使用的TTS模型名称，默认为"tts-1"。
            - voice: 语音类型，默认为"alloy"。
            - speed: 语音的播放速度，默认为1.0。
            - output_file: 生成音频文件的保存路径，默认为"tmp/"。
        :param delete_audio_file: 布尔值，指示是否在完成TTS任务后删除生成的音频文件。
        """
        # 调用父类的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取API密钥
        self.api_key = config.get("api_key")
        # 从配置字典中获取API URL，若未提供则使用默认的OpenAI TTS服务URL
        self.api_url = config.get("api_url", "https://api.openai.com/v1/audio/speech")
        # 从配置字典中获取要使用的TTS模型名称，若未提供则使用默认值"tts-1"
        self.model = config.get("model", "tts-1")
        # 从配置字典中获取语音类型，若未提供则使用默认值"alloy"
        self.voice = config.get("voice", "alloy")
        # 设置响应的音频格式为wav
        self.response_format = "wav"
        # 从配置字典中获取语音的播放速度，若未提供则使用默认值1.0
        self.speed = config.get("speed", 1.0)
        # 从配置字典中获取生成音频文件的保存路径，若未提供则使用默认值"tmp/"
        self.output_file = config.get("output_file", "tmp/")
        # 调用检查模型密钥的函数，验证TTS服务的API密钥是否有效
        check_model_key("TTS", self.api_key)

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
        # 定义请求头，包含授权信息和内容类型
        headers = {
            "Authorization": f"Bearer {self.api_key}",  # 使用API密钥进行身份验证
            "Content-Type": "application/json"  # 请求内容类型为JSON
        }
        # 定义请求数据，包含要使用的模型、输入文本、语音类型、响应格式和播放速度
        data = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": "wav",
            "speed": self.speed
        }
        # 向API发送POST请求，携带请求数据和请求头
        response = requests.post(self.api_url, json=data, headers=headers)
        # 检查响应的状态码是否为200，表示请求成功
        if response.status_code == 200:
            # 若请求成功，以二进制写入模式打开指定的输出文件
            with open(output_file, "wb") as audio_file:
                # 将响应的内容（即生成的音频数据）写入文件
                audio_file.write(response.content)
        else:
            # 若请求失败，抛出异常，包含请求的状态码和响应文本
            raise Exception(f"OpenAI TTS请求失败: {response.status_code} - {response.text}")