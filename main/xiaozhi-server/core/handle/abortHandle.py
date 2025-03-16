import json
import queue
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# 定义一个异步函数，用于处理终止消息
async def handleAbortMessage(conn):
    """
    处理接收到的终止消息。

    :param conn: 表示与客户端的连接对象，该对象应包含以下属性和方法：
                 - client_abort: 用于标记客户端是否处于打断状态的布尔型属性。
                 - websocket: 用于与客户端进行通信的 WebSocket 对象，具备 send 方法。
                 - session_id: 表示当前会话的唯一标识符的属性。
                 - clearSpeakStatus: 用于清除客户端说话状态的方法。
    """
    # 记录日志，表明已经接收到终止消息
    logger.bind(tag=TAG).info("Abort message received")

    # 设置连接对象的 client_abort 属性为 True，
    # 此操作会使系统自动打断大语言模型（LLM）和文本转语音（TTS）任务
    conn.client_abort = True

    # 构建一个包含终止 TTS 任务信息的字典，
    # 该字典包含消息类型、状态和会话 ID
    message = {
        "type": "tts",
        "state": "stop",
        "session_id": conn.session_id
    }

    # 将消息字典转换为 JSON 字符串，并通过 WebSocket 发送给客户端，
    # 以此来打断客户端的说话状态
    await conn.websocket.send(json.dumps(message))

    # 调用连接对象的 clearSpeakStatus 方法，清除客户端的说话状态
    conn.clearSpeakStatus()

    # 记录日志，表明终止消息处理完毕
    logger.bind(tag=TAG).info("Abort message received-end")
