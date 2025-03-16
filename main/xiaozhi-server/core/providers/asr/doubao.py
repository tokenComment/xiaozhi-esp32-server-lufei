import time
import io
import wave
import os
from typing import Optional, Tuple, List
import uuid
import websockets
import json
import gzip

import opuslib_next
from core.providers.asr.base import ASRProviderBase

from config.logger import setup_logging

TAG = __name__  # 定义日志标签，用于在日志中标识模块名称
logger = setup_logging()  # 初始化日志记录器

# 定义协议相关的常量
CLIENT_FULL_REQUEST = 0b0001  # 客户端完整请求
CLIENT_AUDIO_ONLY_REQUEST = 0b0010  # 客户端仅音频请求

NO_SEQUENCE = 0b0000  # 无序列标志
NEG_SEQUENCE = 0b0010  # 负序列标志

SERVER_FULL_RESPONSE = 0b1001  # 服务器完整响应
SERVER_ACK = 0b1011  # 服务器确认响应
SERVER_ERROR_RESPONSE = 0b1111  # 服务器错误响应

NO_SERIALIZATION = 0b0000  # 无序列化
JSON = 0b0001  # JSON 序列化
THRIFT = 0b0011  # Thrift 序列化
CUSTOM_TYPE = 0b1111  # 自定义类型

NO_COMPRESSION = 0b0000  # 无压缩
GZIP = 0b0001  # Gzip 压缩
CUSTOM_COMPRESSION = 0b1111  # 自定义压缩


def parse_response(res):
    """
    解析服务器响应数据。

    响应数据格式：
    protocol_version(4 bits), header_size(4 bits),
    message_type(4 bits), message_type_specific_flags(4 bits)
    serialization_method(4 bits) message_compression(4 bits)
    reserved (8 bits) 保留字段
    header_extensions 扩展头(大小等于 8 * 4 * (header_size - 1) )
    payload 类似于 HTTP 请求体

    参数：
        res (bytes): 服务器响应的原始字节数据。

    返回：
        dict: 解析后的响应数据。
    """
    protocol_version = res[0] >> 4  # 协议版本
    header_size = res[0] & 0x0f  # 头部大小
    message_type = res[1] >> 4  # 消息类型
    message_type_specific_flags = res[1] & 0x0f  # 消息类型特定标志
    serialization_method = res[2] >> 4  # 序列化方法
    message_compression = res[2] & 0x0f  # 压缩方法
    reserved = res[3]  # 保留字段
    header_extensions = res[4:header_size * 4]  # 扩展头
    payload = res[header_size * 4:]  # 负载数据

    result = {}
    payload_msg = None
    payload_size = 0

    # 根据消息类型解析负载数据
    if message_type == SERVER_FULL_RESPONSE:
        payload_size = int.from_bytes(payload[:4], "big", signed=True)
        payload_msg = payload[4:]
    elif message_type == SERVER_ACK:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result['seq'] = seq
        if len(payload) >= 8:
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]
    elif message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        result['code'] = code
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]

    # 解压缩和反序列化负载数据
    if payload_msg is not None:
        if message_compression == GZIP:
            payload_msg = gzip.decompress(payload_msg)
        if serialization_method == JSON:
            payload_msg = json.loads(str(payload_msg, "utf-8"))
        elif serialization_method != NO_SERIALIZATION:
            payload_msg = str(payload_msg, "utf-8")

    result['payload_msg'] = payload_msg
    result['payload_size'] = payload_size
    return result


class ASRProvider(ASRProviderBase):
    """
    ASR（自动语音识别）服务提供者。

    功能：
        1. 将 Opus 格式的音频数据解码并保存为 WAV 文件。
        2. 将音频数据发送到 ASR 服务并获取识别结果。
    """

    def __init__(self, config: dict, delete_audio_file: bool):
        """
        初始化 ASRProvider。

        参数：
            config (dict): ASR 服务的配置信息，包括 appid、cluster、access_token 等。
            delete_audio_file (bool): 是否删除保存的音频文件。
        """
        self.appid = config.get("appid")  # 应用 ID
        self.cluster = config.get("cluster")  # 集群信息
        self.access_token = config.get("access_token")  # 访问令牌
        self.output_dir = config.get("output_dir")  # 音频文件保存目录

        self.host = "openspeech.bytedance.com"  # ASR 服务主机
        self.ws_url = f"wss://{self.host}/api/v2/asr"  # WebSocket URL
        self.success_code = 1000  # 成功响应码
        self.seg_duration = 15000  # 分段时长（毫秒）

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    def save_audio_to_file(self, opus_data: List[bytes], session_id: str) -> str:
        """
        将 Opus 音频数据解码并保存为 WAV 文件。

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
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 采样宽度为 2 字节（16-bit）
            wf.setframerate(16000)  # 采样率为 16kHz
            wf.writeframes(b"".join(pcm_data))

        return file_path

    @staticmethod
    def _generate_header(message_type=CLIENT_FULL_REQUEST, message_type_specific_flags=NO_SEQUENCE) -> bytearray:
        """
        生成协议头部。

        参数：
            message_type (int): 消息类型，默认为客户端完整请求。
            message_type_specific_flags (int): 消息类型特定标志，默认为无序列标志。

        返回：
            bytearray: 生成的协议头部。
        """
        header = bytearray()
        header_size = 1  # 头部大小为 1
        header.append((0b0001 << 4) | header_size)  # 协议版本
        header.append((message_type << 4) | message_type_specific_flags)
        header.append((0b0001 << 4) | 0b0001)  # JSON 序列化 & GZIP 压缩
        header.append(0x00)  # 保留字段
        return header

    def _construct_request(self, reqid) -> dict:
        """
        构造请求负载。

        参数：
            reqid (str): 请求 ID。

        返回：
            dict: 请求负载。
        """
        return {
            "app": {
                "appid": f"{self.appid}",  # 应用 ID
                "cluster": self.cluster,  # 集群信息
                "token": self.access_token,  # 访问令牌
            },
            "user": {
                "uid": str(uuid.uuid4()),  # 用户 ID
            },
            "request": {
                "reqid": reqid,  # 请求 ID
                "show_utterances": False,  # 是否显示语句
                "sequence": 1  # 序列号
            },
            "audio": {
                "format": "wav",  # 音频格式
                "rate": 16000,  # 采样率
                "language": "zh-CN",  # 语言
                "bits": 16,  # 采样位数
                "channel": 1,  # 声道数
                "codec": "raw",  # 编码格式
            },
        }

    async def _send_request(self, audio_data: List[bytes], segment_size: int) -> Optional[str]:
        """
        将音频数据发送到 ASR 服务并获取识别结果。

        参数：
            audio_data (List[bytes]): 音频数据。
            segment_size (int): 分段大小。

        返回：
            Optional[str]: 识别结果文本，如果失败则返回 None。
        """
        try:
            auth_header = {'Authorization': 'Bearer; {}'.format(self.access_token)}  # 认证头
            async with websockets.connect(self.ws_url, additional_headers=auth_header) as websocket:
                # 准备请求数据
                request_params = self._construct_request(str(uuid.uuid4()))  # 构造请求负载
                payload_bytes = str.encode(json.dumps(request_params))  # 序列化为 JSON
                payload_bytes = gzip.compress(payload_bytes)  # 压缩负载数据
                full_client_request = self._generate_header()  # 生成协议头部
                full_client_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # 添加负载大小
                full_client_request.extend(payload_bytes)  # 添加负载数据

                # 发送头部和元数据
                await websocket.send(full_client_request)
                res = await websocket.recv()
                result = parse_response(res)
                if 'payload_msg' in result and result['payload_msg']['code'] != self.success_code:
                    logger.bind(tag=TAG).error(f"ASR 错误: {result}")
                    return None

                # 分段发送音频数据
                for seq, (chunk, last) in enumerate(self.slice_data(audio_data, segment_size), 1):
                    if last:
                        audio_only_request = self._generate_header(
                            message_type=CLIENT_AUDIO_ONLY_REQUEST,
                            message_type_specific_flags=NEG_SEQUENCE
                        )
                    else:
                        audio_only_request = self._generate_header(
                            message_type=CLIENT_AUDIO_ONLY_REQUEST
                        )
                    payload_bytes = gzip.compress(chunk)  # 压缩音频数据
                    audio_only_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # 添加负载大小
                    audio_only_request.extend(payload_bytes)  # 添加负载数据
                    await websocket.send(audio_only_request)  # 发送音频数据

                # 接收响应
                response = await websocket.recv()
                result = parse_response(response)  # 解析响应数据

                if 'payload_msg' in result and result['payload_msg']['code'] == self.success_code:
                    if len(result['payload_msg']['result']) > 0:
                        return result['payload_msg']['result'][0]["text"]  # 返回识别结果
                    return None
                else:
                    logger.bind(tag=TAG).error(f"ASR 错误: {result}")
                    return None

        except Exception as e:
            logger.bind(tag=TAG).error(f"ASR 请求失败: {e}", exc_info=True)
            return None

    @staticmethod
    def decode_opus(opus_data: List[bytes], session_id: str) -> List[bytes]:
        """
        解码 Opus 音频数据。

        参数：
            opus_data (List[bytes]): Opus 格式的音频数据。
            session_id (str): 会话 ID。

        返回：
            List[bytes]: 解码后的 PCM 数据。
        """
        decoder = opuslib_next.Decoder(16000, 1)  # 创建 Opus 解码器（16kHz, 单声道）
        pcm_data = []

        for opus_packet in opus_data:
            try:
                pcm_frame = decoder.decode(opus_packet, 960)  # 解码 Opus 数据（960 samples = 60ms）
                pcm_data.append(pcm_frame)
            except opuslib_next.OpusError as e:
                logger.bind(tag=TAG).error(f"Opus 解码错误: {e}", exc_info=True)

        return pcm_data

    @staticmethod
    def read_wav_info(data: io.BytesIO = None) -> (int, int, int, int, int):
        """
    读取 WAV 文件的元信息。

    功能：
        从 WAV 数据流中读取音频文件的元信息，包括声道数、采样宽度、采样率、帧数和数据长度。

    参数：
        data (io.BytesIO): WAV 数据流，以字节流的形式提供。如果为 None，则默认为空流。

    返回：
        tuple: 包含以下五个值的元组：
            - nchannels (int): 声道数（单声道为1，立体声为2）。
            - sampwidth (int): 采样宽度（以字节为单位，如16位采样为2字节）。
            - framerate (int): 采样率（每秒采样次数，如16000 Hz）。
            - nframes (int): 帧数（音频数据的总帧数）。
            - data_length (int): 音频数据的总长度（以字节为单位）。

    逻辑：
        1. 使用 `io.BytesIO` 将输入数据包装为文件对象。
        2. 使用 `wave.open` 打开 WAV 数据流并读取其元信息。
        3. 读取音频数据并计算其总长度。

    示例：
        >>> wav_data = io.BytesIO(b'...WAV文件数据...')
        >>> nchannels, sampwidth, framerate, nframes, data_length = ASRProvider.read_wav_info(wav_data)
        >>> print(f"声道数: {nchannels}, 采样宽度: {sampwidth}字节, 采样率: {framerate}Hz, 帧数: {nframes}, 数据长度: {data_length}字节")
        声道数: 1, 采样宽度: 2字节, 采样率: 16000Hz, 帧数: 1000, 数据长度: 2000字节

    注意：
        - 输入的 `data` 必须是有效的 WAV 格式数据流。
        - 如果输入为 None，则会返回默认值（声道数=0，采样宽度=0，采样率=0，帧数=0，数据长度=0）。
        """
        if data is None:
            return 0, 0, 0, 0, 0  # 如果输入为空，则返回默认值

        with io.BytesIO(data) as _f:  # 将输入数据包装为文件对象
            wave_fp = wave.open(_f, 'rb')  # 打开 WAV 数据流
            nchannels, sampwidth, framerate, nframes = wave_fp.getparams()[:4]  # 获取音频文件的基本参数
            wave_bytes = wave_fp.readframes(nframes)  # 读取音频数据
            data_length = len(wave_bytes)  # 计算音频数据的总长度
        return nchannels, sampwidth, framerate, nframes, data_length

    @staticmethod
    def slice_data(data: bytes, chunk_size: int) -> (list, bool):
        """
    将数据分段。

    功能：
        将输入的字节数据按照指定的分段大小进行分段处理，并返回一个生成器。
        每次生成一个数据段及其是否为最后一段的标志。

    参数：
        data (bytes): 要分段的字节数据。
        chunk_size (int): 每段的大小（以字节为单位）。

    返回：
        generator: 生成器，每次返回一个元组 (数据段, 是否为最后一段)。
            - 数据段 (bytes): 当前分段的字节数据。
            - 是否为最后一段 (bool): 如果是最后一段，则为 True，否则为 False。

    逻辑：
        1. 计算输入数据的总长度。
        2. 使用循环按照指定大小分段数据。
        3. 如果当前段是最后一段，则返回剩余的所有数据，并标记为最后一段。

    示例：
        >>> data = b"0123456789"
        >>> chunk_size = 3
        >>> for chunk, is_last in ASRProvider.slice_data(data, chunk_size):
        >>>     print(f"Chunk: {chunk}, Is Last: {is_last}")
        Chunk: b'012', Is Last: False
        Chunk: b'345', Is Last: False
        Chunk: b'678', Is Last: False
        Chunk: b'9', Is Last: True

    注意：
        - 如果 `chunk_size` 大于数据长度，则只返回一个包含所有数据的段，并标记为最后一段。
        - 如果 `chunk_size` 为 0 或负数，将引发异常。
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须为正整数")

        data_len = len(data)  # 计算数据总长度
        offset = 0  # 初始化偏移量

        # 循环分段数据
        while offset + chunk_size < data_len:
            yield data[offset: offset + chunk_size], False  # 返回当前段及其标志
            offset += chunk_size  # 更新偏移量

        # 返回最后一段数据
        yield data[offset: data_len], True

    async def speech_to_text(self, opus_data: List[bytes], session_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
    将 Opus 格式的语音数据转换为文本。

    功能：
        1. 解码 Opus 音频数据并将其转换为 PCM 格式。
        2. 将 PCM 数据封装为 WAV 格式。
        3. 将 WAV 数据分段并发送到 ASR（自动语音识别）服务。
        4. 获取并返回识别结果。

    参数：
        opus_data (List[bytes]): Opus 格式的音频数据，以字节列表的形式提供。
        session_id (str): 会话 ID，用于标识当前会话。

    返回：
        Tuple[Optional[str], Optional[str]]: 一个元组，包含以下两个值：
            - 识别结果文本（如果识别成功，否则为空字符串）。
            - 音频文件路径（如果保存了音频文件，否则为 None）。

    逻辑：
        1. 使用 `decode_opus` 方法将 Opus 数据解码为 PCM 数据。
        2. 将 PCM 数据封装为 WAV 格式，并计算分段大小。
        3. 使用 `_send_request` 方法将音频数据发送到 ASR 服务并获取识别结果。
        4. 如果识别成功，返回识别结果；否则返回空字符串。

    示例：
        >>> opus_data = [b'...Opus数据1...', b'...Opus数据2...']
        >>> session_id = "example_session_id"
        >>> text, audio_file_path = await asr_provider.speech_to_text(opus_data, session_id)
        >>> print(f"识别结果: {text}")
        识别结果: "这是识别的文本内容"

    注意：
        - 输入的 `opus_data` 必须是有效的 Opus 格式音频数据。
        - 如果 ASR 服务返回错误或识别失败，将返回空字符串。
        - 该方法是异步的，需要在异步环境中调用。
        """
        try:
            # 解码 Opus 数据并合并为 PCM 数据
            pcm_data = self.decode_opus(opus_data, session_id)  # 解码 Opus 数据
            combined_pcm_data = b''.join(pcm_data)  # 合并所有 PCM 数据片段

            # 将 PCM 数据封装为 WAV 格式
            wav_buffer = io.BytesIO()  # 创建一个内存中的字节流对象
            with wave.open(wav_buffer, "wb") as wav_file:  # 打开 WAV 文件（写入模式）
                wav_file.setnchannels(1)  # 设置声道数为 1（单声道）
                wav_file.setsampwidth(2)  # 设置采样宽度为 2 字节（16-bit）
                wav_file.setframerate(16000)  # 设置采样率为 16000 Hz
                wav_file.writeframes(combined_pcm_data)  # 写入 PCM 数据

            # 获取封装后的 WAV 数据
            wav_data = wav_buffer.getvalue()  # 从内存中获取 WAV 数据
            nchannels, sampwidth, framerate, nframes, wav_len = self.read_wav_info(wav_data)  # 读取 WAV 文件信息
            size_per_sec = nchannels * sampwidth * framerate  # 计算每秒数据大小
            segment_size = int(size_per_sec * self.seg_duration / 1000)  # 计算分段大小（基于分段时长）

            # 发送音频数据到 ASR 服务并获取识别结果
            start_time = time.time()  # 记录开始时间
            text = await self._send_request(wav_data, segment_size)  # 发送请求并获取识别结果
            if text:
                logger.bind(tag=TAG).debug(f"语音识别耗时: {time.time() - start_time:.3f}s | 结果: {text}")
                return text, None  # 返回识别结果
            return "", None  # 如果识别失败，返回空字符串

        except Exception as e:
            logger.bind(tag=TAG).error(f"语音识别失败: {e}", exc_info=True)  # 记录错误日志
            return "", None  # 返回空字符串