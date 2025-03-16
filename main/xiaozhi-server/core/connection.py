# 导入os模块，用于与操作系统进行交互，如文件操作、环境变量等
import os
# 导入json模块，用于处理JSON数据，如解析和生成JSON字符串
import json
# 导入uuid模块，用于生成唯一标识符，如会话ID
import uuid
# 导入time模块，用于处理时间相关操作，如获取当前时间、格式化时间等
import time
# 导入queue模块，用于线程间的数据传递，如存储TTS任务和音频播放任务
import queue
# 导入asyncio模块，用于异步编程，处理WebSocket连接和异步任务
import asyncio
# 导入traceback模块，用于获取异常的堆栈跟踪信息，便于调试和错误处理
import traceback
# 从自定义配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging
# 导入threading模块，用于多线程编程，创建和管理线程
import threading
# 导入websockets模块，用于处理WebSocket连接，实现客户端和服务器之间的双向通信
import websockets
# 从typing模块导入Dict和Any，用于类型提示，增强代码的可读性和可维护性
from typing import Dict, Any
# 从自定义模块中导入Message和Dialogue类，用于处理对话消息和对话记录
from core.utils.dialogue import Message, Dialogue
# 从自定义模块中导入处理文本消息的函数
from core.handle.textHandle import handleTextMessage
# 从自定义模块中导入字符串处理和JSON提取的工具函数
from core.utils.util import get_string_no_punctuation_or_emoji, extract_json_from_string
# 从concurrent.futures模块导入ThreadPoolExecutor和TimeoutError，用于创建线程池和处理超时错误
from concurrent.futures import ThreadPoolExecutor, TimeoutError
# 从自定义模块中导入发送音频消息的函数
from core.handle.sendAudioHandle import sendAudioMessage
# 从自定义模块中导入处理音频消息的函数
from core.handle.receiveAudioHandle import handleAudioMessage
from core.handle.functionHandler import FunctionHandler
from plugins_func.register import Action
# 从自定义配置模块中导入私有配置类
from config.private_config import PrivateConfig
# 从自定义认证模块中导入认证中间件类和认证异常类
from core.auth import AuthMiddleware, AuthenticationError
# 从自定义工具模块中导入认证码生成器类
from core.utils.auth_code_gen import AuthCodeGenerator
import plugins_func.loadplugins  

# 获取当前模块的名称作为标签，用于在日志记录中标识来源
TAG = __name__



# 自定义异常类，用于TTS（文本到语音）相关的错误
class TTSException(RuntimeError):
    pass

# 连接处理类，负责管理与客户端的WebSocket连接，处理消息路由、语音识别、文本生成、语音合成等任务
class ConnectionHandler:
    def __init__(self, config: Dict[str, Any], _vad, _asr, _llm, _tts, _music, _hass, _memory, _intent):
        # 初始化配置
        self.config = config
        # 设置日志记录器
        self.logger = setup_logging()
        # 初始化认证中间件
        self.auth = AuthMiddleware(config)

        # WebSocket连接相关
        self.websocket = None
        self.headers = None
        self.session_id = None
        self.prompt = None
        self.welcome_msg = None

        # 客户端状态相关
        self.client_abort = False  # 客户端是否中断
        self.client_listen_mode = "auto"  # 客户端监听模式

        # 线程任务相关
        self.loop = asyncio.get_event_loop()  # 事件循环
        self.stop_event = threading.Event()  # 停止事件
        self.tts_queue = queue.Queue()  # TTS任务队列
        self.audio_play_queue = queue.Queue()  # 音频播放队列
        self.executor = ThreadPoolExecutor(max_workers=10)  # 线程池执行器

        # 依赖的组件
        self.vad = _vad  # 语音活动检测
        self.asr = _asr  # 自动语音识别
        self.llm = _llm  # 大语言模型
        self.tts = _tts  # 文本到语音合成
        self.memory = _memory  # 记忆模块
        self.intent = _intent  # 意图处理模块

        # VAD相关变量
        self.client_audio_buffer = bytes()  # 客户端音频缓冲区
        self.client_have_voice = False  # 客户端是否有语音
        self.client_have_voice_last_time = 0.0  # 上次检测到语音的时间
        self.client_no_voice_last_time = 0.0  # 上次检测到无语音的时间
        self.client_voice_stop = False  # 语音是否停止

        # ASR相关变量
        self.asr_audio = []  # ASR音频数据
        self.asr_server_receive = True  # ASR服务器是否接收数据

        # LLM相关变量
        self.llm_finish_task = False  # LLM任务是否完成
        self.dialogue = Dialogue()  # 对话记录

        # TTS相关变量
        self.tts_first_text_index = -1  # 第一个TTS文本的索引
        self.tts_last_text_index = -1  # 最后一个TTS文本的索引

        # IoT相关变量
        self.iot_descriptors = {}  # IoT设备描述符

        # 退出命令相关
        self.cmd_exit = self.config["CMD_exit"]  # 退出命令
        self.max_cmd_length = 0  # 最长命令长度
        for cmd in self.cmd_exit:
            if len(cmd) > self.max_cmd_length:
                self.max_cmd_length = len(cmd)

        # 私有配置相关
        self.private_config = None
        self.auth_code_gen = AuthCodeGenerator.get_instance()  # 认证码生成器
        self.is_device_verified = False  # 设备是否已验证
        self.music_handler = _music  # 音乐处理模块
        self.hass_handler = _hass  # 家庭自动化处理模块
        self.close_after_chat = False  # 是否在聊天结束后关闭连接
        self.use_function_call_mode = False  # 是否使用函数调用模式
        if self.config["selected_module"]["Intent"] == 'function_call':
            self.use_function_call_mode = True
        self.func_handler = FunctionHandler(self.config)

    # 处理WebSocket连接
    async def handle_connection(self, ws):
        try:
            # 获取并验证headers
            self.headers = dict(ws.request.headers)
            # 获取客户端IP地址
            client_ip = ws.remote_address[0]
            self.logger.bind(tag=TAG).info(f"{client_ip} conn - Headers: {self.headers}")

            # 进行认证
            await self.auth.authenticate(self.headers)

            # 获取设备ID并初始化记忆模块
            device_id = self.headers.get("device-id", None)
            self.memory.init_memory(device_id, self.llm)
            self.intent.set_llm(self.llm)

            # 如果启用了私有配置且设备ID存在，则加载私有配置
            bUsePrivateConfig = self.config.get("use_private_config", False)
            self.logger.bind(tag=TAG).info(f"bUsePrivateConfig: {bUsePrivateConfig}, device_id: {device_id}")
            if bUsePrivateConfig and device_id:
                try:
                    self.private_config = PrivateConfig(device_id, self.config, self.auth_code_gen)
                    await self.private_config.load_or_create()
                    # 判断设备是否已经绑定
                    owner = self.private_config.get_owner()
                    self.is_device_verified = owner is not None

                    if self.is_device_verified:
                        await self.private_config.update_last_chat_time()

                    # 创建私有实例
                    llm, tts = self.private_config.create_private_instances()
                    if all([llm, tts]):
                        self.llm = llm
                        self.tts = tts
                        self.logger.bind(tag=TAG).info(f"Loaded private config and instances for device {device_id}")
                    else:
                        self.logger.bind(tag=TAG).error(f"Failed to create instances for device {device_id}")
                        self.private_config = None
                except Exception as e:
                    self.logger.bind(tag=TAG).error(f"Error initializing private config: {e}")
                    self.private_config = None
                    raise

            # 认证通过，继续处理
            self.websocket = ws
            self.session_id = str(uuid.uuid4())

            # 发送欢迎消息
            self.welcome_msg = self.config["xiaozhi"]
            self.welcome_msg["session_id"] = self.session_id
            await self.websocket.send(json.dumps(self.welcome_msg))

            # 初始化组件
            await self.loop.run_in_executor(None, self._initialize_components)

            # 启动TTS处理线程
            tts_priority = threading.Thread(target=self._tts_priority_thread, daemon=True)
            tts_priority.start()

            # 启动音频播放处理线程
            audio_play_priority = threading.Thread(target=self._audio_play_priority_thread, daemon=True)
            audio_play_priority.start()

            try:
                # 处理来自客户端的消息
                async for message in self.websocket:
                    await self._route_message(message)
            except websockets.exceptions.ConnectionClosed:
                self.logger.bind(tag=TAG).info("客户端断开连接")
                await self.close()

        except AuthenticationError as e:
            self.logger.bind(tag=TAG).error(f"Authentication failed: {str(e)}")
            await ws.close()
            return
        except Exception as e:
            stack_trace = traceback.format_exc()
            self.logger.bind(tag=TAG).error(f"Connection error: {str(e)}-{stack_trace}")
            await ws.close()
            return
        finally:
            # 保存对话记忆
            await self.memory.save_memory(self.dialogue.dialogue)

    # 消息路由方法，根据消息类型调用不同的处理函数
    async def _route_message(self, message):
        """消息路由"""
        if isinstance(message, str):
            await handleTextMessage(self, message)
        elif isinstance(message, bytes):
            await handleAudioMessage(self, message)

    # 初始化组件，设置系统提示词
    def _initialize_components(self):
        self.prompt = self.config["prompt"]
        if self.private_config:
            self.prompt = self.private_config.private_config.get("prompt", self.prompt)
        
        self.dialogue.put(Message(role="system", content=self.prompt))

    def change_system_prompt(self, prompt):
        self.prompt = prompt
        # 找到原来的role==system，替换原来的系统提示
        for m in self.dialogue.dialogue:
            if m.role == "system":
                m.content = prompt

    # 检查设备绑定状态并广播认证码
    async def _check_and_broadcast_auth_code(self):
        """检查设备绑定状态并广播认证码"""
        if not self.private_config.get_owner():
            auth_code = self.private_config.get_auth_code()
            if auth_code:
                # 发送验证码语音提示
                text = f"请在后台输入验证码：{' '.join(auth_code)}"
                self.recode_first_last_text(text)
                future = self.executor.submit(self.speak_and_play, text)
                self.tts_queue.put(future)
            return False
        return True

    # 判断是否需要认证
    def isNeedAuth(self):
        bUsePrivateConfig = self.config.get("use_private_config", False)
        if not bUsePrivateConfig:
            # 如果不使用私有配置，就不需要验证
            return False
        return not self.is_device_verified

    # 处理用户输入的文本消息
    def chat(self, query):
        if self.isNeedAuth():
            self.llm_finish_task = True
            future = asyncio.run_coroutine_threadsafe(self._check_and_broadcast_auth_code(), self.loop)
            future.result()
            return True

        # 将用户输入添加到对话记录中
        self.dialogue.put(Message(role="user", content=query))

        response_message = []
        processed_chars = 0  # 跟踪已处理的字符位置
        try:
            start_time = time.time()
            # 使用带记忆的对话
            future = asyncio.run_coroutine_threadsafe(self.memory.query_memory(query), self.loop)
            memory_str = future.result()

            self.logger.bind(tag=TAG).debug(f"记忆内容: {memory_str}")
            llm_responses = self.llm.response(
                self.session_id,
                self.dialogue.get_llm_dialogue_with_memory(memory_str)
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"LLM 处理出错 {query}: {e}")
            return None

        self.llm_finish_task = False
        text_index = 0
        for content in llm_responses:
            response_message.append(content)
            if self.client_abort:
                break

            end_time = time.time()
            self.logger.bind(tag=TAG).debug(f"大模型返回时间: {end_time - start_time} 秒, 生成token={content}")

            # 合并当前全部文本并处理未分割部分
            full_text = "".join(response_message)
            current_text = full_text[processed_chars:]  # 从未处理的位置开始

            # 查找最后一个有效标点
            punctuations = ("。", "？", "！", "；", "：")
            last_punct_pos = -1
            for punct in punctuations:
                pos = current_text.rfind(punct)
                if pos > last_punct_pos:
                    last_punct_pos = pos

            # 找到分割点则处理
            if last_punct_pos != -1:
                segment_text_raw = current_text[:last_punct_pos + 1]
                segment_text = get_string_no_punctuation_or_emoji(segment_text_raw)
                if segment_text:
                    # 强制设置空字符，测试TTS出错返回语音的健壮性
                    # if text_index % 2 == 0:
                    #     segment_text = " "
                    text_index += 1
                    self.recode_first_last_text(segment_text, text_index)
                    future = self.executor.submit(self.speak_and_play, segment_text, text_index)
                    self.tts_queue.put(future)
                    processed_chars += len(segment_text_raw)  # 更新已处理字符位置

        # 处理最后剩余的文本
        full_text = "".join(response_message)
        remaining_text = full_text[processed_chars:]
        if remaining_text:
            segment_text = get_string_no_punctuation_or_emoji(remaining_text)
            if segment_text:
                text_index += 1
                self.recode_first_last_text(segment_text, text_index)
                future = self.executor.submit(self.speak_and_play, segment_text, text_index)
                self.tts_queue.put(future)

        self.llm_finish_task = True
        self.dialogue.put(Message(role="assistant", content="".join(response_message)))
        self.logger.bind(tag=TAG).debug(json.dumps(self.dialogue.get_llm_dialogue(), indent=4, ensure_ascii=False))
        return True

    # 使用函数调用模式处理用户输入的文本消息
    def chat_with_function_calling(self, query, tool_call = False):
        self.logger.bind(tag=TAG).debug(f"Chat with function calling start: {query}")
        """Chat with function calling for intent detection using streaming"""
        if self.isNeedAuth():
            self.llm_finish_task = True
            future = asyncio.run_coroutine_threadsafe(self._check_and_broadcast_auth_code(), self.loop)
            future.result()
            return True

        if not tool_call:
            # 将用户输入添加到对话记录中
            self.dialogue.put(Message(role="user", content=query))

        # 定义意图函数
        functions = self.func_handler.get_functions()

        response_message = []
        processed_chars = 0  # 跟踪已处理的字符位置
   
        try:
            start_time = time.time()

            # 使用带记忆的对话
            future = asyncio.run_coroutine_threadsafe(self.memory.query_memory(query), self.loop)
            memory_str = future.result()

            # 使用支持functions的streaming接口
            llm_responses = self.llm.response_with_functions(
                self.session_id,
                self.dialogue.get_llm_dialogue_with_memory(memory_str),
                functions=functions
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"LLM 处理出错 {query}: {e}")
            return None

        self.llm_finish_task = False
        text_index = 0

        # 处理流式响应
        tool_call_flag = False
        function_name = None
        function_id = None
        function_arguments = ""
        content_arguments = ""
        for response in llm_responses:
            content, tools_call = response
            if content is not None and len(content)>0:
                if len(response_message)<=0 and (content=="```" or "<tool_call>" in content):
                    tool_call_flag = True

            if tools_call is not None:
                tool_call_flag = True
                if tools_call[0].id is not None:
                    function_id = tools_call[0].id
                if tools_call[0].function.name is not None:
                    function_name = tools_call[0].function.name
                if tools_call[0].function.arguments is not None:
                    function_arguments += tools_call[0].function.arguments

            if content is not None and len(content) > 0:
                if tool_call_flag:
                    content_arguments+=content
                else:
                    response_message.append(content)

                    if self.client_abort:
                        break

                    end_time = time.time()
                    self.logger.bind(tag=TAG).debug(f"大模型返回时间: {end_time - start_time} 秒, 生成token={content}")

                    # 处理文本分段和TTS逻辑
                    # 合并当前全部文本并处理未分割部分
                    full_text = "".join(response_message)
                    current_text = full_text[processed_chars:]  # 从未处理的位置开始

                    # 查找最后一个有效标点
                    punctuations = ("。", "？", "！", "；", "：")
                    last_punct_pos = -1
                    for punct in punctuations:
                        pos = current_text.rfind(punct)
                        if pos > last_punct_pos:
                            last_punct_pos = pos

                    # 找到分割点则处理
                    if last_punct_pos != -1:
                        segment_text_raw = current_text[:last_punct_pos + 1]
                        segment_text = get_string_no_punctuation_or_emoji(segment_text_raw)
                        if segment_text:
                            text_index += 1
                            self.recode_first_last_text(segment_text, text_index)
                            future = self.executor.submit(self.speak_and_play, segment_text, text_index)
                            self.tts_queue.put(future)
                            processed_chars += len(segment_text_raw)  # 更新已处理字符位置

        # 处理function call
        if tool_call_flag:
            bHasError = False
            if function_id is None:
                a = extract_json_from_string(content_arguments)
                if a is not None:
                    try:
                        content_arguments_json = json.loads(a)
                        function_name = content_arguments_json["name"]
                        function_arguments = json.dumps(content_arguments_json["arguments"], ensure_ascii=False)
                        function_id = str(uuid.uuid4().hex)
                    except Exception as e:
                        bHasError = True
                        response_message.append(a)
                else:
                    bHasError = True
                    response_message.append(content_arguments)
                if bHasError:
                    self.logger.bind(tag=TAG).error(f"function call error: {content_arguments}")
                else:
                    function_arguments = json.loads(function_arguments)
            if not bHasError:
                self.logger.bind(tag=TAG).info(f"function_name={function_name}, function_id={function_id}, function_arguments={function_arguments}")
                function_call_data = {
                    "name": function_name,
                    "id": function_id,
                    "arguments": function_arguments
                }
                result = self.func_handler.handle_llm_function_call(self, function_call_data)
                self._handle_function_result(result, function_call_data, text_index+1)

 

        # 处理最后剩余的文本
        full_text = "".join(response_message)
        remaining_text = full_text[processed_chars:]
        if remaining_text:
            segment_text = get_string_no_punctuation_or_emoji(remaining_text)
            if segment_text:
                text_index += 1
                self.recode_first_last_text(segment_text, text_index)
                future = self.executor.submit(self.speak_and_play, segment_text, text_index)
                self.tts_queue.put(future)

        # 存储对话内容
        if len(response_message)>0:
            self.dialogue.put(Message(role="assistant", content="".join(response_message)))

        self.llm_finish_task = True
        self.logger.bind(tag=TAG).debug(json.dumps(self.dialogue.get_llm_dialogue(), indent=4, ensure_ascii=False))

        return True

    # 处理函数调用结果
    def _handle_function_result(self, result, function_call_data, text_index):
        if result.action == Action.RESPONSE: # 直接回复前端
            text = result.response
            self.recode_first_last_text(text, text_index)
            future = self.executor.submit(self.speak_and_play, text, text_index)
            self.tts_queue.put(future)
            self.dialogue.put(Message(role="assistant", content=text))
        if result.action == Action.REQLLM: # 调用函数后再请求llm生成回复
            text = result.result
            if text is not None and len(text) > 0:
                function_id = function_call_data["id"]
                function_name = function_call_data["name"]
                function_arguments = function_call_data["arguments"]
                self.dialogue.put(Message(role='assistant',
                                            tool_calls=[{"id": function_id, 
                                                        "function": {"arguments": function_arguments,"name": function_name},
                                                        "type": 'function', 
                                                        "index": 0}]))

                self.dialogue.put(Message(role="tool", tool_call_id=function_id, content=text))
                self.chat_with_function_calling(text, tool_call=True)
        if result.action == Action.NOTFOUND:
            text = result.response

    # TTS任务处理线程
    def _tts_priority_thread(self):
        while not self.stop_event.is_set():
            text = None
            try:
                future = self.tts_queue.get()
                if future is None:
                    continue
                text = None
                opus_datas, text_index, tts_file = [], 0, None
                try:
                    self.logger.bind(tag=TAG).debug("正在处理TTS任务...")
                    tts_timeout = self.config.get("tts_timeout", 10)
                    tts_file, text, text_index = future.result(timeout=tts_timeout)
                    if text is None or len(text) <= 0:
                        self.logger.bind(tag=TAG).error(f"TTS出错：{text_index}: tts text is empty")
                    elif tts_file is None:
                        self.logger.bind(tag=TAG).error(f"TTS出错： file is empty: {text_index}: {text}")
                    else:
                        self.logger.bind(tag=TAG).debug(f"TTS生成：文件路径: {tts_file}")
                        if os.path.exists(tts_file):
                            opus_datas, duration = self.tts.audio_to_opus_data(tts_file)
                        else:
                            self.logger.bind(tag=TAG).error(f"TTS出错：文件不存在{tts_file}")
                except TimeoutError:
                    self.logger.bind(tag=TAG).error("TTS超时")
                except Exception as e:
                    self.logger.bind(tag=TAG).error(f"TTS出错: {e}")
                if not self.client_abort:
                    # 如果没有中途打断就发送语音
                    self.audio_play_queue.put((opus_datas, text, text_index))
                if self.tts.delete_audio_file and tts_file is not None and os.path.exists(tts_file):
                    os.remove(tts_file)
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"TTS任务处理错误: {e}")
                self.clearSpeakStatus()
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps({"type": "tts", "state": "stop", "session_id": self.session_id})),
                    self.loop
                )
                self.logger.bind(tag=TAG).error(f"tts_priority priority_thread: {text} {e}")

    # 音频播放任务处理线程
    def _audio_play_priority_thread(self):
        while not self.stop_event.is_set():
            text = None
            try:
                opus_datas, text, text_index = self.audio_play_queue.get()
                future = asyncio.run_coroutine_threadsafe(sendAudioMessage(self, opus_datas, text, text_index),
                                                          self.loop)
                future.result()
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"audio_play_priority priority_thread: {text} {e}")

    # 将文本转换为语音并播放
    def speak_and_play(self, text, text_index=0):
        if text is None or len(text) <= 0:
            self.logger.bind(tag=TAG).info(f"无需tts转换，query为空，{text}")
            return None, text, text_index
        tts_file = self.tts.to_tts(text)
        if tts_file is None:
            self.logger.bind(tag=TAG).error(f"tts转换失败，{text}")
            return None, text, text_index
        self.logger.bind(tag=TAG).debug(f"TTS 文件生成完毕: {tts_file}")
        return tts_file, text, text_index

    # 清除讲话状态
    def clearSpeakStatus(self):
        self.logger.bind(tag=TAG).debug(f"清除服务端讲话状态")
        self.asr_server_receive = True
        self.tts_last_text_index = -1
        self.tts_first_text_index = -1

    # 记录第一个和最后一个TTS文本
    def recode_first_last_text(self, text, text_index=0):
        if self.tts_first_text_index == -1:
            self.logger.bind(tag=TAG).info(f"大模型说出第一句话: {text}")
            self.tts_first_text_index = text_index
        self.tts_last_text_index = text_index

    # 关闭连接并清理资源
    async def close(self):
        """资源清理方法"""

        # 清理其他资源
        self.stop_event.set()
        self.executor.shutdown(wait=False)
        if self.websocket:
            await self.websocket.close()
        self.logger.bind(tag=TAG).info("连接资源已释放")

    # 重置VAD状态
    def reset_vad_states(self):
        self.client_audio_buffer = bytes()
        self.client_have_voice = False
        self.client_have_voice_last_time = 0
        self.client_voice_stop = False
        self.logger.bind(tag=TAG).debug("VAD states reset.")

    # 与用户聊天并关闭连接
    def chat_and_close(self, text):
        """Chat with the user and then close the connection"""
        try:
            # 使用现有的chat方法
            self.chat(text)

            # 聊天结束后关闭连接
            self.close_after_chat = True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Chat and close error: {str(e)}")