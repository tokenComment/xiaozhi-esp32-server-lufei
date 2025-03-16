import time
import wave
import os
import sys
import io
from config.logger import setup_logging
from typing import Optional, Tuple, List
import uuid
import opuslib_next
from core.providers.asr.base import ASRProviderBase

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

TAG = __name__
logger = setup_logging()


# 捕获标准输出
class CaptureOutput:
    """
    上下文管理器，用于捕获标准输出并将其记录到日志中。

    功能：
        1. 使用 `io.StringIO` 捕获 `sys.stdout` 的输出。
        2. 在退出上下文时，将捕获的内容通过 `logger` 输出。
    """
    def __enter__(self):
        self._output = io.StringIO()  # 创建一个字符串流对象
        self._original_stdout = sys.stdout  # 保存原始标准输出
        sys.stdout = self._output  # 将标准输出重定向到字符串流

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout  # 恢复原始标准输出
        self.output = self._output.getvalue()  # 获取捕获的内容
        self._output.close()  # 关闭字符串流

        # 将捕获到的内容通过 logger 输出
        if self.output:
            logger.bind(tag=TAG).info(self.output.strip())


class ASRProvider(ASRProviderBase):
    """
    ASR（自动语音识别）服务提供者。

    功能：
        1. 将 Opus 格式的音频数据解码并保存为 WAV 文件。
        2. 使用 FunASR 模型进行语音识别。
        3. 提供语音转文本的功能。
    """

    def __init__(self, config: dict, delete_audio_file: bool):
        """
        初始化 ASRProvider。

        参数：
            config (dict): 配置信息，包含模型路径和输出目录。
            delete_audio_file (bool): 是否删除保存的音频文件。
        """
        self.model_dir = config.get("model_dir")  # 模型路径
        self.output_dir = config.get("output_dir")  # 输出目录
        self.delete_audio_file = delete_audio_file  # 是否删除音频文件

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

        # 初始化 FunASR 模型
        with CaptureOutput():  # 捕获模型初始化时的输出
            self.model = AutoModel(
                model=self.model_dir,
                vad_kwargs={"max_single_segment_time": 30000},  # VAD 参数
                disable_update=True,  # 禁用模型更新
                hub="hf"  # 使用 Hugging Face Hub
                # device="cuda:0",  # 启用 GPU 加速（如果需要）
            )

    def save_audio_to_file(self, opus_data: List[bytes], session_id: str) -> str:
        """
        将 Opus 格式的音频数据解码并保存为 WAV 文件。

        参数：
            opus_data (List[bytes]): Opus 格式的音频数据。
            session_id (str): 会话 ID。

        返回：
            str: 保存的 WAV 文件路径。
        """
        file_name = f"asr_{session_id}_{uuid.uuid4()}.wav"  # 生成文件名
        file_path = os.path.join(self.output_dir, file_name)  # 生成文件路径

        decoder = opuslib_next.Decoder(16000, 1)  # 创建 Opus 解码器（16kHz, 单声道）
        pcm_data = []

        for opus_packet in opus_data:
            try:
                pcm_frame = decoder.decode(opus_packet, 960)  # 解码 Opus 数据（960 samples = 60ms）
                pcm_data.append(pcm_frame)
            except opuslib_next.OpusError as e:
                logger.bind(tag=TAG).error(f"Opus 解码错误: {e}", exc_info=True)

        # 将 PCM 数据保存为 WAV 文件
        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(1)  # 声道数
            wf.setsampwidth(2)  # 采样宽度（2 字节 = 16-bit）
            wf.setframerate(16000)  # 采样率
            wf.writeframes(b"".join(pcm_data))  # 写入 PCM 数据

        return file_path

    async def speech_to_text(self, opus_data: List[bytes], session_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
    将 Opus 格式的语音数据转换为文本。

    功能：
        1. 将 Opus 音频数据解码并保存为 WAV 文件。
        2. 使用 FunASR 模型进行语音识别。
        3. 对识别结果进行后处理并返回识别文本。
        4. 根据配置决定是否删除临时保存的音频文件。

    参数：
        opus_data (List[bytes]): Opus 格式的音频数据，以字节列表的形式提供。
        session_id (str): 会话 ID，用于标识当前会话。

    返回：
        Tuple[Optional[str], Optional[str]]: 一个元组，包含以下两个值：
            - 识别结果文本（如果识别成功，否则为空字符串）。
            - 音频文件路径（如果保存了音频文件，否则为 None）。

    逻辑：
        1. 调用 `save_audio_to_file` 方法将 Opus 数据解码并保存为 WAV 文件。
        2. 使用 FunASR 模型的 `generate` 方法进行语音识别。
        3. 对识别结果进行后处理（`rich_transcription_postprocess`）。
        4. 如果配置中指定删除临时文件，则在识别完成后删除 WAV 文件。
        5. 返回识别结果文本和音频文件路径（或 None）。

    示例：
        >>> opus_data = [b'...Opus数据1...', b'...Opus数据2...']  # 替换为实际的 Opus 数据
        >>> session_id = "example_session_id"  # 会话 ID
        >>> text, audio_file_path = await asr_provider.speech_to_text(opus_data, session_id)
        >>> print(f"识别结果: {text}")
        识别结果: "这是识别的文本内容"

    注意：
        - 输入的 `opus_data` 必须是有效的 Opus 格式音频数据。
        - 如果识别失败或发生异常，将返回空字符串和 None。
        - 该方法是异步的，需要在异步环境中调用。
        """
        file_path = None  # 初始化音频文件路径为 None
        try:
            # 保存音频文件
            start_time = time.time()  # 记录开始时间
            file_path = self.save_audio_to_file(opus_data, session_id)  # 将 Opus 数据解码并保存为 WAV 文件
            logger.bind(tag=TAG).debug(f"音频文件保存耗时: {time.time() - start_time:.3f}s | 路径: {file_path}")

            # 语音识别
            start_time = time.time()  # 记录开始时间
            result = self.model.generate(  # 使用 FunASR 模型进行语音识别
                input=file_path,
                cache={},
                language="auto",  # 自动检测语言
                use_itn=True,  # 启用逆文本归一化
                batch_size_s=60,  # 每批次处理时长（秒）
            )
            text = rich_transcription_postprocess(result[0]["text"])  # 对识别结果进行后处理
            logger.bind(tag=TAG).debug(f"语音识别耗时: {time.time() - start_time:.3f}s | 结果: {text}")

            return text, file_path  # 返回识别结果和音频文件路径

        except Exception as e:
            logger.bind(tag=TAG).error(f"语音识别失败: {e}", exc_info=True)  # 记录错误日志
            return "", None  # 返回空字符串和 None

        finally:
            # 文件清理逻辑
            if self.delete_audio_file and file_path and os.path.exists(file_path):  # 如果需要删除临时文件
                try:
                    os.remove(file_path)  # 删除音频文件
                    logger.bind(tag=TAG).debug(f"已删除临时音频文件: {file_path}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"文件删除失败: {file_path} | 错误: {e}")