# 从配置文件的日志模块中导入设置日志的函数，用于配置和初始化日志记录
from config.logger import setup_logging
# 从 openai 库中导入 OpenAI 类，用于与 OpenAI 或兼容的 API 进行交互
from openai import OpenAI
# 导入 json 模块，用于处理 JSON 数据
import json
# 从核心的大语言模型（LLM）提供程序基础模块中导入基类，用于继承和扩展
from core.providers.llm.base import LLMProviderBase

# 获取当前模块的名称，作为日志标签，方便在日志中定位问题
TAG = __name__
# 调用设置日志的函数，初始化日志记录器
logger = setup_logging()

# 定义一个大语言模型（LLM）提供程序类，继承自 LLMProviderBase 基类
class LLMProvider(LLMProviderBase):
    # 类的初始化方法，在创建该类的实例时会被调用
    def __init__(self, config):
        """
        初始化 LLMProvider 类的实例。

        :param config: 包含配置信息的字典，其中应包含 'model_name'，
                       可选包含 'base_url'，默认为 'http://localhost:11434'。
        """
        # 从配置字典中获取模型名称，如果没有提供则为 None
        self.model_name = config.get("model_name")
        # 从配置字典中获取基础 URL，如果没有提供则使用默认值 'http://localhost:11434'
        self.base_url = config.get("base_url", "http://localhost:11434")
        # 如果基础 URL 不以 '/v1' 结尾，则添加 '/v1'
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"

        # 创建 OpenAI 客户端实例，使用 Ollama 的基础 URL
        self.client = OpenAI(
            base_url=self.base_url,
            # Ollama 不需要 API 密钥，但 OpenAI 客户端要求提供一个，这里使用 'ollama' 作为占位符
            api_key="ollama"
        )

    # 定义一个生成器方法，用于处理对话响应
    def response(self, session_id, dialogue):
        """
        生成对话响应，通过流式请求从 Ollama 获取答案并逐块生成。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 一个生成器，逐块生成 Ollama 返回的答案。
        """
        try:
            # 调用 OpenAI 客户端的聊天完成 API，发起流式请求
            responses = self.client.chat.completions.create(
                # 指定使用的模型名称
                model=self.model_name,
                # 传递对话消息列表
                messages=dialogue,
                # 开启流式响应模式
                stream=True
            )

            is_active=True
            # 遍历流式响应的每个块
            for chunk in responses:
                try:
                    # 获取响应块中的第一个选择的增量信息，如果不存在则为 None
                    delta = chunk.choices[0].delta if getattr(chunk, 'choices', None) else None
                    # 获取增量信息中的内容，如果不存在则为空字符串
                    content = delta.content if hasattr(delta, 'content') else ''
                    # 如果内容不为空，则通过生成器返回该内容
                    if content:
                        if '<think>' in content:
                            is_active = False
                            content = content.split('<think>')[0]
                        if '</think>' in content:
                            is_active = True
                            content = content.split('</think>')[-1]
                        if is_active:
                            yield content
                except Exception as e:
                    # 记录错误日志，表明处理响应块时出错，并包含具体的异常信息
                    logger.bind(tag=TAG).error(f"Error processing chunk: {e}")

        except Exception as e:
            # 记录错误日志，表明在生成 Ollama 响应时出错，并包含具体的异常信息
            logger.bind(tag=TAG).error(f"Error in Ollama response generation: {e}")
            # 当出现异常时，通过生成器返回错误提示信息
            yield "【Ollama服务响应异常】"

    # 定义一个生成器方法，用于处理带函数调用的对话响应
    def response_with_functions(self, session_id, dialogue, functions=None):
        """
        生成带函数调用的对话响应，通过流式请求从 Ollama 获取答案和工具调用信息并逐块生成。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :param functions: 包含工具调用信息的列表，可选参数。
        :return: 一个生成器，逐块生成 Ollama 返回的答案和工具调用信息。
        """
        try:
            # 调用 OpenAI 客户端的聊天完成 API，发起流式请求，并传递工具调用信息
            stream = self.client.chat.completions.create(
                # 指定使用的模型名称
                model=self.model_name,
                # 传递对话消息列表
                messages=dialogue,
                # 开启流式响应模式
                stream=True,
                # 传递工具调用信息
                tools=functions,
            )

            # 遍历流式响应的每个块
            for chunk in stream:
                # 通过生成器返回响应块中的第一个选择的增量信息中的内容和工具调用信息
                yield chunk.choices[0].delta.content, chunk.choices[0].delta.tool_calls

        except Exception as e:
            # 记录错误日志，表明在进行 Ollama 函数调用时出错，并包含具体的异常信息
            logger.bind(tag=TAG).error(f"Error in Ollama function call: {e}")
            # 当出现异常时，通过生成器返回错误提示信息
            yield {"type": "content", "content": f"【Ollama服务响应异常: {str(e)}】"}