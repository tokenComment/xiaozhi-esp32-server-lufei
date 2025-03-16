# 导入importlib模块，用于动态导入Python模块，实现根据配置动态创建类实例
import importlib
# 导入logging模块，用于记录程序运行过程中的信息，便于调试和监控
import logging
# 导入os模块，用于与操作系统进行交互，如文件和目录操作
import os
# 导入sys模块，提供对Python解释器相关的变量和函数的访问，这里用于检查模块是否已导入
import sys
# 导入time模块，提供时间相关的功能，不过此代码中未实际使用
import time
# 导入wave模块，用于处理WAV格式的音频文件，此代码中未实际使用
import wave
# 导入uuid模块，用于生成通用唯一识别码，此代码中未实际使用
import uuid
# 从abc模块导入ABC和abstractmethod，用于定义抽象基类和抽象方法
from abc import ABC, abstractmethod
# 从typing模块导入Optional、Tuple和List，用于类型提示，提高代码的可读性和可维护性
from typing import Optional, Tuple, List
# 从自定义模块中导入ASR提供者的基类，后续创建的实例将继承该基类
from core.providers.asr.base import ASRProviderBase
# 从自定义配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging

# 获取当前模块的名称作为标签，用于在日志记录中标识来源
TAG = __name__
# 调用设置日志的函数，获取日志记录器
logger = setup_logging()

def create_instance(class_name: str, *args, **kwargs) -> ASRProviderBase:
    """
    工厂方法，用于根据给定的类名动态创建ASR（自动语音识别）提供者的实例。

    :param class_name: 要创建实例的类名，对应于core/providers/asr目录下的Python文件名。
    :param args: 传递给类构造函数的位置参数。
    :param kwargs: 传递给类构造函数的关键字参数。
    :return: ASRProviderBase的子类实例，实现具体的自动语音识别功能。
    :raises ValueError: 如果指定的类名对应的Python文件不存在，则抛出此异常。
    """
    # 构建指定类名对应的Python文件路径
    file_path = os.path.join('core', 'providers', 'asr', f'{class_name}.py')
    # 检查该文件是否存在
    if os.path.exists(file_path):
        # 构建要导入的模块名称
        lib_name = f'core.providers.asr.{class_name}'
        # 检查该模块是否已经导入
        if lib_name not in sys.modules:
            # 如果未导入，则使用importlib动态导入该模块
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        # 从导入的模块中获取ASRProvider类，并使用传递的参数创建实例
        return sys.modules[lib_name].ASRProvider(*args, **kwargs)

    # 如果指定的类名对应的Python文件不存在，抛出异常提示用户检查配置
    raise ValueError(f"不支持的ASR类型: {class_name}，请检查该配置的type是否设置正确")