# 导入os模块，用于处理文件和目录路径相关操作
import os
# 导入uuid模块，用于生成通用唯一识别码，保证生成的文件名具有唯一性
import uuid
# 导入json模块，用于处理JSON数据，如构建请求体和解析响应数据
import json
# 导入requests模块，用于发送HTTP请求，与TTS服务进行交互
import requests
# 导入shutil模块，用于高级的文件和目录操作，这里用于移动文件
import shutil
# 从datetime模块导入datetime类，用于获取当前日期，方便生成带日期的文件名
from datetime import datetime
# 从自定义模块中导入TTS提供者的基类，当前类将继承该基类
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于将文本转换为语音。

        :param config: 包含TTS服务所需配置信息的字典，可能包含以下键值对：
            - url: TTS服务的基础URL，默认为指定的地址。
            - voice_id: 语音的ID，默认为1695。
            - token: 访问TTS服务的令牌。
            - to_lang: 目标语言。
            - volume_change_dB: 音量变化（分贝），默认为0。
            - speed_factor: 语速因子，默认为1。
            - stream: 是否使用流式传输，默认为False。
            - output_file: 生成音频文件的输出路径。
            - pitch_factor: 音调因子，默认为0。
            - format: 音频文件的格式，默认为"mp3"。
            - emotion: 语音的情感，默认为1。
        :param delete_audio_file: 布尔值，指示在完成TTS任务后是否删除生成的音频文件。
        """
        # 调用父类的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取TTS服务的基础URL，若未提供则使用默认值
        self.url = config.get("url", "https://u95167-bd74-2aef8085.westx.seetacloud.com:8443/flashsummary/tts?token=")
        # 从配置字典中获取语音的ID，若未提供则使用默认值
        self.voice_id = config.get("voice_id", 1695)
        # 从配置字典中获取访问TTS服务的令牌
        self.token = config.get("token")
        # 从配置字典中获取目标语言
        self.to_lang = config.get("to_lang")
        # 从配置字典中获取音量变化（分贝），若未提供则使用默认值
        self.volume_change_dB = config.get("volume_change_dB", 0)
        # 从配置字典中获取语速因子，若未提供则使用默认值
        self.speed_factor = config.get("speed_factor", 1)
        # 从配置字典中获取是否使用流式传输，若未提供则使用默认值
        self.stream = config.get("stream", False)
        # 从配置字典中获取生成音频文件的输出路径
        self.output_file = config.get("output_file")
        # 从配置字典中获取音调因子，若未提供则使用默认值
        self.pitch_factor = config.get("pitch_factor", 0)
        # 从配置字典中获取音频文件的格式，若未提供则使用默认值
        self.format = config.get("format", "mp3")
        # 从配置字典中获取语音的情感，若未提供则使用默认值
        self.emotion = config.get("emotion", 1)
        # 定义请求头，指定请求内容的类型为JSON
        self.header = {
            "Content-Type": "application/json"
        }

    def generate_filename(self, extension=".mp3"):
        """
        生成一个唯一的文件名，用于保存TTS生成的音频文件。

        :param extension: 音频文件的扩展名，默认为".mp3"。
        :return: 包含完整路径和文件名的字符串，文件名由固定前缀、当前日期、唯一的UUID和文件扩展名组成。
        """
        # 使用os.path.join函数将输出文件路径、固定前缀、当前日期、唯一的UUID和文件扩展名组合成完整的文件名
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将输入的文本转换为语音，并将生成的音频保存到指定的文件中。

        :param text: 要转换为语音的文本内容。
        :param output_file: 保存生成音频文件的完整路径。
        :return: 如果音频文件保存成功返回True，否则返回None。
        """
        # 构建完整的请求URL，将基础URL和令牌拼接在一起
        url = f'{self.url}{self.token}'
        # 初始化结果变量
        result = "firefly"
        # 构建请求的JSON数据，包含目标语言、文本、情感、格式等配置信息
        payload = json.dumps({
            "to_lang": self.to_lang,
            "text": text,
            "emotion": self.emotion,
            "format": self.format,
            "volume_change_dB": self.volume_change_dB,
            "voice_id": self.voice_id,
            "pitch_factor": self.pitch_factor,
            "speed_factor": self.speed_factor,
            "token": self.token
        })

        # 发送POST请求到TTS服务，携带请求数据
        resp = requests.request("POST", url, data=payload)
        # 检查响应的状态码是否为200，若不是则返回None
        if resp.status_code != 200:
            return None
        # 将响应内容解析为JSON格式
        resp_json = resp.json()
        try:
            # 从响应的JSON数据中提取音频文件的下载URL
            result = resp_json['url'] + ':' + str(
                resp_json[
                    'port']) + '/flashsummary/retrieveFileData?stream=True&token=' + self.token + '&voice_audio_path=' + \
                     resp_json['voice_path']
        except Exception as e:
            # 若提取下载URL时出现异常，打印错误信息
            print("error:", e)

        # 发送GET请求到音频文件的下载URL，获取音频内容
        audio_content = requests.get(result)
        # 以二进制写入模式打开指定的输出文件
        with open(output_file, "wb") as f:
            # 将音频内容写入文件
            f.write(audio_content.content)
            # 写入成功后返回True
            return True
        # 从响应的JSON数据中获取语音文件的原始路径
        voice_path = resp_json.get("voice_path")
        # 目标路径为指定的输出文件路径
        des_path = output_file
        # 将语音文件从原始路径移动到目标路径
        shutil.move(voice_path, des_path)