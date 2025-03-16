from typing import List, Dict
from ..base import IntentProviderBase
from config.logger import setup_logging
import re

TAG = __name__
logger = setup_logging()


class IntentProvider(IntentProviderBase):
    """
    意图识别提供者。

    功能：
        1. 根据配置的意图选项动态生成系统提示词。
        2. 使用 LLM（语言模型）进行意图识别。
        3. 提取意图识别结果并返回。

    属性：
        config (dict): 配置信息，包含意图选项。
        llm: LLM 提供者，用于意图识别。
        prompt (str): 系统提示词，用于引导 LLM 进行意图识别。
    """

    def __init__(self, config):
        """
        初始化 IntentProvider。

        参数：
            config (dict): 配置信息，包含意图选项。
        """
        super().__init__(config)
        self.llm = None  # 初始化 LLM 提供者为 None
        self.prompt = self.get_intent_system_prompt()  # 生成系统提示词

    def get_intent_system_prompt(self) -> str:
        """
        根据配置的意图选项动态生成系统提示词。

        功能：
            1. 遍历配置中的意图选项，生成对应的提示词。
            2. 提示词包含意图分类和处理步骤，用于引导 LLM 进行意图识别。

        返回：
            str: 格式化后的系统提示词。

        示例：
            >>> config = {
            >>>     "intent_options": {
            >>>         "continue_chat": "1.继续聊天, 除了播放音乐和结束聊天的时候的选项, 比如日常的聊天和问候, 对话等",
            >>>         "end_chat": "2.结束聊天, 用户发来如再见之类的表示结束的话, 不想再进行对话的时候",
            >>>         "play_music": "3.播放音乐, 用户希望你可以播放音乐, 只用于播放音乐的意图"
            >>>     }
            >>> }
            >>> provider = IntentProvider(config)
            >>> print(provider.prompt)
            生成的系统提示词
        """
        intent_list = []  # 初始化意图列表

        # 遍历配置中的意图选项，生成对应的提示词
        for key, value in self.intent_options.items():
            if key == "play_music":
                intent_list.append("3.播放音乐, 用户希望你可以播放音乐, 只用于播放音乐的意图")
            elif key == "end_chat":
                intent_list.append("2.结束聊天, 用户发来如再见之类的表示结束的话, 不想再进行对话的时候")
            elif key == "continue_chat":
                intent_list.append("1.继续聊天, 除了播放音乐和结束聊天的时候的选项, 比如日常的聊天和问候, 对话等")
            else:
                intent_list.append(value)

        # 构建系统提示词
        prompt = (
            "你是一个意图识别助手。你需要根据和用户的对话记录，重点分析用户的最后一句话，判断用户意图属于以下哪一类(使用<start>和<end>标志)：\n"
            "<start>"
            f"{', '.join(intent_list)}"  # 插入意图列表
            "<end>\n"
            "你需要按照以下的步骤处理用户的对话：\n"
            "1. 思考出对话的意图是哪一类的。\n"
            "2. 属于1和2的意图, 直接返回，返回格式如下：\n"
            "{intent: '用户意图'}\n"
            "3. 属于3的意图，则继续分析用户希望播放的音乐。\n"
            "4. 如果无法识别出具体歌名，可以返回'随机播放音乐'。\n"
            "{intent: '播放音乐 [获取的音乐名字]'}\n"
            "下面是几个处理的示例(思考的内容不返回, 只返回json部分, 无额外的内容)：\n"
            "```"
            "用户: 你今天怎么样?\n"
            "返回结果: {intent: '继续聊天'}\n"
            "```"
            "用户: 我今天有点累了, 我们明天再聊吧\n"
            "返回结果: {intent: '结束聊天'}\n"
            "```"
            "用户: 你可以播放一首中秋月给我听吗\n"
            "返回结果: {intent: '播放音乐 [中秋月]'}\n"
            "```"
            "你现在可以使用的音乐的名称如下(使用<start>和<end>标志)：\n"
        )
        return prompt

    async def detect_intent(self, conn, dialogue_history: List[Dict], text: str) -> str:
        """
        使用 LLM 检测用户意图。

        功能：
            1. 构建用户最后一句话的提示。
            2. 使用 LLM 进行意图识别。
            3. 提取意图识别结果并返回。

        参数：
            conn: 客户端连接对象，包含音乐文件列表等信息。
            dialogue_history (List[Dict]): 对话历史记录。
            text (str): 用户的最后一句话。

        返回：
            str: 意图识别结果，格式为 JSON 字符串。

        示例：
            >>> dialogue_history = [
            >>>     {"role": "User", "content": "你好"},
            >>>     {"role": "Assistant", "content": "你好呀"}
            >>> ]
            >>> text = "播放一首周杰伦的歌"
            >>> intent = await provider.detect_intent(conn, dialogue_history, text)
            >>> print(intent)
            {intent: '播放音乐 [周杰伦的歌]'}
        """
        if not self.llm:
            raise ValueError("LLM provider not set")  # 如果未设置 LLM 提供者，抛出异常

        # 构建用户最后一句话的提示
        msgStr = ""

        # 只使用最后两句即可
        if len(dialogue_history) >= 2:
            # 保证最少有两句话的时候处理
            msgStr += f"{dialogue_history[-2]['role']}: {dialogue_history[-2]['content']}\n"
        msgStr += f"{dialogue_history[-1]['role']}: {dialogue_history[-1]['content']}\n"

        msgStr += f"User: {text}\n"
        user_prompt = f"当前的对话如下：\n{msgStr}"  # 构建用户提示

        # 构建系统提示词，包含音乐文件列表
        prompt_music = f"{self.prompt}\n<start>{conn.music_handler.music_files}\n<end>"
        logger.bind(tag=TAG).debug(f"User prompt: {prompt_music}")  # 记录用户提示

        # 使用 LLM 进行意图识别
        intent = self.llm.response_no_stream(
            system_prompt=prompt_music,  # 系统提示词
            user_prompt=user_prompt  # 用户提示
        )

        # 使用正则表达式提取意图识别结果
        match = re.search(r'\{.*?\}', intent)
        if match:
            result = match.group(0)  # 获取匹配到的内容（包含 {}）
            logger.bind(tag=TAG).info(f"Detected intent: {result}")  # 记录意图识别结果
            intent = result
        else:
            intent = "{intent: '继续聊天'}"  # 如果未匹配到结果，返回默认意图
        return intent.strip()  # 返回意图识别结果