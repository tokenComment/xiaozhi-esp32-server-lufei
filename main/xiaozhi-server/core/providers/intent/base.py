from abc import ABC, abstractmethod
from typing import List, Dict
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class IntentProviderBase(ABC):
    """
    意图识别提供者的抽象基类。

    功能：
        1. 提供意图识别的通用接口。
        2. 根据配置动态加载意图选项。
        3. 允许设置 LLM（语言模型）提供者。

    属性：
        config (dict): 配置信息，包含意图选项和其他参数。
        intent_options (dict): 意图选项，定义了支持的意图及其描述。
        llm: LLM 提供者，用于实际的意图识别逻辑（由子类实现）。

    方法：
        set_llm(llm): 设置 LLM 提供者。
        detect_intent(conn, dialogue_history, text): 检测用户意图（抽象方法）。
    """

    def __init__(self, config):
        """
        初始化 IntentProviderBase。

        参数：
            config (dict): 配置信息，包含意图选项和其他参数。

        功能：
            1. 加载配置中的意图选项。
            2. 如果配置中未指定意图选项，则使用默认意图选项。
        """
        self.config = config
        self.intent_options = config.get("intent_options", {
            "continue_chat": "继续聊天",
            "end_chat": "结束聊天",
            "play_music": "播放音乐"
        })

    def set_llm(self, llm):
        """
        设置 LLM 提供者。

        参数：
            llm: LLM 提供者，用于实际的意图识别逻辑。

        功能：
            1. 将 LLM 提供者绑定到当前意图识别器。
            2. 记录日志，确认 LLM 提供者已设置。
        """
        self.llm = llm
        logger.bind(tag=TAG).debug("Set LLM for intent provider")

    @abstractmethod
    async def detect_intent(self, conn, dialogue_history: List[Dict], text: str) -> str:
        """
        检测用户最后一句话的意图。

        参数：
            conn: 客户端连接对象，包含上下文信息。
            dialogue_history (List[Dict]): 对话历史记录，每条记录包含 `role` 和 `content`。
            text (str): 用户的最后一句话。

        返回：
            str: 识别出的意图，格式为：
                - "继续聊天"
                - "结束聊天"
                - "播放音乐 歌名" 或 "随机播放音乐"

        功能：
            1. 根据对话历史和用户输入，识别用户意图。
            2. 返回识别结果，格式化为字符串。

        示例：
            >>> dialogue_history = [
            >>>     {"role": "User", "content": "你好"},
            >>>     {"role": "Assistant", "content": "你好呀"}
            >>> ]
            >>> text = "播放一首周杰伦的歌"
            >>> intent = await provider.detect_intent(conn, dialogue_history, text)
            >>> print(intent)
            "播放音乐 周杰伦的歌"

        注意：
            - 子类必须实现该方法。
            - 该方法是异步的，需要在异步环境中调用。
        """
        pass