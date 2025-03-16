# 导入用于处理 JSON 数据的模块
import json
# 从配置文件的日志模块中导入设置日志的函数
from config.logger import setup_logging
# 导入用于发送 HTTP 请求的库
import requests
# 从核心的大语言模型（LLM）提供程序基础模块中导入基类
from core.providers.llm.base import LLMProviderBase

# 获取当前模块的名称，作为日志标签
TAG = __name__
# 调用设置日志的函数，初始化日志记录器
logger = setup_logging()

# 定义一个大语言模型（LLM）提供程序类，继承自 LLMProviderBase 基类
class LLMProvider(LLMProviderBase):
    # 类的初始化方法，在创建该类的实例时会被调用
    def __init__(self, config):
        """
        初始化 LLMProvider 类的实例。

        :param config: 包含配置信息的字典，其中应包含 'api_key' 用于身份验证，
                       可选包含 'base_url' 作为 API 的基础 URL，默认为 'https://api.dify.ai/v1'。
        """
        # 从配置字典中获取 API 密钥，并存储在实例的 api_key 属性中
        self.api_key = config["api_key"]
        # 从配置字典中获取基础 URL，如果没有提供则使用默认值 'https://api.dify.ai/v1'，
        # 并去除 URL 末尾的斜杠
        self.base_url = config.get("base_url", "https://api.dify.ai/v1").rstrip('/')
        # 初始化一个空字典，用于存储会话 ID 和对话 ID 的映射关系
        self.session_conversation_map = {}

    # 定义一个生成器方法，用于处理对话响应
    def response(self, session_id, dialogue):
        """
        处理对话响应，通过流式请求从 API 获取答案并逐块生成。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 一个生成器，逐块生成 API 返回的答案。
        """
        try:
            # 从对话列表中逆序查找最后一条用户发送的消息
            last_msg = next(m for m in reversed(dialogue) if m["role"] == "user")
            # 根据会话 ID 从映射字典中获取对应的对话 ID，如果不存在则为 None
            conversation_id = self.session_conversation_map.get(session_id)

            # 发起一个流式的 POST 请求到 API 的聊天消息端点
            with requests.post(
                    # 构建完整的请求 URL
                    f"{self.base_url}/chat-messages",
                    # 设置请求头，包含用于身份验证的 API 密钥
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    # 发送的 JSON 数据，包含查询内容、响应模式、用户会话 ID、输入参数和对话 ID
                    json={
                        "query": last_msg["content"],
                        "response_mode": "streaming",
                        "user": session_id,
                        "inputs": {},
                        "conversation_id": conversation_id
                    },
                    # 开启流式响应模式
                    stream=True
            ) as r:
                # 逐行迭代响应内容
                for line in r.iter_lines():
                    # 检查行是否以 'data: ' 开头
                    if line.startswith(b'data: '):
                        # 去除 'data: ' 前缀，并将剩余的 JSON 数据解析为 Python 对象
                        event = json.loads(line[6:])
                        # 如果之前没有找到对话 ID，则从当前事件中获取对话 ID
                        if not conversation_id:
                            conversation_id = event.get('conversation_id')
                            # 更新会话 ID 和对话 ID 的映射关系
                            self.session_conversation_map[session_id] = conversation_id
                        # 如果事件中包含答案，则通过生成器逐块返回答案
                        if event.get('answer'):
                            yield event['answer']

        # 捕获并处理可能出现的异常
        except Exception as e:
            # 记录错误日志，包含异常信息
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")
            # 当出现异常时，通过生成器返回错误提示信息
            yield "【服务响应异常】"