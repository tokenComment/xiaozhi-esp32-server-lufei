import os
import uuid
import json
import base64
import requests
from datetime import datetime
from core.utils.util import check_model_key
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例。

        :param config: 包含TTS服务配置信息的字典，
                       应包含appid（应用ID）、access_token（访问令牌）、
                       cluster（集群信息）、voice（语音类型）、
                       api_url（API地址）、authorization（授权信息）等配置项。
        :param delete_audio_file: 布尔值，指示是否删除生成的音频文件，
                                  该参数会传递给父类的构造函数。
        """
        # 调用父类TTSProviderBase的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取应用ID并赋值给实例属性
        self.appid = config.get("appid")
        # 从配置字典中获取访问令牌并赋值给实例属性
        self.access_token = config.get("access_token")
        # 从配置字典中获取集群信息并赋值给实例属性
        self.cluster = config.get("cluster")
        # 从配置字典中获取语音类型并赋值给实例属性
        self.voice = config.get("voice")
        # 从配置字典中获取API地址并赋值给实例属性
        self.api_url = config.get("api_url")
        # 从配置字典中获取授权信息并赋值给实例属性
        self.authorization = config.get("authorization")
        # 构建请求头，包含授权信息和访问令牌
        self.header = {"Authorization": f"{self.authorization}{self.access_token}"}
        # 检查TTS服务的访问令牌是否有效
        check_model_key("TTS", self.access_token)

    def generate_filename(self, extension=".wav"):
        """
        生成用于保存TTS音频文件的文件名。

        :param extension: 音频文件的扩展名，默认为".wav"。
        :return: 包含完整路径和文件名的字符串，文件名由固定前缀、当前日期、唯一UUID和扩展名组成。
        """
        # 使用os.path.join拼接路径和文件名，文件名包含当前日期和唯一UUID
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将输入的文本转换为语音，并将生成的音频数据保存到指定的文件中。

        :param text: 要转换为语音的文本内容。
        :param output_file: 保存生成音频数据的文件路径。
        """
        # 构建请求的JSON数据，包含应用信息、用户信息、音频参数和请求信息
        request_json = {
            "app": {
                "appid": f"{self.appid}",
                "token": "access_token",
                "cluster": self.cluster
            },
            "user": {
                "uid": "1"
            },
            "audio": {
                "voice_type": self.voice,
                "encoding": "wav",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
                "with_frontend": 1,
                "frontend_type": "unitTson"
            }
        }

        try:
            # 发送POST请求到TTS服务的API，传递请求的JSON数据和请求头
            resp = requests.post(self.api_url, json.dumps(request_json), headers=self.header)
            # 检查响应的JSON数据中是否包含"data"字段
            if "data" in resp.json():
                # 从响应的JSON数据中获取音频数据
                data = resp.json()["data"]
                # 以二进制写入模式打开输出文件
                file_to_save = open(output_file, "wb")
                # 对音频数据进行Base64解码，并写入文件
                file_to_save.write(base64.b64decode(data))
            else:
                # 如果响应中不包含"data"字段，抛出异常，包含模块名、状态码和响应内容
                raise Exception(f"{__name__} status_code: {resp.status_code} response: {resp.content}")
        except Exception as e:
            # 如果在请求或处理过程中发生异常，抛出异常，包含模块名和异常信息
            raise Exception(f"{__name__} error: {e}")