# 导入os模块，用于与操作系统进行交互，例如检查文件是否存在、处理文件路径等操作
import os
# 导入sys模块，提供对Python解释器相关的变量和函数的访问，这里用于管理已导入的模块
import sys
# 从自定义配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging
# 导入importlib模块，用于动态导入Python模块，可根据类名动态创建类的实例
import importlib

# 调用设置日志的函数，获取日志记录器
logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    """
    此函数作为工厂方法，根据传入的类名动态创建TTS（Text-to-Speech，文本转语音）提供者的实例。

    :param class_name: 要创建实例的类名，对应于core/providers/tts目录下的Python文件名。
    :param args: 传递给类构造函数的位置参数。
    :param kwargs: 传递给类构造函数的关键字参数。
    :return: TTSProvider类的实例，用于将文本转换为语音。
    :raises ValueError: 若指定类名对应的Python文件不存在，则抛出此异常，提示用户检查配置。
    """
    # 创建TTS实例
    # 构建指定类名对应的Python文件的完整路径
    file_path = os.path.join('core', 'providers', 'tts', f'{class_name}.py')
    # 检查该文件是否存在
    if os.path.exists(file_path):
        # 若文件存在，构建要导入的模块名称
        lib_name = f'core.providers.tts.{class_name}'
        # 检查该模块是否已经导入
        if lib_name not in sys.modules:
            # 若未导入，则使用importlib动态导入该模块
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        # 从导入的模块中获取TTSProvider类，并使用传递的参数创建实例
        return sys.modules[lib_name].TTSProvider(*args, **kwargs)

    # 若指定类名对应的Python文件不存在，抛出异常提示用户检查配置
    raise ValueError(f"不支持的TTS类型: {class_name}，请检查该配置的type是否设置正确")