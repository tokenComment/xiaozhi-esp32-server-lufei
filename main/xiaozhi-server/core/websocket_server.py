# 导入asyncio模块，用于异步编程，处理异步任务和事件循环
import asyncio
# 导入websockets模块，用于创建和处理WebSocket连接
import websockets
# 从配置日志模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging
# 从核心连接模块中导入连接处理类，用于处理客户端的连接和交互
from core.connection import ConnectionHandler
# 从核心音乐处理模块中导入音乐处理类，用于处理音乐相关的操作
from core.handle.musicHandler import MusicHandler
# 从核心工具模块中导入获取本地IP地址的函数，用于显示服务器的本地IP
from core.utils.util import get_local_ip
# 从核心工具模块中导入语音活动检测、自动语音识别、大语言模型、文本转语音、记忆管理和意图处理等相关功能模块
from core.utils import asr, vad, llm, tts, memory, intent

# 获取当前模块的名称作为标签，用于在日志记录中标识来源
TAG = __name__


class WebSocketServer:
    def __init__(self, config: dict):
        """
        初始化WebSocket服务器实例。

        :param config: 配置字典，包含服务器的各种配置信息，如模块选择、端口号等。
        """
        self.config = config
        # 调用设置日志的函数，获取日志记录器
        self.logger = setup_logging()
        # 创建各种处理模块的实例，包括语音活动检测、自动语音识别、大语言模型、文本转语音、音乐处理、记忆管理和意图处理
        self._vad, self._asr, self._llm, self._tts, self._music, self._hass, self._memory, self.intent = self._create_processing_instances()
        # 用于存储当前活跃的连接处理实例，方便管理和跟踪所有连接
        self.active_connections = set()  

    def _create_processing_instances(self):
        """
        创建处理模块的实例，根据配置文件中的选择来初始化各个模块。

        :return: 包含各个处理模块实例的元组。
        """
        # 获取配置文件中选择的记忆模块名称，默认使用 "nomem"
        memory_cls_name = self.config["selected_module"].get("Memory", "nomem")
        # 检查配置文件中是否存在记忆模块的配置信息
        has_memory_cfg = self.config.get("Memory") and memory_cls_name in self.config["Memory"]
        # 如果存在记忆模块的配置信息，则获取该模块的具体配置，否则使用空字典
        memory_cfg = self.config["Memory"][memory_cls_name] if has_memory_cfg else {}

        return (
            # 创建语音活动检测（VAD）模块的实例，根据配置文件中选择的VAD模块和其具体配置进行初始化
            vad.create_instance(
                self.config["selected_module"]["VAD"],
                self.config["VAD"][self.config["selected_module"]["VAD"]]
            ),
            # 创建自动语音识别（ASR）模块的实例，根据配置文件中选择的ASR模块和其具体配置进行初始化
            asr.create_instance(
                # 如果配置文件中ASR模块的配置没有 "type" 字段，则使用选择的模块名称，否则使用 "type" 字段的值
                self.config["selected_module"]["ASR"]
                if not 'type' in self.config["ASR"][self.config["selected_module"]["ASR"]]
                else
                self.config["ASR"][self.config["selected_module"]["ASR"]]["type"],
                self.config["ASR"][self.config["selected_module"]["ASR"]],
                self.config["delete_audio"]
            ),
            # 创建大语言模型（LLM）模块的实例，根据配置文件中选择的LLM模块和其具体配置进行初始化
            llm.create_instance(
                # 如果配置文件中LLM模块的配置没有 "type" 字段，则使用选择的模块名称，否则使用 "type" 字段的值
                self.config["selected_module"]["LLM"]
                if not 'type' in self.config["LLM"][self.config["selected_module"]["LLM"]]
                else
                self.config["LLM"][self.config["selected_module"]["LLM"]]['type'],
                self.config["LLM"][self.config["selected_module"]["LLM"]],
            ),
            # 创建文本转语音（TTS）模块的实例，根据配置文件中选择的TTS模块和其具体配置进行初始化
            tts.create_instance(
                # 如果配置文件中TTS模块的配置没有 "type" 字段，则使用选择的模块名称，否则使用 "type" 字段的值
                self.config["selected_module"]["TTS"]
                if not 'type' in self.config["TTS"][self.config["selected_module"]["TTS"]]
                else
                self.config["TTS"][self.config["selected_module"]["TTS"]]["type"],
                self.config["TTS"][self.config["selected_module"]["TTS"]],
                self.config["delete_audio"]
            ),
            # 创建音乐处理模块的实例，传入配置文件
            MusicHandler(self.config),
            # 创建记忆管理模块的实例，根据选择的记忆模块名称和其具体配置进行初始化
            memory.create_instance(memory_cls_name, memory_cfg),
            # 创建意图处理模块的实例，根据配置文件中选择的意图处理模块和其具体配置进行初始化
            intent.create_instance(
                # 如果配置文件中意图处理模块的配置没有 "type" 字段，则使用选择的模块名称，否则使用 "type" 字段的值
                self.config["selected_module"]["Intent"]
                if not 'type' in self.config["Intent"][self.config["selected_module"]["Intent"]]
                else
                self.config["Intent"][self.config["selected_module"]["Intent"]]["type"],
                self.config["Intent"][self.config["selected_module"]["Intent"]]
            ),
        )

    async def start(self):
        """
        启动WebSocket服务器，监听指定的主机和端口，处理客户端连接。
        """
        # 获取服务器的配置信息
        server_config = self.config["server"]
        # 获取服务器监听的主机地址
        host = server_config["ip"]
        # 获取服务器监听的端口号
        port = server_config["port"]
        # 获取配置文件中选择的模块信息
        selected_module = self.config.get("selected_module")
        # 记录选择的模块信息到日志中
        self.logger.bind(tag=TAG).info(f"selected_module values: {', '.join(selected_module.values())}")
        # 记录服务器运行的地址到日志中，显示本地IP和端口号
        self.logger.bind(tag=TAG).info("Server is running at ws://{}:{}", get_local_ip(), port)
        # 提示用户该地址是WebSocket协议地址，不要用浏览器访问
        self.logger.bind(tag=TAG).info("=======上面的地址是websocket协议地址，请勿用浏览器访问=======")
        # 使用websockets.serve方法启动服务器，传入处理连接的方法和监听的主机、端口
        async with websockets.serve(
                self._handle_connection,
                host,
                port
        ):
            # 等待异步任务完成，保持服务器一直运行
            await asyncio.Future()

    async def _handle_connection(self, websocket):
        """
        处理新的WebSocket连接，为每个连接创建一个独立的连接处理实例。

        :param websocket: 新连接的WebSocket对象。
        """
        # 创建一个连接处理实例，传入配置信息和各个处理模块的实例
        handler = ConnectionHandler(self.config, self._vad, self._asr, self._llm, self._tts, self._music, self._hass, self._memory, self.intent)
        # 将新的连接处理实例添加到活跃连接集合中
        self.active_connections.add(handler)
        try:
            # 调用连接处理实例的handle_connection方法处理该连接
            await handler.handle_connection(websocket)
        finally:
            # 无论连接处理是否成功，都将该连接处理实例从活跃连接集合中移除
            self.active_connections.discard(handler)