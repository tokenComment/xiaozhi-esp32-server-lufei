# 导入 OpenAI 官方 Python 库，用于与 OpenAI 的 API 进行交互
import openai
# 从核心工具模块导入检查模型密钥的函数，用于验证 API 密钥的有效性
from core.utils.util import check_model_key
# 从核心的大语言模型（LLM）提供程序基础模块中导入基类，用于继承和扩展
from core.providers.llm.base import LLMProviderBase

# 定义一个大语言模型（LLM）提供程序类，继承自 LLMProviderBase 基类
class LLMProvider(LLMProviderBase):
    # 类的初始化方法，在创建该类的实例时会被调用
    def __init__(self, config):
        """
        初始化 LLMProvider 类的实例。

        :param config: 包含配置信息的字典，其中应包含 'model_name'、'api_key'，
                       可选包含 'base_url' 或 'url' 作为 API 的基础 URL。
        """
        # 从配置字典中获取模型名称，如果没有提供则为 None
        self.model_name = config.get("model_name")
        # 从配置字典中获取 API 密钥，如果没有提供则为 None
        self.api_key = config.get("api_key")
        # 检查配置字典中是否包含 'base_url' 字段
        if 'base_url' in config:
            # 如果包含，则获取 'base_url' 的值
            self.base_url = config.get("base_url")
        else:
            # 如果不包含，则获取 'url' 的值
            self.base_url = config.get("url")
        # 调用检查模型密钥的函数，验证 LLM 的 API 密钥是否有效
        check_model_key("LLM", self.api_key)
        # 使用获取到的 API 密钥和基础 URL 创建 OpenAI 客户端实例
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    # 定义一个生成器方法，用于处理对话响应
    def response(self, session_id, dialogue):
        """
        生成对话响应，通过流式请求从 OpenAI 获取答案并逐块生成。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 一个生成器，逐块生成 OpenAI 返回的答案。
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

            # 初始化一个标志变量，用于控制是否输出内容
            is_active = True
            # 遍历流式响应的每个块
            for chunk in responses:
                try:
                    # 获取响应块中的第一个选择的增量信息，如果不存在则为 None
                    delta = chunk.choices[0].delta if getattr(chunk, 'choices', None) else None
                    # 获取增量信息中的内容，如果不存在则为空字符串
                    content = delta.content if hasattr(delta, 'content') else ''
                except IndexError:
                    # 如果出现索引错误，将内容设置为空字符串
                    content = ''
                # 如果内容不为空
                if content:
                    # 处理标签跨多个 chunk 的情况
                    if '<think>' in content:
                        # 遇到 <think> 标签，将标志变量设置为 False，停止输出内容
                        is_active = False
                        # 截取 <think> 标签之前的内容
                        content = content.split('<think>')[0]
                    if '</think>' in content:
                        # 遇到 </think> 标签，将标志变量设置为 True，恢复输出内容
                        is_active = True
                        # 截取 </think> 标签之后的内容
                        content = content.split('</think>')[-1]
                    # 如果标志变量为 True，则通过生成器返回内容
                    if is_active:
                        yield content

        except Exception as e:
            # 记录错误日志，表明在生成响应时出错，并包含具体的异常信息
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")

    # 定义一个生成器方法，用于处理带函数调用的对话响应
    def response_with_functions(self, session_id, dialogue, functions=None):
        """
        生成带函数调用的对话响应，通过流式请求从 OpenAI 获取答案和工具调用信息并逐块生成。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :param functions: 包含工具调用信息的列表，可选参数。
        :return: 一个生成器，逐块生成 OpenAI 返回的答案和工具调用信息。
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
            # 记录错误日志，表明在进行函数调用流式处理时出错，并包含具体的异常信息
            self.logger.bind(tag=TAG).error(f"Error in function call streaming: {e}")
            # 当出现异常时，通过生成器返回错误提示信息
            yield {"type": "content", "content": f"【OpenAI服务响应异常: {e}】"}