# 导入 json 模块，用于处理 JSON 数据，如解析 API 返回的 JSON 字符串
import json
# 从配置文件的日志模块中导入设置日志的函数，用于配置和初始化日志记录
from config.logger import setup_logging
# 导入 requests 库，用于发送 HTTP 请求，与外部 API 进行通信
import requests
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

        :param config: 包含配置信息的字典，其中应包含 'api_key' 用于身份验证，
                       可选包含 'base_url' 作为 API 的基础 URL，
                       可选包含 'detail' 表示是否需要详细信息，默认为 False，
                       可选包含 'variables' 表示需要传递的变量，默认为空字典。
        """
        # 从配置字典中获取 API 密钥，并存储在实例的 api_key 属性中
        self.api_key = config["api_key"]
        # 从配置字典中获取基础 URL，如果没有提供则为 None
        self.base_url = config.get("base_url")
        # 从配置字典中获取是否需要详细信息的标志，如果没有提供则默认为 False
        self.detail = config.get("detail", False)
        # 从配置字典中获取需要传递的变量，如果没有提供则默认为空字典
        self.variables = config.get("variables", {})

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

            # 发起一个流式的 POST 请求到 API 的聊天完成端点
            with requests.post(
                    # 构建完整的请求 URL
                    f"{self.base_url}/chat/completions",
                    # 设置请求头，包含用于身份验证的 API 密钥
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    # 发送的 JSON 数据，包含流式标志、会话 ID、详细信息标志、变量和消息内容
                    json={
                        "stream": True,
                        "chatId": session_id,
                        "detail": self.detail,
                        "variables": self.variables,
                        "messages": [
                            {
                                "role": "user",
                                "content": last_msg["content"]
                            }
                        ]
                    },
                    # 开启流式响应模式
                    stream=True
            ) as r:
                # 逐行迭代响应内容
                for line in r.iter_lines():
                    # 检查行是否不为空
                    if line:
                        try:
                            # 检查行是否以 'data: ' 开头
                            if line.startswith(b'data: '):
                                # 检查去除 'data: ' 前缀后的数据是否为 '[DONE]'，如果是则结束循环
                                if line[6:].decode('utf-8') == '[DONE]':
                                    break
                                # 去除 'data: ' 前缀，并将剩余的 JSON 数据解析为 Python 对象
                                data = json.loads(line[6:])
                                # 检查数据中是否包含 'choices' 字段，并且 'choices' 列表不为空
                                if 'choices' in data and len(data['choices']) > 0:
                                    # 获取 'choices' 列表中的第一个元素的 'delta' 字段，如果不存在则为空字典
                                    delta = data['choices'][0].get('delta', {})
                                    # 检查 'delta' 字段是否存在，并且包含 'content' 字段，且 'content' 不为 None
                                    if delta and 'content' in delta and delta['content'] is not None:
                                        # 获取 'content' 字段的值
                                        content = delta['content']
                                        # 检查内容中是否包含 '<think>' 标签，如果包含则跳过本次循环
                                        if '<think>' in content:
                                            continue
                                        # 检查内容中是否包含 '</think>' 标签，如果包含则跳过本次循环
                                        if '</think>' in content:
                                            continue
                                        # 通过生成器逐块返回内容
                                        yield content

                        # 捕获并处理 JSON 解析错误
                        except json.JSONDecodeError as e:
                            # 发生 JSON 解析错误时，跳过当前行，继续处理下一行
                            continue
                        # 捕获并处理其他异常
                        except Exception as e:
                            # 发生其他异常时，跳过当前行，继续处理下一行
                            continue

        # 捕获并处理可能出现的异常
        except Exception as e:
            # 记录错误日志，包含异常信息
            logger.bind(tag=TAG).error(f"Error in response generation: {e}")
            # 当出现异常时，通过生成器返回错误提示信息
            yield "【服务响应异常】"