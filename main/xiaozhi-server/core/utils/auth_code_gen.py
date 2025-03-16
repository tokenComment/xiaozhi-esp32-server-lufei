# 导入random模块，用于生成随机数，这里用于生成认证码
import random
# 导入threading模块，用于实现多线程编程，确保在多线程环境下代码的线程安全
import threading
# 导入time模块，用于获取当前时间戳，在生成随机数种子、记录认证码生成时间和清理过期认证码时会用到
import time
# 从typing模块导入Set，用于类型提示，明确表示变量的类型为集合
from typing import Set

class AuthCodeGenerator:
    # 类属性，用于存储单例实例
    _instance = None
    # 类属性，用于线程安全的锁，确保在多线程环境下只有一个线程能创建实例
    _instance_lock = threading.Lock()

    def __new__(cls):
        """
        重写__new__方法，实现单例模式。

        单例模式确保一个类只有一个实例，并提供一个全局访问点。
        在多线程环境下，使用锁机制保证线程安全。
        """
        # 检查单例实例是否已经存在
        if not cls._instance:
            # 使用锁确保在多线程环境下只有一个线程能创建实例
            with cls._instance_lock:
                # 再次检查实例是否存在，防止多个线程同时通过第一次检查
                if not cls._instance:
                    # 创建新的实例
                    cls._instance = super(AuthCodeGenerator, cls).__new__(cls)
                    # 初始化随机种子，使用当前时间戳，确保每次程序运行时随机数不同
                    random.seed(time.time())
        return cls._instance

    def __init__(self):
        """
        初始化方法，确保只被调用一次。

        初始化用于存储已使用认证码、认证码生成时间的集合和字典，
        以及用于线程安全的锁和认证码过期时间。
        """
        # 确保__init__只被调用一次
        if not hasattr(self, '_initialized'):
            # 用于存储已使用的认证码
            self._used_codes: Set[str] = set()
            # 用于存储每个认证码的生成时间戳
            self._code_timestamps = {}
            # 用于线程安全的锁，确保在多线程环境下对共享资源的操作是安全的
            self._lock = threading.Lock()
            # 认证码的过期时间，这里设置为3天（以秒为单位）
            self._code_timeout = 3 * 24 * 60 * 60
            # 标记已初始化
            self._initialized = True

    @classmethod
    def get_instance(cls):
        """
        获取AuthCodeGenerator的单例实例。

        返回:
            AuthCodeGenerator: 单例实例
        """
        return cls()

    def generate_code(self) -> str:
        """
        生成6位数字认证码，确保不重复。

        每次生成认证码前会清理过期的认证码，使用时间戳和已用码数量作为随机数种子，
        确保生成的认证码不重复。

        返回:
            str: 6位数字字符串形式的认证码
        """
        # 使用锁确保在多线程环境下对共享资源的操作是安全的
        with self._lock:
            # 清理过期的认证码
            self._clean_expired_codes()
            while True:
                # 使用时间戳和已用码数量作为种子，确保每次生成不同的随机数
                seed = int(time.time() * 1000) + len(self._used_codes)
                random.seed(seed)
                # 生成6位随机数字
                code = ''.join(str(random.randint(0, 9)) for _ in range(6))
                # 检查生成的认证码是否已经存在
                if code not in self._used_codes:
                    # 将未使用过的认证码添加到已使用集合中
                    self._used_codes.add(code)
                    # 记录该认证码的生成时间
                    self._code_timestamps[code] = time.time()
                    return code

    def remove_code(self, code: str) -> bool:
        """
        删除已使用的认证码。

        参数:
            code (str): 要删除的认证码

        返回:
            bool: 删除成功返回True，码不存在返回False
        """
        print('remove_code', code)
        # 使用锁确保在多线程环境下对共享资源的操作是安全的
        with self._lock:
            # 检查认证码是否存在于已使用集合中
            if code in self._used_codes:
                # 从已使用集合中移除该认证码
                self._used_codes.remove(code)
                # 检查该认证码的生成时间是否存在于字典中
                if code in self._code_timestamps:
                    # 从字典中删除该认证码的生成时间记录
                    del self._code_timestamps[code]
                return True
            return False

    def is_code_used(self, code: str) -> bool:
        """
        检查认证码是否已被使用。

        参数:
            code (str): 要检查的认证码

        返回:
            bool: 如果码存在返回True，否则返回False
        """
        # 使用锁确保在多线程环境下对共享资源的操作是安全的
        with self._lock:
            # 检查认证码是否存在于已使用集合中
            return code in self._used_codes

    def clear_codes(self):
        """
        清空所有已使用的认证码。

        清空已使用认证码集合和认证码生成时间字典。
        """
        # 使用锁确保在多线程环境下对共享资源的操作是安全的
        with self._lock:
            # 清空已使用认证码集合
            self._used_codes.clear()
            # 清空认证码生成时间字典
            self._code_timestamps.clear()

    def _clean_expired_codes(self):
        """
        清理过期的认证码。

        根据当前时间和认证码的生成时间，找出过期的认证码并从集合和字典中移除。
        """
        # 获取当前时间戳
        current_time = time.time()
        # 找出所有过期的认证码
        expired_codes = [
            code for code, timestamp in self._code_timestamps.items()
            if (current_time - timestamp) > self._code_timeout
        ]
        # 遍历过期的认证码
        for code in expired_codes:
            # 从已使用集合中移除过期的认证码
            self._used_codes.remove(code)
            # 从字典中删除过期认证码的生成时间记录
            del self._code_timestamps[code]