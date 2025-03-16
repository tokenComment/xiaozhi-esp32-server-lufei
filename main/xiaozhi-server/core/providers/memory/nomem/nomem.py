'''
不使用记忆，可以选择此模块
'''
# 从上级目录的 base 模块导入 MemoryProviderBase 类和 logger 对象
from ..base import MemoryProviderBase, logger

# 获取当前模块的名称，作为日志标签
TAG = __name__

class MemoryProvider(MemoryProviderBase):
    def __init__(self, config):
        # 调用父类的构造函数进行初始化
        super().__init__(config)
      
    async def save_memory(self, msgs):
        # 记录调试日志，表明处于无记忆模式，不执行记忆保存操作
        logger.bind(tag=TAG).debug("nomem mode: No memory saving is performed.")
        # 直接返回 None，表示未执行保存操作
        return None

    async def query_memory(self, query: str)-> str:
        # 记录调试日志，表明处于无记忆模式，不执行记忆查询操作
        logger.bind(tag=TAG).debug("nomem mode: No memory query is performed.")
        # 直接返回空字符串，表示未查询到任何记忆
        return ""