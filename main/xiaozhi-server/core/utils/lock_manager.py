# 导入asyncio模块，用于支持异步编程，实现异步锁的功能
import asyncio
# 从typing模块导入Dict，用于类型提示，明确表示变量的类型为字典
from typing import Dict
# 从自定义配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging

# 获取当前模块的名称作为标签，用于在日志记录中标识来源
TAG = __name__
# 调用设置日志的函数，获取日志记录器
logger = setup_logging()

class FileLockManager:
    # 类属性，用于存储单例实例
    _instance = None
    # 类属性，用于存储文件路径和对应的异步锁的映射关系
    _locks: Dict[str, asyncio.Lock] = {}

    def __new__(cls):
        """
        重写__new__方法，实现单例模式。

        单例模式确保一个类只有一个实例，并提供一个全局访问点。
        """
        # 检查单例实例是否已经存在
        if cls._instance is None:
            # 如果不存在，则创建一个新的实例
            cls._instance = super(FileLockManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_lock(cls, file_path: str) -> asyncio.Lock:
        """
        获取指定文件的异步锁。

        如果该文件路径对应的锁不存在，则创建一个新的异步锁并存储在_locks字典中。

        :param file_path: 文件的路径
        :return: 该文件对应的异步锁
        """
        # 检查文件路径是否已经存在于_locks字典中
        if file_path not in cls._locks:
            # 如果不存在，则为该文件路径创建一个新的异步锁
            cls._locks[file_path] = asyncio.Lock()
        # 返回该文件路径对应的异步锁
        return cls._locks[file_path]

    @classmethod
    async def acquire_lock(cls, file_path: str):
        """
        获取指定文件的锁。

        调用get_lock方法获取锁，并使用await关键字异步地获取该锁。
        成功获取锁后，记录调试日志。

        :param file_path: 文件的路径
        """
        # 获取指定文件的异步锁
        lock = cls.get_lock(file_path)
        # 异步地获取锁
        await lock.acquire()
        # 记录调试日志，表明已成功获取指定文件的锁
        logger.bind(tag=TAG).debug(f"Acquired lock for {file_path}")

    @classmethod
    def release_lock(cls, file_path: str):
        """
        释放指定文件的锁。

        检查文件路径是否存在于_locks字典中，如果存在则尝试释放锁。
        若释放锁时出现RuntimeError异常，记录警告日志。

        :param file_path: 文件的路径
        """
        # 检查文件路径是否存在于_locks字典中
        if file_path in cls._locks:
            try:
                # 尝试释放该文件路径对应的锁
                cls._locks[file_path].release()
                # 记录调试日志，表明已成功释放指定文件的锁
                logger.bind(tag=TAG).debug(f"Released lock for {file_path}")
            except RuntimeError as e:
                # 若释放锁时出现RuntimeError异常，记录警告日志
                logger.bind(tag=TAG).warning(f"Failed to release lock for {file_path}: {e}")