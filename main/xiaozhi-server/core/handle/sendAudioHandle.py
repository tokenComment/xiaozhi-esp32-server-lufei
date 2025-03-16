from config.logger import setup_logging
import json
import asyncio
import time
from core.utils.util import remove_punctuation_and_length, get_string_no_punctuation_or_emoji

TAG = __name__
logger = setup_logging()

async def sendAudioMessage(conn, audios, text, text_index=0):
    # 发送句子开始消息
    if text_index == conn.tts_first_text_index:
        logger.bind(tag=TAG).info(f"发送第一段语音: {text}")
    await send_tts_message(conn, "sentence_start", text)

    # 流控参数优化
    original_frame_duration = 60  # 原始帧时长（毫秒）
    adjusted_frame_duration = int(original_frame_duration * 0.8)  # 缩短20%
    total_frames = len(audios)  # 获取总帧数
    compensation = total_frames * (original_frame_duration - adjusted_frame_duration) / 1000  # 补偿时间（秒）

    start_time = time.perf_counter()
    play_position = 0  # 已播放时长（毫秒）

    for opus_packet in audios:
        if conn.client_abort:
            return

        # 计算带加速因子的预期时间
        expected_time = start_time + (play_position / 1000)
        current_time = time.perf_counter()

        # 流控等待（使用加速后的帧时长）
        delay = expected_time - current_time
        if delay > 0:
            await asyncio.sleep(delay)

        await conn.websocket.send(opus_packet)
        play_position += adjusted_frame_duration  # 使用调整后的帧时长

    # 补偿因加速损失的时长
    if compensation > 0:
        await asyncio.sleep(compensation)

    await send_tts_message(conn, "sentence_end", text)

    # 发送结束消息（如果是最后一个文本）
    if conn.llm_finish_task and text_index == conn.tts_last_text_index:
        await send_tts_message(conn, 'stop', None)
        if conn.close_after_chat:
            await conn.close()

async def send_tts_message(conn, state, text=None):
    """
    发送 TTS（文本到语音）状态消息。

    功能：
        1. 构建并发送 TTS 状态消息。
        2. 如果状态为 "stop"，清除当前的语音播放状态。

    参数：
        conn: 客户端连接对象，包含 WebSocket 连接和会话信息。
        state (str): TTS 的状态，如 "start"、"stop" 等。
        text (str, optional): 要发送的文本内容。如果为 None，则不包含文本字段。

    逻辑：
        1. 构建 TTS 消息的基本结构，包含类型、状态和会话 ID。
        2. 如果提供了文本内容，则将文本字段添加到消息中。
        3. 将消息通过 WebSocket 发送给客户端。
        4. 如果状态为 "stop"，调用 `clearSpeakStatus` 方法清除语音播放状态。
    """
    # 构建 TTS 消息的基本结构
    message = {
        "type": "tts",  # 消息类型为 TTS
        "state": state,  # TTS 的状态
        "session_id": conn.session_id  # 当前会话 ID
    }

    # 如果提供了文本内容，则添加到消息中
    if text is not None:
        message["text"] = text

    # 将消息通过 WebSocket 发送给客户端
    await conn.websocket.send(json.dumps(message))

    # 如果状态为 "stop"，清除语音播放状态
    if state == "stop":
        conn.clearSpeakStatus()

async def send_stt_message(conn, text):
    """
    发送语音识别（STT）状态消息。

    功能：
        1. 将用户输入的文本（语音识别结果）发送给客户端。
        2. 发送一个带有表情符号的 LLM（语言模型）状态消息。
        3. 触发 TTS（文本到语音）消息的发送。

    参数：
        conn: 客户端连接对象，包含 WebSocket 连接和会话信息。
        text (str): 语音识别结果文本。

    逻辑：
        1. 调用 `get_string_no_punctuation_or_emoji` 函数，移除文本中的标点符号和表情符号。
        2. 将处理后的文本封装为 STT 消息并发送。
        3. 发送一个带有表情符号的 LLM 消息。
        4. 调用 `send_tts_message` 函数，发送 TTS 消息。
    """
    # 移除文本中的标点符号和表情符号
    stt_text = get_string_no_punctuation_or_emoji(text)

    # 发送 STT 状态消息
    await conn.websocket.send(json.dumps({
        "type": "stt",  # 消息类型为 STT
        "text": stt_text,  # 语音识别结果
        "session_id": conn.session_id  # 当前会话 ID
    }))

    # 发送 LLM 状态消息（带有表情符号）
    await conn.websocket.send(
        json.dumps({
            "type": "llm",  # 消息类型为 LLM
            "text": "😊",  # 表情符号文本
            "emotion": "happy",  # 情感状态
            "session_id": conn.session_id  # 当前会话 ID
        })
    )

    # 触发 TTS 消息的发送，状态为 "start"
    await send_tts_message(conn, "start")
