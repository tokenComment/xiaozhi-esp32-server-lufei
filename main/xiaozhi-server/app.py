# 导入 asyncio 库，用于支持异步 I/O 操作和并发编程
import asyncio
# 导入 sys 模块，提供对 Python 解释器相关变量和函数的访问
import sys
# 导入 signal 模块，用于处理系统信号，如 Ctrl + C 等
import signal
# 从 config.settings 模块中导入 load_config 和 check_config_file 函数
from config.settings import load_config, check_config_file
# 从 core.websocket_server 模块中导入 WebSocketServer 类
from core.websocket_server import WebSocketServer
# 从 core.utils.util 模块中导入 check_ffmpeg_installed 函数
from core.utils.util import check_ffmpeg_installed

# 定义当前模块的标签，通常用于日志记录等场景
TAG = __name__

async def wait_for_exit():
    """Windows 和 Linux 兼容的退出监听"""
    # 获取当前的事件循环
    loop = asyncio.get_running_loop()
    # 创建一个异步事件对象，用于标记是否收到退出信号
    stop_event = asyncio.Event()

    if sys.platform == "win32":
        # Windows 系统：使用 sys.stdin.read() 监听 Ctrl + C 信号
        # 在单独的执行器中运行 sys.stdin.read()，避免阻塞事件循环
        await loop.run_in_executor(None, sys.stdin.read)
    else:
        # Linux/macOS 系统：使用 signal 模块监听 Ctrl + C 和 SIGTERM 信号
        def stop():
            # 当收到信号时，设置事件对象，表示程序需要退出
            stop_event.set()
        # 为 SIGINT 信号（Ctrl + C）添加信号处理函数
        loop.add_signal_handler(signal.SIGINT, stop)
        # 为 SIGTERM 信号（通常由 kill 命令发送）添加信号处理函数
        loop.add_signal_handler(signal.SIGTERM, stop)
        # 等待事件对象被设置，即等待退出信号
        await stop_event.wait()

async def main():
    # 检查配置文件是否存在
    check_config_file()
    # 检查 ffmpeg 是否安装
    check_ffmpeg_installed()
    # 加载配置文件内容
    config = load_config()

    # 实例化 WebSocketServer 类，传入配置信息
    ws_server = WebSocketServer(config)
    # 创建一个异步任务，启动 WebSocket 服务器
    ws_task = asyncio.create_task(ws_server.start())

    try:
        # 等待退出信号，即调用 wait_for_exit 函数
        await wait_for_exit()
    except asyncio.CancelledError:
        # 若任务被取消，打印提示信息
        print("任务被取消，清理资源中...")
    finally:
        # 取消 WebSocket 服务器任务
        ws_task.cancel()
        try:
            # 等待任务被取消完成
            await ws_task
        except asyncio.CancelledError:
            pass
        # 打印服务器关闭和程序退出的提示信息
        print("服务器已关闭，程序退出。")

if __name__ == "__main__":
    try:
        # 运行异步主函数
        asyncio.run(main())
    except KeyboardInterrupt:
        # 若手动中断程序（如按下 Ctrl + C），打印提示信息
        print("手动中断，程序终止。")