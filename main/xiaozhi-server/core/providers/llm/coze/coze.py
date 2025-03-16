from config.logger import setup_logging
import requests
import json
import re
from core.providers.llm.base import LLMProviderBase
import os
from cozepy import COZE_CN_BASE_URL
from cozepy import Coze, TokenAuth, Message, ChatStatus, MessageContentType, ChatEventType  # noqa

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    """
    基于 Coze API 的 LLM 提供者。

    功能：
        1. 使用 Coze API 进行对话管理。
        2. 支持流式聊天（streaming chat）。
        3. 管理会话与对话的映射关系。

    属性：
        personal_access_token (str): Coze API 的个人访问令牌。
        bot_id (str): 机器人 ID。
        user_id (str): 用户 ID。
        session_conversation_map (dict): 会话 ID 到对话 ID 的映射表。
    """

    def __init__(self, config):
        """
    初始化 LLMProvider。

    功能：
        1. 从配置中加载必要的参数，包括个人访问令牌、机器人 ID 和用户 ID。
        2. 初始化会话与对话的映射表，用于管理多个会话的对话状态。

    参数：
        config (dict): 配置信息，包含以下字段：
            - personal_access_token (str): Coze API 的个人访问令牌，用于认证和访问 Coze 服务。
            - bot_id (str): 机器人 ID，标识与用户交互的机器人实例。
            - user_id (str): 用户 ID，标识与机器人交互的用户。

    属性：
        personal_access_token (str): Coze API 的个人访问令牌。
        bot_id (str): 机器人 ID。
        user_id (str): 用户 ID。
        session_conversation_map (dict): 会话 ID 到对话 ID 的映射表，用于管理多个会话的对话状态。

    示例：
        >>> config = {
        >>>     "personal_access_token": "your_personal_access_token",
        >>>     "bot_id": "your_bot_id",
        >>>     "user_id": "your_user_id"
        >>> }
        >>> provider = LLMProvider(config)
        >>> print(provider.personal_access_token)
        your_personal_access_token

    注意：
        - `config` 参数必须包含 `personal_access_token`、`bot_id` 和 `user_id` 字段。
        - 如果这些字段缺失，可能会导致 Coze API 调用失败。
        """
        # 从配置中加载个人访问令牌
        self.personal_access_token = config.get("personal_access_token")
        # 从配置中加载机器人 ID
        self.bot_id = config.get("bot_id")
        # 从配置中加载用户 ID
        self.user_id = config.get("user_id")
        # 初始化会话与对话的映射表
        self.session_conversation_map = {}  # 存储 session_id 和 conversation_id 的映射

    def response(self, session_id, dialogue):
        """
    根据会话 ID 和对话历史生成响应。

    功能：
        1. 获取用户最后一条消息。
        2. 如果当前会话没有对应的对话 ID，则创建新的对话。
        3. 使用 Coze API 的流式聊天接口生成响应。
        4. 逐条输出聊天事件的内容。

    参数：
        session_id (str): 会话 ID，用于标识当前会话。
        dialogue (list): 对话历史，包含多个字典，每个字典包含以下字段：
            - role (str): 角色（"user" 或 "assistant"）。
            - content (str): 消息内容。

    返回：
        generator: 逐条生成聊天事件的内容。

    示例：
        >>> dialogue = [
        >>>     {"role": "user", "content": "你好"},
        >>>     {"role": "assistant", "content": "你好呀"}
        >>> ]
        >>> provider = LLMProvider(config)
        >>> for response in provider.response("session_id", dialogue):
        >>>     print(response)
        生成的响应内容

    注意：
        - 该方法假设 `dialogue` 中至少包含一条用户消息。
        - 如果会话中没有找到对应的对话 ID，则会自动创建一个新的对话。
        - 使用 Coze API 的流式聊天接口时，会逐条处理聊天事件并输出内容。
        """
        # 获取 Coze API 的个人访问令牌和基础 URL
        coze_api_token = self.personal_access_token
        coze_api_base = COZE_CN_BASE_URL

        # 从对话历史中获取用户最后一条消息
        # reversed(dialogue) 用于从后向前遍历对话历史，确保获取最新的用户消息
        last_msg = next(m for m in reversed(dialogue) if m["role"] == "user")

        # 初始化 Coze 客户端
        coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)

        # 从会话映射表中获取当前会话的对话 ID
        conversation_id = self.session_conversation_map.get(session_id)

        # 如果当前会话没有对应的对话 ID，则创建新的对话
        if not conversation_id:
            # 创建新的对话
            conversation = coze.conversations.create(messages=[])
            conversation_id = conversation.id
            # 将新的对话 ID 更新到会话映射表中
            self.session_conversation_map[session_id] = conversation_id

        # 调用 Coze API 的流式聊天接口
        for event in coze.chat.stream(
            bot_id=self.bot_id,  # 机器人 ID
            user_id=self.user_id,  # 用户 ID
            additional_messages=[  # 添加用户最后一条消息作为额外消息
                Message.build_user_question_text(last_msg["content"]),
            ],
            conversation_id=conversation_id,  # 当前对话 ID
        ):
            # 检查聊天事件类型
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                # 如果是消息增量事件，输出聊天事件的内容
                print(event.message.content, end="", flush=True)
                # 逐条生成聊天事件的内容
                yield event.message.content