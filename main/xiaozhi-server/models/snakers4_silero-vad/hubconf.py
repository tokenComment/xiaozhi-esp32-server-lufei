# 定义该模块所依赖的库
dependencies = ['torch', 'torchaudio']
# 导入 PyTorch 库，用于深度学习任务
import torch
# 导入 os 模块，用于与操作系统进行交互，如文件和目录操作
import os
# 导入 sys 模块，提供对 Python 解释器相关变量和函数的访问
import sys
# 将当前脚本所在目录下的 src 目录添加到系统路径中，以便后续可以导入该目录下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
# 从 silero_vad 包的 utils_vad 模块中导入所需的函数和类
from silero_vad.utils_vad import (init_jit_model,
                                  get_speech_timestamps,
                                  save_audio,
                                  read_audio,
                                  VADIterator,
                                  collect_chunks,
                                  OnnxWrapper)

def versiontuple(v):
    """
    将版本号字符串转换为元组形式，方便版本比较。

    参数:
    - v: 版本号字符串，例如 '1.12.0+cu113'。

    返回:
    - 版本号元组，例如 (1, 12, 0)。
    """
    # 处理版本号字符串，去除可能存在的后缀（如 '+cu113'），并按 '.' 分割成列表
    splitted = v.split('+')[0].split(".")
    # 用于存储处理后的版本号部分
    version_list = []
    # 遍历分割后的版本号列表
    for i in splitted:
        try:
            # 尝试将版本号部分转换为整数
            version_list.append(int(i))
        except:
            # 若转换失败，将该部分设为 0
            version_list.append(0)
    # 将列表转换为元组并返回
    return tuple(version_list)

def silero_vad(onnx=False, force_onnx_cpu=False, opset_version=16):
    """
    Silero 语音活动检测器。
    返回一个模型和一组实用工具函数。
    请参考 https://github.com/snakers4/silero-vad 查看使用示例。

    参数:
    - onnx: 是否使用 ONNX 格式的模型，默认为 False。
    - force_onnx_cpu: 是否强制使用 CPU 运行 ONNX 模型，默认为 False。
    - opset_version: ONNX 操作集版本，默认为 16。

    返回:
    - 模型和实用工具函数的元组。
    """
    # 定义可用的 ONNX 操作集版本列表
    available_ops = [15, 16]
    # 检查是否使用 ONNX 模型且指定的操作集版本不在可用列表中
    if onnx and opset_version not in available_ops:
        # 若不满足条件，抛出异常提示可用的操作集版本
        raise Exception(f'Available ONNX opset_version: {available_ops}')

    # 若不使用 ONNX 模型
    if not onnx:
        # 获取当前安装的 PyTorch 版本
        installed_version = torch.__version__
        # 定义支持的最小 PyTorch 版本
        supported_version = '1.12.0'
        # 比较当前安装版本和支持版本
        if versiontuple(installed_version) < versiontuple(supported_version):
            # 若当前版本低于支持版本，抛出异常提示安装更高版本
            raise Exception(f'Please install torch {supported_version} or greater ({installed_version} installed)')

    # 获取模型所在的目录路径
    model_dir = os.path.join(os.path.dirname(__file__), 'src', 'silero_vad', 'data')
    # 若使用 ONNX 模型
    if onnx:
        if opset_version == 16:
            # 若操作集版本为 16，使用默认的 ONNX 模型文件名
            model_name = 'silero_vad.onnx'
        else:
            # 否则，根据操作集版本生成对应的模型文件名
            model_name = f'silero_vad_16k_op{opset_version}.onnx'
        # 实例化 OnnxWrapper 类，加载 ONNX 模型
        model = OnnxWrapper(os.path.join(model_dir, model_name), force_onnx_cpu)
    else:
        # 若不使用 ONNX 模型，调用 init_jit_model 函数加载 JIT 模型
        model = init_jit_model(os.path.join(model_dir, 'silero_vad.jit'))
    # 定义一组实用工具函数，用于语音活动检测相关操作
    utils = (get_speech_timestamps,
             save_audio,
             read_audio,
             VADIterator,
             collect_chunks)

    # 返回加载的模型和实用工具函数的元组
    return model, utils