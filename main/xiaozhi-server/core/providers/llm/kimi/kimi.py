# 从配置文件的日志模块中导入设置日志的函数，用于配置和初始化日志记录
from config.logger import setup_logging
# 导入 OpenAI 官方 Python 库，用于与 OpenAI 的 API 进行交互
import openai
# 从核心的大语言模型（LLM）提供程序基础模块中导入基类，用于继承和扩展
from core.providers.llm.base import LLMProviderBase
# 从 typing 模块导入 Dict 和 Any 类型提示，用于增强代码的可读性和可维护性
from typing import Dict, Any
# 导入 json 模块，用于处理 JSON 数据，如序列化和反序列化
import json
# 从 openai.types.chat.chat_completion 模块导入 Choice 类，用于表示聊天完成的选择结果
from openai.types.chat.chat_completion import Choice

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
        # 检查 API 密钥中是否包含 "你" 字符，若包含则表示未正确配置密钥
        if "你" in self.api_key:
            # 记录错误日志，提示用户配置 LLM 的密钥
            logger.bind(tag=TAG).error("你还没配置LLM的密钥，请在配置文件中配置密钥，否则无法正常工作")
        # 使用获取到的 API 密钥和基础 URL 创建 OpenAI 客户端实例
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    # 定义一个方法，用于处理搜索工具的调用
    def search_impl(self, arguments: Dict[str, Any]) -> Any:
        """
        在使用 Moonshot AI 提供的 search 工具的场合，只需要原封不动返回 arguments 即可，
        不需要额外的处理逻辑。

        但如果你想使用其他模型，并保留联网搜索的功能，那你只需要修改这里的实现（例如调用搜索
        和获取网页内容等），函数签名不变，依然是 work 的。

        这最大程度保证了兼容性，允许你在不同的模型间切换，并且不需要对代码有破坏性的修改。

        :param arguments: 包含搜索工具调用参数的字典。
        :return: 返回传入的参数，不做额外处理。
        """
        return arguments

    # 定义一个方法，用于与 OpenAI 的聊天完成 API 进行交互
    def chat(self, messages) -> Choice:
        """
        调用 OpenAI 的聊天完成 API 进行对话。

        :param messages: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 返回聊天完成结果中的第一个选择。
        """
        # 调用 OpenAI 客户端的聊天完成 API，创建一个聊天完成实例
        completion = self.client.chat.completions.create(
            # 指定使用的模型名称
            model=self.model_name,
            # 传递对话消息列表
            messages=messages,
            # 设置生成文本的温度，控制随机性，值越低越稳定
            temperature=0.3,
            # 定义使用的工具，这里使用了内置的网页搜索工具
            tools=[
                {
                    "type": "builtin_function",
                    "function": {
                        "name": "$web_search",
                    },
                }
            ]
        )
        # 返回聊天完成结果中的第一个选择
        return completion.choices[0]

    # 定义一个方法，用于生成对话响应
    def response(self, session_id, dialogue):
        """
        生成对话响应，处理工具调用和循环请求，直到得到最终结果。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 返回最终的对话响应内容。
        """
        try:
            # 初始化完成原因变量为 None
            finish_reason = None
            # 循环处理，直到完成原因不为 None 且不为 "tool_calls"
            while finish_reason is None or finish_reason == "tool_calls":
                # 调用 chat 方法进行对话，获取选择结果
                choice = self.chat(dialogue)
                # 获取选择结果的完成原因
                finish_reason = choice.finish_reason
                # 打印完成原因，方便调试
                print(finish_reason)
                # 检查完成原因是否为 "tool_calls"，表示需要调用工具
                if finish_reason == "tool_calls":
                    # 将模型返回的助手消息添加到对话列表中，以便下次请求使用
                    dialogue.append(choice.message)
                    # 遍历助手消息中的工具调用列表
                    for tool_call in choice.message.tool_calls:
                        # 获取工具调用的名称
                        tool_call_name = tool_call.function.name
                        # 反序列化工具调用的参数，将其从 JSON 字符串转换为 Python 对象
                        tool_call_arguments = json.loads(tool_call.function.arguments)
                        # 检查工具调用的名称是否为 "$web_search"
                        if tool_call_name == "$web_search":
                            # 调用 search_impl 方法处理网页搜索工具调用，获取工具调用结果
                            tool_result = self.search_impl(tool_call_arguments)
                        else:
                            # 如果工具调用名称不是 "$web_search"，则返回错误信息
                            tool_result = f"Error: unable to find tool by name '{tool_call_name}'"

                        # 使用工具调用结果构造一个角色为 "tool" 的消息，添加到对话列表中
                        dialogue.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call_name,
                            # 将工具调用结果序列化为 JSON 字符串
                            "content": json.dumps(tool_result),
                        })

            # 返回最终的对话响应内容
            return choice.message.content

        # 捕获并处理可能出现的异常
        except Exception as e:
            # 记录错误日志，包含具体的异常信息
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")