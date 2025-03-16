# 从当前包的 utils_vad 模块中导入 init_jit_model 函数和 OnnxWrapper 类
# init_jit_model 用于初始化 JIT 模型，OnnxWrapper 用于封装 ONNX 模型
from .utils_vad import init_jit_model, OnnxWrapper
# 导入 PyTorch 库
import torch
# 设置 PyTorch 使用的线程数为 1，以控制模型推理时的并行度
torch.set_num_threads(1)

# 定义一个名为 load_silero_vad 的函数，用于加载 Silero 语音活动检测（VAD）模型
# onnx 参数表示是否使用 ONNX 格式的模型，默认为 False
# opset_version 参数表示 ONNX 操作集的版本，默认为 16
def load_silero_vad(onnx=False, opset_version=16):
    # 定义可用的 ONNX 操作集版本列表
    available_ops = [15, 16]
    # 如果选择使用 ONNX 模型，并且指定的操作集版本不在可用列表中
    if onnx and opset_version not in available_ops:
        # 抛出异常，提示用户可用的操作集版本
        raise Exception(f'Available ONNX opset_version: {available_ops}')

    # 如果选择使用 ONNX 模型
    if onnx:
        # 根据指定的操作集版本选择对应的模型文件名
        if opset_version == 16:
            model_name = 'silero_vad.onnx'
        else:
            model_name = f'silero_vad_16k_op{opset_version}.onnx'
    else:
        # 如果不使用 ONNX 模型，使用 JIT 格式的模型文件名
        model_name = 'silero_vad.jit'
    # 定义模型所在的包路径
    package_path = "silero_vad.data"

    try:
        # 尝试使用 importlib_resources 库来获取模型文件的路径
        import importlib_resources as impresources
        model_file_path = str(impresources.files(package_path).joinpath(model_name))
    except:
        # 如果 importlib_resources 不可用，使用 importlib.resources 库
        from importlib import resources as impresources
        try:
            # 使用 with 语句获取模型文件的路径
            with impresources.path(package_path, model_name) as f:
                model_file_path = f
        except:
            # 如果上述方法都失败，再次尝试使用 importlib.resources 库获取路径
            model_file_path = str(impresources.files(package_path).joinpath(model_name))

    # 如果选择使用 ONNX 模型
    if onnx:
        # 使用 OnnxWrapper 类封装 ONNX 模型，并强制在 CPU 上运行
        model = OnnxWrapper(model_file_path, force_onnx_cpu=True)
    else:
        # 如果不使用 ONNX 模型，使用 init_jit_model 函数初始化 JIT 模型
        model = init_jit_model(model_file_path)

    # 返回加载好的模型
    return model