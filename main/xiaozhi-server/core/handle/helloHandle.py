import json
from config.logger import setup_logging

# 初始化日志记录器，用于记录程序运行过程中的日志信息
logger = setup_logging()

# 定义一个异步函数 handleHelloMessage，用于处理客户端发送的“Hello”消息
async def handleHelloMessage(conn):
    """
    处理客户端的“Hello”消息。
    当客户端发送“Hello”消息时，通过 WebSocket 连接向客户端发送欢迎消息。

    参数:
        conn: 客户端连接对象，包含 WebSocket 连接和欢迎消息等信息。
            - conn.websocket: WebSocket 连接对象，用于与客户端通信。
            - conn.welcome_msg: 欢迎消息内容，以字典形式存储。

    功能:
        1. 将欢迎消息 conn.welcome_msg 转换为 JSON 格式。
        2. 通过 WebSocket 连接将 JSON 格式的欢迎消息发送给客户端。

    示例:
        假设 conn.welcome_msg = {"message": "Welcome to the server!"}
        则发送给客户端的 JSON 数据为 '{"message": "Welcome to the server!"}'
    """
    # 使用 json.dumps 将 conn.welcome_msg 转换为 JSON 格式的字符串
    # json.dumps 是将 Python 对象（如字典）转换为 JSON 格式的字符串
    await conn.websocket.send(json.dumps(conn.welcome_msg))
    # 通过 conn.websocket.send 方法将 JSON 格式的欢迎消息发送给客户端
    # 这里使用了异步操作，await 确保在发送消息完成后才继续执行后续代码
