# 导入os模块，用于与操作系统进行交互，例如处理文件路径和目录
import os
# 导入sys模块，提供对Python解释器相关的变量和函数的访问，这里用于修改模块搜索路径
import sys

# 添加项目根目录到Python路径
# 获取当前脚本文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 从当前脚本文件所在目录向上两级，得到项目根目录的绝对路径
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
# 将项目根目录添加到Python模块搜索路径的开头，这样Python解释器就能优先从该目录查找模块
sys.path.insert(0, project_root)

# 从配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging
# 导入importlib模块，用于动态导入Python模块，可根据类名动态创建类的实例
import importlib

# 调用设置日志的函数，获取日志记录器
logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    """
    工厂方法，用于根据给定的类名动态创建LLMProvider实例。

    :param class_name: 要创建实例的类名，对应于core/providers/llm目录下的特定文件夹和Python文件名。
    :param args: 传递给类构造函数的位置参数。
    :param kwargs: 传递给类构造函数的关键字参数。
    :return: LLMProvider的实例，用于与大语言模型进行交互。
    :raises ValueError: 如果指定的类名对应的Python文件不存在，则抛出此异常。
    """
    # 构建指定类名对应的Python文件路径
    file_path = os.path.join('core', 'providers', 'llm', class_name, f'{class_name}.py')
    # 检查该文件是否存在
    if os.path.exists(file_path):
        # 构建要导入的模块名称
        lib_name = f'core.providers.llm.{class_name}.{class_name}'
        # 检查该模块是否已经导入
        if lib_name not in sys.modules:
            # 如果未导入，则使用importlib动态导入该模块
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        # 从导入的模块中获取LLMProvider类，并使用传递的参数创建实例
        return sys.modules[lib_name].LLMProvider(*args, **kwargs)

    # 如果指定的类名对应的Python文件不存在，抛出异常提示用户检查配置
    raise ValueError(f"不支持的LLM类型: {class_name}，请检查该配置的type是否设置正确")