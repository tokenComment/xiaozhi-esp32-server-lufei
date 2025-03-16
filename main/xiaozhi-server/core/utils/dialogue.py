# 导入uuid模块，用于生成通用唯一识别码，为消息提供唯一标识
import uuid
# 从typing模块导入List和Dict，用于类型提示，增强代码的可读性和可维护性
from typing import List, Dict
# 从datetime模块导入datetime类，用于获取当前时间，记录对话时间
from datetime import datetime


class Message:
    def __init__(self, role: str, content: str = None, uniq_id: str = None, tool_calls = None, tool_call_id=None):
        """
        初始化Message类的实例，该类用于表示对话中的一条消息。

        :param role: 消息的角色，如 "user"（用户）、"assistant"（助手）、"system"（系统）等。
        :param content: 消息的具体内容，默认为None。
        :param uniq_id: 消息的唯一标识符，若未提供则使用uuid生成。
        """
        # 若未提供唯一标识符，则使用uuid生成一个
        self.uniq_id = uniq_id if uniq_id is not None else str(uuid.uuid4())
        # 消息的角色
        self.role = role
        # 消息的内容
        self.content = content
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id


class Dialogue:
    def __init__(self):
        """
        初始化Dialogue类的实例，该类用于管理对话。
        """
        # 存储对话消息的列表，每个元素为Message类的实例
        self.dialogue: List[Message] = []
        # 获取当前时间，并将其格式化为指定的字符串形式
        self.current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def put(self, message: Message):
        """
        向对话中添加一条消息。

        :param message: 要添加的消息，为Message类的实例。
        """
        # 将消息添加到对话列表中
        self.dialogue.append(message)

    def getMessages(self, m, dialogue):
        """
        根据消息对象 m 的不同属性，将其转换为特定格式的消息字典，并添加到对话列表 dialogue 中。

        :param m: 消息对象，该对象可能包含 role（角色）、tool_calls（工具调用信息）、tool_call_id（工具调用 ID）和 content（消息内容）等属性。
        :param dialogue: 对话列表，用于存储转换后的消息字典，以记录对话的历史信息。
        """
        # 检查消息对象 m 是否包含工具调用信息
        if m.tool_calls is not None:
            # 如果包含工具调用信息，将消息转换为包含角色和工具调用信息的字典，并添加到对话列表中
            dialogue.append({"role": m.role, "tool_calls": m.tool_calls})
        # 检查消息对象 m 的角色是否为 "tool"
        elif m.role == "tool":
            # 如果角色为 "tool"，将消息转换为包含角色、工具调用 ID 和消息内容的字典，并添加到对话列表中
            dialogue.append({"role": m.role, "tool_call_id": m.tool_call_id, "content": m.content})
        else:
            # 如果既没有工具调用信息，角色也不是 "tool"，将消息转换为包含角色和消息内容的字典，并添加到对话列表中
            dialogue.append({"role": m.role, "content": m.content})

    def get_llm_dialogue(self) -> List[Dict[str, str]]:
        """
        获取对话的列表形式，每个元素为一个字典，包含消息的角色和内容。

        :return: 包含对话消息的列表，每个元素为字典，键为 "role" 和 "content"。
        """
        # 初始化一个空列表，用于存储处理后的对话消息
        dialogue = []
        # 遍历对话列表中的每条消息
        for m in self.dialogue:
            # 将消息的角色和内容以字典形式添加到新列表中
            self.getMessages(m, dialogue)
        return dialogue

    def get_llm_dialogue_with_memory(self, memory_str: str = None) -> List[Dict[str, str]]:
        """
        获取带有记忆信息的对话列表。

        :param memory_str: 相关的记忆信息字符串，默认为None。
        :return: 包含对话消息的列表，若提供了记忆信息，会将其添加到系统消息中。
        """
        # 若未提供记忆信息或记忆信息为空字符串，则直接调用get_llm_dialogue方法获取对话列表
        if memory_str is None or len(memory_str) == 0:
            return self.get_llm_dialogue()

        # 初始化一个空列表，用于存储带记忆的对话消息
        dialogue = []

        # 查找对话列表中角色为 "system" 的系统消息
        system_message = next(
            (msg for msg in self.dialogue if msg.role == "system"), None
        )

        # 若存在系统消息
        if system_message:
            # 构建增强后的系统提示，将原系统消息内容和记忆信息拼接
            enhanced_system_prompt = (
                f"{system_message.content}\n\n"
                f"相关记忆：\n{memory_str}"
            )
            # 将增强后的系统消息以字典形式添加到对话列表中
            dialogue.append({"role": "system", "content": enhanced_system_prompt})

        # 遍历对话列表中的每条消息
        for m in self.dialogue:
            if m.role != "system":  # 跳过原始的系统消息
                self.getMessages(m, dialogue)

        return dialogue