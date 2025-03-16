# 导入os模块，用于与操作系统进行交互，例如检查文件和目录是否存在、处理文件路径等
import os
# 导入sys模块，提供对Python解释器相关的变量和函数的访问，这里用于管理已导入的模块
import sys
# 导入importlib模块，用于动态导入Python模块，可根据类名动态创建类的实例
import importlib
# 从自定义配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging
# 从自定义工具模块中导入读取配置文件和获取项目目录的函数
from core.utils.util import read_config, get_project_dir

# 调用设置日志的函数，获取日志记录器
logger = setup_logging()

def create_instance(class_name, *args, **kwargs):
    """
    工厂方法，用于根据给定的类名动态创建MemoryProvider实例。

    :param class_name: 要创建实例的类名，对应于core/providers/memory目录下的特定文件夹和Python文件名。
    :param args: 传递给类构造函数的位置参数。
    :param kwargs: 传递给类构造函数的关键字参数。
    :return: MemoryProvider的实例，用于处理记忆服务相关的任务。
    :raises ValueError: 如果指定的类名对应的Python文件不存在，则抛出此异常。
    """
    # 构建指定类名对应的Python文件路径
    file_path = os.path.join('core', 'providers', 'memory', class_name, f'{class_name}.py')
    # 检查该文件是否存在
    if os.path.exists(file_path):
        # 构建要导入的模块名称
        lib_name = f'core.providers.memory.{class_name}.{class_name}'
        # 检查该模块是否已经导入
        if lib_name not in sys.modules:
            # 如果未导入，则使用importlib动态导入该模块
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        # 从导入的模块中获取MemoryProvider类，并使用传递的参数创建实例
        return sys.modules[lib_name].MemoryProvider(*args, **kwargs)

    # 如果指定的类名对应的Python文件不存在，抛出异常提示用户当前记忆服务类型不支持
    raise ValueError(f"不支持的记忆服务类型: {class_name}")