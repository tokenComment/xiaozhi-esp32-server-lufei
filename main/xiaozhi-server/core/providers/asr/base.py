from abc import ABC, abstractmethod
from typing import Optional, Tuple, List

from config.logger import setup_logging

TAG = __name__  # 定义日志标签，用于在日志中标识模块名称
logger = setup_logging()  # 初始化日志记录器


class ASRProviderBase(ABC):
    """
    ASR（自动语音识别）服务提供者的抽象基类。

    功能：
        定义了 ASR 服务提供者必须实现的接口方法，包括：
        1. 将 Opus 格式的音频数据解码并保存为 WAV 文件。
        2. 将语音数据转换为文本。

    说明：
        该类是一个抽象基类，不能直接实例化。具体实现需要继承该类并实现其抽象方法。
    """

    @abstractmethod
    def save_audio_to_file(self, opus_data: List[bytes], session_id: str) -> str:
        """
        将 Opus 格式的音频数据解码并保存为 WAV 文件。

        参数：
            opus_data (List[bytes]): Opus 格式的音频数据，以字节列表的形式提供。
            session_id (str): 会话 ID，用于标识当前会话。

        返回：
            str: 保存后的 WAV 文件路径。

        功能：
            1. 接收 Opus 格式的音频数据。
            2. 解码 Opus 数据并转换为 WAV 格式。
            3. 将 WAV 数据保存到文件中，并返回文件路径。
        """
        pass

    @abstractmethod
    async def speech_to_text(self, opus_data: List[bytes], session_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        将语音数据转换为文本。

        参数：
            opus_data (List[bytes]): Opus 格式的音频数据，以字节列表的形式提供。
            session_id (str): 会话 ID，用于标识当前会话。

        返回：
            Tuple[Optional[str], Optional[str]]: 一个元组，包含：
                - 转换后的文本（如果成功识别）。
                - 保存的音频文件路径（如果需要保存）。

        功能：
            1. 接收 Opus 格式的音频数据。
            2. 将音频数据转换为文本（通过语音识别技术）。
            3. 返回识别结果和相关文件路径（如果需要）。
        """
        pass