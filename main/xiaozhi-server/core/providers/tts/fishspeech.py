# 导入用于处理Base64编码的模块
import base64
# 导入用于操作系统相关功能的模块
import os
# 导入用于生成通用唯一识别码（UUID）的模块
import uuid
# 导入用于发送HTTP请求的模块
import requests
# 导入用于序列化和反序列化消息包的模块
import ormsgpack
# 导入用于处理文件路径的模块
from pathlib import Path
# 从pydantic库导入基础模型、字段、整数约束和模型验证器
from pydantic import BaseModel, Field, conint, model_validator
# 从typing_extensions库导入Annotated类型
from typing_extensions import Annotated
# 从datetime模块导入日期时间类
from datetime import datetime
# 从typing模块导入Literal类型
from typing import Literal
# 从自定义模块中导入检查模型密钥的函数
from core.utils.util import check_model_key
# 从自定义模块中导入TTS提供者的基类
from core.providers.tts.base import TTSProviderBase
# 从自定义配置模块中导入设置日志的函数
from config.logger import setup_logging

# 获取当前模块的名称作为标签
TAG = __name__
# 调用设置日志的函数并获取日志记录器
logger = setup_logging()


class ServeReferenceAudio(BaseModel):
    """
    该类用于表示参考音频数据，继承自pydantic的BaseModel，可对数据进行验证和序列化。
    """
    # 音频数据，以字节形式存储
    audio: bytes
    # 与音频对应的文本
    text: str

    @model_validator(mode="before")
    def decode_audio(cls, values):
        """
        在模型验证之前对音频数据进行解码操作。
        如果音频数据是Base64编码的字符串，则尝试将其解码为字节类型。
        :param values: 包含模型字段值的字典
        :return: 处理后的字段值字典
        """
        # 从传入的值中获取音频数据
        audio = values.get("audio")
        # 检查音频数据是否为字符串且长度超过255，以判断是否为Base64编码
        if (
                isinstance(audio, str) and len(audio) > 255
        ):
            try:
                # 尝试对Base64编码的音频数据进行解码
                values["audio"] = base64.b64decode(audio)
            except Exception as e:
                # 若解码失败，忽略该错误，让服务器处理此情况
                pass
        return values

    def __repr__(self) -> str:
        """
        返回对象的字符串表示形式，方便调试和日志记录。
        :return: 包含文本和音频数据大小的字符串
        """
        return f"ServeReferenceAudio(text={self.text!r}, audio_size={len(self.audio)})"


class ServeTTSRequest(BaseModel):
    """
    该类用于表示TTS（文本转语音）请求，继承自pydantic的BaseModel，可对请求数据进行验证和序列化。
    """
    # 要转换为语音的文本
    text: str
    # 每个文本块的长度，范围在100到300之间，默认为200
    chunk_length: Annotated[int, conint(ge=100, le=300, strict=True)] = 200
    # 音频的格式，可选值为"wav"、"pcm"、"mp3"，默认为"wav"
    format: Literal["wav", "pcm", "mp3"] = "wav"
    # 用于上下文学习的参考音频列表
    references: list[ServeReferenceAudio] = []
    # 参考音频的ID
    reference_id: str | None = None
    # 随机数种子，用于控制生成语音的随机性
    seed: int | None = None
    # 是否使用内存缓存，可选值为"on"或"off"，默认为"off"
    use_memory_cache: Literal["on", "off"] = "off"
    # 是否对英文和中文文本进行规范化处理，以提高数字的稳定性，默认为True
    normalize: bool = True
    # 以下参数通常不常用
    # 是否使用流式传输，默认为False
    streaming: bool = False
    # 生成语音的最大新令牌数，默认为1024
    max_new_tokens: int = 1024
    # 采样概率，范围在0.1到1.0之间，默认为0.7
    top_p: Annotated[float, Field(ge=0.1, le=1.0, strict=True)] = 0.7
    # 重复惩罚因子，范围在0.9到2.0之间，默认为1.2
    repetition_penalty: Annotated[float, Field(ge=0.9, le=2.0, strict=True)] = 1.2
    # 温度参数，范围在0.1到1.0之间，默认为0.7
    temperature: Annotated[float, Field(ge=0.1, le=1.0, strict=True)] = 0.7

    class Config:
        # 允许使用任意类型，以支持与PyTorch相关的类型
        arbitrary_types_allowed = True


def audio_to_bytes(file_path):
    """
    将音频文件读取为字节数据。
    :param file_path: 音频文件的路径
    :return: 音频文件的字节数据，如果文件路径无效或文件不存在则返回None
    """
    # 检查文件路径是否有效或文件是否存在
    if not file_path or not Path(file_path).exists():
        return None
    # 以二进制读取模式打开音频文件
    with open(file_path, "rb") as wav_file:
        # 读取文件内容
        wav = wav_file.read()
    return wav


def read_ref_text(ref_text):
    """
    读取参考文本文件内容。
    如果传入的是文件路径，则读取文件内容；否则直接返回传入的文本。
    :param ref_text: 参考文本或文本文件路径
    :return: 参考文本内容
    """
    # 将传入的路径转换为Path对象
    path = Path(ref_text)
    # 检查路径对应的文件是否存在且为普通文件
    if path.exists() and path.is_file():
        # 以文本读取模式打开文件
        with path.open("r", encoding="utf-8") as file:
            # 读取文件内容
            return file.read()
    return ref_text


class TTSProvider(TTSProviderBase):
    """
    该类用于提供文本转语音（TTS）服务，继承自TTSProviderBase。
    """

    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例。
        :param config: 包含TTS服务配置信息的字典
        :param delete_audio_file: 布尔值，指示是否删除生成的音频文件
        """
        # 调用父类的构造函数进行初始化
        super().__init__(config, delete_audio_file)

        # 从配置中获取参考音频的ID
        self.reference_id = config.get("reference_id")
        # 从配置中获取参考音频文件路径列表，默认为空列表
        self.reference_audio = config.get("reference_audio", [])
        # 从配置中获取参考文本文件路径或文本列表，默认为空列表
        self.reference_text = config.get("reference_text", [])
        # 从配置中获取音频格式，默认为"wav"
        self.format = config.get("format", "wav")
        # 从配置中获取音频通道数，默认为1
        self.channels = config.get("channels", 1)
        # 从配置中获取音频采样率，默认为44100
        self.rate = config.get("rate", 44100)
        # 从配置中获取API密钥，默认为"YOUR_API_KEY"
        self.api_key = config.get("api_key", "YOUR_API_KEY")
        # 检查API密钥是否有效
        have_key = check_model_key("FishSpeech TTS", self.api_key)
        # 如果API密钥无效，则直接返回
        if not have_key:
            return
        # 从配置中获取是否对文本进行规范化处理，默认为True
        self.normalize = config.get("normalize", True)
        # 从配置中获取生成语音的最大新令牌数，默认为1024
        self.max_new_tokens = config.get("max_new_tokens", 1024)
        # 从配置中获取每个文本块的长度，默认为200
        self.chunk_length = config.get("chunk_length", 200)
        # 从配置中获取采样概率，默认为0.7
        self.top_p = config.get("top_p", 0.7)
        # 从配置中获取重复惩罚因子，默认为1.2
        self.repetition_penalty = config.get("repetition_penalty", 1.2)
        # 从配置中获取温度参数，默认为0.7
        self.temperature = config.get("temperature", 0.7)
        # 从配置中获取是否使用流式传输，默认为False
        self.streaming = config.get("streaming", False)
        # 从配置中获取是否使用内存缓存，默认为"on"
        self.use_memory_cache = config.get("use_memory_cache", "on")
        # 从配置中获取随机数种子
        self.seed = config.get("seed")
        # 从配置中获取API的URL，默认为"http://127.0.0.1:8080/v1/tts"
        self.api_url = config.get("api_url", "http://127.0.0.1:8080/v1/tts")

    def generate_filename(self, extension=".wav"):
        """
        生成用于保存TTS音频文件的文件名。
        :param extension: 音频文件的扩展名，默认为".wav"
        :return: 包含完整路径和文件名的字符串
        """
        # 使用os.path.join函数将输出文件路径、固定前缀、当前日期、唯一的UUID和文件扩展名组合成完整的文件名
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将输入的文本转换为语音，并将生成的音频保存到指定文件。
        :param text: 要转换为语音的文本内容
        :param output_file: 保存生成音频文件的路径
        """
        # 准备参考数据，将参考音频文件转换为字节数据
        byte_audios = [audio_to_bytes(ref_audio) for ref_audio in self.reference_audio]
        # 准备参考数据，读取参考文本文件内容
        ref_texts = [read_ref_text(ref_text) for ref_text in self.reference_text]

        # 构建请求数据字典
        data = {
            "text": text,
            "references": [
                ServeReferenceAudio(
                    audio=audio if audio else b"", text=text
                )
                for text, audio in zip(ref_texts, byte_audios)
            ],
            "reference_id": self.reference_id,
            "normalize": self.normalize,
            "format": self.format,
            "max_new_tokens": self.max_new_tokens,
            "chunk_length": self.chunk_length,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty,
            "temperature": self.temperature,
            "streaming": self.streaming,
            "use_memory_cache": self.use_memory_cache,
            "seed": self.seed,
        }

        # 使用请求数据字典创建ServeTTSRequest对象
        pydantic_data = ServeTTSRequest(**data)

        # 发送POST请求到API，使用ormsgpack对请求数据进行序列化
        response = requests.post(
            self.api_url,
            data=ormsgpack.packb(pydantic_data, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
            headers={
                # 在请求头中添加授权信息
                "Authorization": f"Bearer {self.api_key}",
                # 指定请求体的内容类型为application/msgpack
                "Content-Type": "application/msgpack",
            },
        )

        # 检查响应状态码是否为200，表示请求成功
        if response.status_code == 200:
            # 获取响应中的音频内容
            audio_content = response.content

            # 以二进制写入模式打开输出文件
            with open(output_file, "wb") as audio_file:
                # 将音频内容写入文件
                audio_file.write(audio_content)
        else:
            # 若请求失败，打印失败的状态码
            print(f"Request failed with status code {response.status_code}")
            # 打印响应的JSON数据
            print(response.json())
