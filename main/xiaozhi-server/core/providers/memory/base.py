# 导入 ABC（抽象基类）和 abstractmethod 装饰器，用于定义抽象基类和抽象方法
from abc import ABC, abstractmethod
# 从 config.logger 模块导入 setup_logging 函数，用于设置日志
from config.logger import setup_logging

# 获取当前模块的名称，作为日志标签
TAG = __name__
# 调用 setup_logging 函数来设置日志，并将返回的日志记录器赋值给 logger 变量
logger = setup_logging()

# 定义一个抽象基类 MemoryProviderBase，继承自 ABC
class MemoryProviderBase(ABC):
    def __init__(self, config):
        # 将传入的配置信息保存到实例属性中
        self.config = config
        # 初始化角色 ID 为 None
        self.role_id = None
        # 初始化大语言模型实例为 None
        self.llm = None

    # 定义一个抽象方法 save_memory，使用 async 关键字表示这是一个异步方法
    @abstractmethod
    async def save_memory(self, msgs):
        """
        保存特定角色的新记忆，并返回记忆 ID
        :param msgs: 包含记忆信息的消息列表
        """
        # 这里只是一个示例打印，实际实现需要在子类中完成
        print("this is base func", msgs)

    # 定义一个抽象方法 query_memory，使用 async 关键字表示这是一个异步方法
    @abstractmethod
    async def query_memory(self, query: str) -> str:
        """
        根据相似度查询特定角色的记忆
        :param query: 查询的字符串
        :return: 查询到的记忆内容字符串
        """
        # 这里只是一个示例返回，实际实现需要在子类中完成
        return "please implement query method"

    def init_memory(self, role_id, llm):
        """
        初始化记忆相关的角色 ID 和大语言模型实例
        :param role_id: 角色的 ID
        :param llm: 大语言模型的实例
        """
        # 将传入的角色 ID 赋值给实例属性
        self.role_id = role_id    
        # 将传入的大语言模型实例赋值给实例属性
        self.llm = llm