import traceback

# 从上级目录的 base 模块导入 MemoryProviderBase 类和 logger 对象
from ..base import MemoryProviderBase, logger
# 从 mem0 模块导入 MemoryClient 类
from mem0 import MemoryClient
# 从 core.utils.util 模块导入 check_model_key 函数
from core.utils.util import check_model_key

# 获取当前模块的名称，作为日志标签
TAG = __name__

class MemoryProvider(MemoryProviderBase):
    def __init__(self, config):
        # 调用父类的构造函数进行初始化
        super().__init__(config)
        # 从配置中获取 API 密钥，如果没有则默认为空字符串
        self.api_key = config.get("api_key", "")
        # 从配置中获取 API 版本，如果没有则默认为 "v1.1"
        self.api_version = config.get("api_version", "v1.1")
        # 检查 Mem0ai 的 API 密钥是否有效
        have_key = check_model_key("Mem0ai", self.api_key)
        # 如果 API 密钥无效
        if not have_key :
            # 标记不使用 Mem0ai 服务
            self.use_mem0 = False
            return
        else:
            # 标记使用 Mem0ai 服务
            self.use_mem0 = True
        try:
            # 创建 MemoryClient 实例，使用获取到的 API 密钥
            self.client = MemoryClient(api_key=self.api_key)
            # 记录成功连接到 Mem0ai 服务的日志
            logger.bind(tag=TAG).info("成功连接到 Mem0ai 服务")
        except Exception as e:
            # 记录连接到 Mem0ai 服务时发生错误的日志
            logger.bind(tag=TAG).error(f"连接到 Mem0ai 服务时发生错误: {str(e)}")
            # 记录详细的错误堆栈信息
            logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")
            # 标记不使用 Mem0ai 服务
            self.use_mem0 = False

    async def save_memory(self, msgs):
        # 如果不使用 Mem0ai 服务，直接返回 None
        if not self.use_mem0:
            return None
        # 如果消息列表的长度小于 2，直接返回 None
        if len(msgs) < 2:
            return None
        
        try:
            # 将消息列表转换为适合 Mem0ai 服务的格式
            messages = [
                {"role": message.role, "content": message.content}
                for message in msgs if message.role != "system"
            ]
            # 调用 MemoryClient 的 add 方法保存记忆
            result = self.client.add(messages, user_id=self.role_id, output_format=self.api_version)
            # 记录保存记忆的结果
            logger.bind(tag=TAG).debug(f"Save memory result: {result}")
        except Exception as e:
            # 记录保存记忆失败的日志
            logger.bind(tag=TAG).error(f"保存记忆失败: {str(e)}")
            return None

    async def query_memory(self, query: str)-> str:
        # 如果不使用 Mem0ai 服务，直接返回空字符串
        if not self.use_mem0:
            return ""
        try:
            # 调用 MemoryClient 的 search 方法查询记忆
            results = self.client.search(
                query,
                user_id=self.role_id,
                output_format=self.api_version
            )
            # 如果查询结果为空或者不包含 'results' 字段，返回空字符串
            if not results or 'results' not in results:
                return ""
                
            # 用于存储格式化后的记忆条目
            memories = []
            # 遍历查询结果中的每个记忆条目
            for entry in results['results']:
                # 获取记忆条目的更新时间戳
                timestamp = entry.get('updated_at', '')
                if timestamp:
                    try:
                        # 去除时间戳中的毫秒部分
                        dt = timestamp.split('.')[0]
                        # 将时间戳中的 'T' 替换为空格
                        formatted_time = dt.replace('T', ' ')
                    except:
                        # 如果处理时间戳时出错，使用原始时间戳
                        formatted_time = timestamp
                # 获取记忆条目的内容
                memory = entry.get('memory', '')
                # 如果时间戳和记忆内容都存在
                if timestamp and memory:
                    # 将时间戳和格式化后的记忆内容作为元组添加到 memories 列表中
                    memories.append((timestamp, f"[{formatted_time}] {memory}"))
            
            # 按照时间戳降序排序，最新的记忆排在前面
            memories.sort(key=lambda x: x[0], reverse=True)
            
            # 将格式化后的记忆条目转换为字符串，每个条目用换行符分隔
            memories_str = "\n".join(f"- {memory[1]}" for memory in memories)
            # 记录查询结果
            logger.bind(tag=TAG).debug(f"Query results: {memories_str}")
            return memories_str
        except Exception as e:
            # 记录查询记忆失败的日志
            logger.bind(tag=TAG).error(f"查询记忆失败: {str(e)}")
            return ""