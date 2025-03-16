# 从 abc 模块导入 ABC 和 abstractmethod，用于定义抽象基类和抽象方法
from abc import ABC, abstractmethod
# 从配置文件的日志模块中导入设置日志的函数，用于配置和初始化日志记录
from config.logger import setup_logging

# 获取当前模块的名称，作为日志标签，方便在日志中定位问题
TAG = __name__
# 调用设置日志的函数，初始化日志记录器
logger = setup_logging()

# 定义一个抽象基类 LLMProviderBase，继承自 ABC 类
class LLMProviderBase(ABC):
    # 定义一个抽象方法，用于生成 LLM 的响应
    @abstractmethod
    def response(self, session_id, dialogue):
        """
        LLM 响应生成器。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 一个生成器，逐块生成 LLM 的响应内容。
        """
        pass

    # 定义一个方法，用于获取非流式的 LLM 响应
    def response_no_stream(self, system_prompt, user_prompt):
        """
        获取非流式的 LLM 响应。

        :param system_prompt: 系统提示信息，用于指导 LLM 的行为。
        :param user_prompt: 用户输入的提示信息。
        :return: 返回完整的 LLM 响应内容，如果出现异常则返回错误提示信息。
        """
        try:
            # 构造对话格式，将系统提示和用户提示组合成对话列表
            dialogue = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            # 初始化一个空字符串，用于存储最终的响应结果
            result = ""
            # 调用 response 方法，逐块获取 LLM 的响应内容，并拼接成完整的结果
            for part in self.response("", dialogue):
                result += part
            # 返回完整的响应结果
            return result

        except Exception as e:
            # 记录错误日志，表明在生成 Ollama 响应时出错，并包含具体的异常信息
            logger.bind(tag=TAG).error(f"Error in Ollama response generation: {e}")
            # 当出现异常时，返回错误提示信息
            return "【LLM服务响应异常】"

    # 定义一个方法，用于处理带函数调用的 LLM 响应（流式）
    def response_with_functions(self, session_id, dialogue, functions=None):
        """
        函数调用（流式）的默认实现。
        支持函数调用的提供程序应重写此方法。

        返回值：一个生成器，逐块生成文本令牌或特殊的函数调用令牌。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :param functions: 包含工具调用信息的列表，可选参数。
        :return: 一个生成器，逐块生成 LLM 的响应内容，格式为包含类型和内容的字典。
        """
        # 对于不支持函数调用的提供程序，直接返回常规的响应内容
        for token in self.response(session_id, dialogue):
            # 通过生成器返回响应内容，格式为包含类型和内容的字典
            yield {"type": "content", "content": token}