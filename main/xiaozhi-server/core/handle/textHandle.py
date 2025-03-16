from config.logger import setup_logging
import json
from core.handle.abortHandle import handleAbortMessage
from core.handle.helloHandle import handleHelloMessage
from core.handle.receiveAudioHandle import startToChat
from core.handle.iotHandle import handleIotDescriptors, handleIotStatus

TAG = __name__  # 定义日志标签，用于在日志中标识模块名称
logger = setup_logging()  # 初始化日志记录器


async def handleTextMessage(conn, message):
    """
    处理客户端发送的文本消息。

    功能：
        1. 解析文本消息内容，根据消息类型调用相应的处理函数。
        2. 支持的消息类型包括：
            - "hello"：处理客户端的连接初始化消息。
            - "abort"：处理客户端的中断请求。
            - "listen"：处理客户端的拾音模式和状态更新。
            - "iot"：处理物联网设备的描述和状态更新。

    参数：
        conn: 客户端连接对象，包含 WebSocket 连接和会话信息。
        message (str): 客户端发送的文本消息内容（JSON 格式）。

    逻辑：
        1. 尝试解析消息为 JSON 格式。
        2. 根据消息类型调用相应的处理函数。
        3. 如果消息格式无效，直接将原始消息发送回客户端。
    """
    logger.bind(tag=TAG).info(f"收到文本消息：{message}")  # 记录收到的文本消息
    try:
        # 尝试将消息解析为 JSON 格式
        msg_json = json.loads(message)
        
        # 如果消息是纯数字，直接转发给客户端
        if isinstance(msg_json, int):
            await conn.websocket.send(message)
            return

        # 根据消息类型进行处理
        if msg_json["type"] == "hello":
            # 处理客户端的连接初始化消息
            await handleHelloMessage(conn)
        elif msg_json["type"] == "abort":
            # 处理客户端的中断请求
            await handleAbortMessage(conn)
        elif msg_json["type"] == "listen":
            # 处理客户端的拾音模式和状态更新
            if "mode" in msg_json:
                # 更新客户端的拾音模式
                conn.client_listen_mode = msg_json["mode"]
                logger.bind(tag=TAG).debug(f"客户端拾音模式：{conn.client_listen_mode}")
            
            # 根据状态更新客户端的语音状态
            if msg_json["state"] == "start":
                conn.client_have_voice = True
                conn.client_voice_stop = False
            elif msg_json["state"] == "stop":
                conn.client_have_voice = True
                conn.client_voice_stop = True
            elif msg_json["state"] == "detect":
                conn.asr_server_receive = False
                conn.client_have_voice = False
                conn.asr_audio.clear()  # 清空音频缓冲区
                
                # 如果消息中包含文本，则触发聊天
                if "text" in msg_json:
                    await startToChat(conn, msg_json["text"])
        elif msg_json["type"] == "iot":
            # 处理物联网设备的描述和状态更新
            if "descriptors" in msg_json:
                await handleIotDescriptors(conn, msg_json["descriptors"])
            if "states" in msg_json:
                await handleIotStatus(conn, msg_json["states"])
    except json.JSONDecodeError:
        # 如果消息格式无效，直接将原始消息发送回客户端
        await conn.websocket.send(message)