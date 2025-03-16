from ..base import IntentProviderBase
from typing import List, Dict
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class IntentProvider(IntentProviderBase):
    """
    默认的意图识别提供者。

    功能：
        1. 继承自 `IntentProviderBase`，提供一个简单的意图识别实现。
        2. 始终返回“继续聊天”意图，忽略对话历史和用户输入。

    属性：
        config (dict): 配置信息，包含意图选项。
        intent_options (dict): 意图选项，定义了支持的意图及其描述。
    """

    async def detect_intent(self, conn, dialogue_history: List[Dict], text: str) -> str:
        """
        默认的意图识别实现，始终返回“继续聊天”。

        功能：
            1. 忽略对话历史和用户输入。
            2. 始终返回“继续聊天”意图。

        参数：
            conn: 客户端连接对象，包含上下文信息。
            dialogue_history (List[Dict]): 对话历史记录，每条记录包含 `role` 和 `content`。
            text (str): 用户的最后一句话。

        返回：
            str: 固定返回“继续聊天”意图。

        示例：
            >>> dialogue_history = [
            >>>     {"role": "User", "content": "你好"},
            >>>     {"role": "Assistant", "content": "你好呀"}
            >>> ]
            >>> text = "播放一首周杰伦的歌"
            >>> intent = await provider.detect_intent(conn, dialogue_history, text)
            >>> print(intent)
            继续聊天

        注意：
            - 该实现是一个占位符，用于在未实现具体意图识别逻辑时提供默认行为。
            - 在实际应用中，应替换为更复杂的意图识别逻辑。
        """
        logger.bind(tag=TAG).debug("Using NoIntentProvider, always returning continue chat")
        return self.intent_options["continue_chat"]