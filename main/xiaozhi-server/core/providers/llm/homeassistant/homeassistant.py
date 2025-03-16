# 导入 requests 库，用于发送 HTTP 请求
import requests
# 从 requests 库的异常模块中导入 RequestException，用于捕获 HTTP 请求过程中可能出现的异常
from requests.exceptions import RequestException
# 从配置文件的日志模块中导入设置日志的函数，用于配置和初始化日志记录
from config.logger import setup_logging
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

        :param config: 包含配置信息的字典，其中应包含 'agent_id'、'api_key'，
                       可选包含 'base_url' 或 'url' 作为 API 的基础 URL。
        """
        # 从配置字典中获取 agent_id，如果没有提供则为 None
        self.agent_id = config.get("agent_id")
        # 从配置字典中获取 API 密钥，如果没有提供则为 None
        self.api_key = config.get("api_key")
        # 从配置字典中获取基础 URL，优先使用 'base_url'，如果没有则尝试使用 'url'
        self.base_url = config.get("base_url", config.get("url"))
        # 拼接完整的 API 请求 URL
        self.api_url = f"{self.base_url}/api/conversation/process"

    # 定义一个生成器方法，用于处理对话响应
    def response(self, session_id, dialogue):
        """
        生成对话响应，通过向 API 发送请求获取答案并逐块生成。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 一个生成器，逐块生成 API 返回的答案。
        """
        # 打印对话信息，方便调试
        print(dialogue)
        try:
            # home assistant 语音助手自带意图，无需使用 xiaozhi ai 自带的，
            # 只需要把用户说的话传递给 home assistant 即可

            # 初始化输入文本为 None
            input_text = None
            # 检查 dialogue 是否为列表类型
            if isinstance(dialogue, list):
                # 逆序遍历对话列表，找到最后一个 role 为 'user' 的消息
                for message in reversed(dialogue):
                    # 检查消息的 role 是否为 'user'
                    if message.get("role") == "user":
                        # 获取该消息的 content 内容，如果没有则为空字符串
                        input_text = message.get("content", "")
                        # 找到后立即退出循环
                        break

            # 构造要发送给 API 的请求数据
            payload = {
                # 用户输入的文本
                "text": input_text,
                # 代理 ID
                "agent_id": self.agent_id,
                # 使用 session_id 作为对话 ID
                "conversation_id": session_id
            }
            # 设置请求头，包含身份验证信息和内容类型
            headers = {
                # 使用 API 密钥进行身份验证
                "Authorization": f"Bearer {self.api_key}",
                # 指定请求体的内容类型为 JSON
                "Content-Type": "application/json"
            }

            # 发起一个 POST 请求到指定的 API URL，携带请求数据和请求头
            response = requests.post(self.api_url, json=payload, headers=headers)

            # 检查请求的响应状态码，如果状态码不是 200 系列，会抛出 HTTPError 异常
            response.raise_for_status()

            # 将响应的 JSON 数据解析为 Python 对象
            data = response.json()
            # 从解析后的数据中提取语音回复内容
            speech = data.get("response", {}).get("speech", {}).get("plain", {}).get("speech", "")

            # 如果提取到了语音回复内容，则通过生成器返回该内容
            if speech:
                yield speech
            else:
                # 如果没有提取到语音回复内容，记录警告日志
                logger.bind(tag=TAG).warning("API 返回数据中没有 speech 内容")

        # 捕获并处理 HTTP 请求过程中可能出现的异常
        except RequestException as e:
            # 记录错误日志，包含具体的异常信息
            logger.bind(tag=TAG).error(f"HTTP 请求错误: {e}")
        # 捕获并处理其他可能出现的异常
        except Exception as e:
            # 记录错误日志，包含具体的异常信息
            logger.bind(tag=TAG).error(f"生成响应时出错: {e}")