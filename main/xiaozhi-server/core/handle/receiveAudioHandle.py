from config.logger import setup_logging
import time
from core.utils.util import remove_punctuation_and_length
from core.handle.sendAudioHandle import send_stt_message
from core.handle.intentHandler import handle_user_intent

TAG = __name__  # 定义日志标签，用于在日志中标识模块名称
logger = setup_logging()  # 初始化日志记录器


async def handleAudioMessage(conn, audio):
    """
    处理音频消息。

    参数:
        conn: 客户端连接对象，包含音频处理、意图识别、聊天等功能。
        audio: 接收到的音频数据。

    功能:
        1. 检查是否处于前期数据处理阶段，如果是则暂停接收音频。
        2. 判断音频中是否有声音（通过 VAD 或客户端状态）。
        3. 如果没有声音，检查是否需要关闭连接。
        4. 如果有声音，进行语音识别并处理识别结果。
    """
    if not conn.asr_server_receive:
        # 如果 ASR 服务器尚未准备好，暂停接收音频
        logger.bind(tag=TAG).debug(f"前期数据处理中，暂停接收")
        return

    # 判断音频中是否有声音
    if conn.client_listen_mode == "auto":
        # 自动模式下，使用 VAD（Voice Activity Detection）检测声音
        have_voice = conn.vad.is_vad(conn, audio)
    else:
        # 手动模式下，直接使用客户端的状态
        have_voice = conn.client_have_voice

    # 如果本次没有声音，且之前也没有声音，则丢弃音频
    if have_voice == False and conn.client_have_voice == False:
        await no_voice_close_connect(conn)  # 检查是否需要关闭连接
        conn.asr_audio.append(audio)  # 保留音频数据
        conn.asr_audio = conn.asr_audio[-5:]  # 保留最新的5帧音频，解决 ASR 句首丢字问题
        return

    # 重置无声音的时间计数
    conn.client_no_voice_last_time = 0.0
    conn.asr_audio.append(audio)  # 将音频数据添加到缓冲区

    # 如果检测到声音且之前已标记为停止
    if conn.client_voice_stop:
        conn.client_abort = False  # 重置中断标志
        conn.asr_server_receive = False  # 停止接收音频

        # 如果音频太短，无法识别
        if len(conn.asr_audio) < 10:
            conn.asr_server_receive = True  # 重新开始接收音频
        else:
            # 进行语音识别
            text, file_path = await conn.asr.speech_to_text(conn.asr_audio, conn.session_id)
            logger.bind(tag=TAG).info(f"识别文本: {text}")

            # 去除标点并计算文本长度
            text_len, _ = remove_punctuation_and_length(text)
            if text_len > 0:
                # 如果识别到有效文本，开始聊天
                await startToChat(conn, text)
            else:
                conn.asr_server_receive = True  # 重新开始接收音频

        # 清空音频缓冲区并重置 VAD 状态
        conn.asr_audio.clear()
        conn.reset_vad_states()


async def startToChat(conn, text):
    """
    开始聊天流程。

    参数:
        conn: 客户端连接对象。
        text (str): 用户输入的文本（语音识别结果）。

    功能:
        1. 首先进行意图分析，判断是否需要处理特定意图。
        2. 如果意图未被处理，则进入常规聊天流程。
    """
    # 首先进行意图分析
    intent_handled = await handle_user_intent(conn, text)
    
    if intent_handled:
        # 如果意图已被处理，不再进行聊天
        conn.asr_server_receive = True
        return
    
    # 意图未被处理，继续常规聊天流程
    await send_stt_message(conn, text)  # 发送语音识别结果
    if conn.use_function_call_mode:
        # 使用支持 function calling 的聊天方法
        conn.executor.submit(conn.chat_with_function_calling, text)
    else:
        conn.executor.submit(conn.chat, text)  # 使用普通聊天方法


async def no_voice_close_connect(conn):
    """
    检查是否因长时间无声音而关闭连接。

    参数:
        conn: 客户端连接对象。

    功能:
        1. 如果是第一次检测到无声音，记录当前时间。
        2. 如果无声音的时间超过配置的阈值，则关闭连接。
    """
    if conn.client_no_voice_last_time == 0.0:
        # 如果是第一次检测到无声音，记录当前时间
        conn.client_no_voice_last_time = time.time() * 1000
    else:
        # 计算无声音的时间
        no_voice_time = time.time() * 1000 - conn.client_no_voice_last_time
        close_connection_no_voice_time = conn.config.get("close_connection_no_voice_time", 120)  # 配置的无声音关闭时间阈值

        # 如果无声音时间超过阈值
        if not conn.close_after_chat and no_voice_time > 1000 * close_connection_no_voice_time:
            conn.close_after_chat = True  # 标记为关闭连接
            conn.client_abort = False  # 重置中断标志
            conn.asr_server_receive = False  # 停止接收音频

            # 发送结束对话的提示
            prompt = "请你以‘时间过得真快’为开头，用富有感情、依依不舍的话来结束这场对话吧。"
            await startToChat(conn, prompt)