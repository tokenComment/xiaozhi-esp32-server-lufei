# 从 importlib.metadata 模块导入 version 函数，该函数用于获取指定包的版本信息
from importlib.metadata import version

try:
    # 尝试获取当前模块的版本号，并将其赋值给 __version__ 变量
    # __name__ 是 Python 中的一个内置变量，代表当前模块的名称
    __version__ = version(__name__)
except:
    # 如果在获取版本号时发生异常（例如模块未正确安装等情况），则不做任何处理
    # 这里使用了一个空的 except 块来捕获所有异常，不进行具体的错误处理，只是简单忽略
    pass

# 从 silero_vad 包的 model 模块导入 load_silero_vad 函数
# load_silero_vad 函数用于加载 Silero 语音活动检测（VAD）模型
from silero_vad.model import load_silero_vad

# 从 silero_vad 包的 utils_vad 模块导入多个实用函数和类
# get_speech_timestamps 函数用于从音频数据中获取语音片段的时间戳
from silero_vad.utils_vad import (get_speech_timestamps,
                                  # save_audio 函数用于将音频数据保存为文件
                                  save_audio,
                                  # read_audio 函数用于读取音频文件并返回音频数据
                                  read_audio,
                                  # VADIterator 类用于迭代处理音频数据进行语音活动检测
                                  VADIterator,
                                  # collect_chunks 函数用于从音频数据中收集语音片段
                                  collect_chunks)