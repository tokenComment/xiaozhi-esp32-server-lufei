import torch
import torchaudio
from typing import Callable, List
import warnings

# 支持的语言列表
languages = ['ru', 'en', 'de', 'es']

class OnnxWrapper():
    """
    ONNX模型封装类，用于加载和运行ONNX格式的语音活动检测（VAD）模型。
    """

    def __init__(self, path, force_onnx_cpu=False):
        """
    初始化ONNX模型封装类。

    参数:
    - path: ONNX模型文件的路径。
    - force_onnx_cpu: 是否强制使用CPU进行推理。
        """
        # 导入numpy库，用于处理数值计算和数组操作
        import numpy as np
        # 导入onnxruntime库，用于运行ONNX模型
        import onnxruntime

        # 设置ONNX运行时的选项，创建一个SessionOptions对象
        # 该对象用于配置ONNX推理会话的相关参数
        opts = onnxruntime.SessionOptions()
        # 设置会话的线程间操作线程数为1，即限制并行处理的线程数量
        # 这样可以避免多线程带来的性能开销，优化单线程性能
        opts.inter_op_num_threads = 1
        # 设置会话的线程内操作线程数为1，进一步优化单线程性能
        opts.intra_op_num_threads = 1

        # 判断是否需要强制使用CPU进行推理，并且检查CPU执行提供者是否可用
        if force_onnx_cpu and 'CPUExecutionProvider' in onnxruntime.get_available_providers():
            # 如果满足条件，使用CPU执行提供者加载ONNX模型
            # 传入模型路径、指定提供者为CPUExecutionProvider和会话选项
            self.session = onnxruntime.InferenceSession(path, providers=['CPUExecutionProvider'], sess_options=opts)
        else:
            # 如果不满足条件，使用默认的提供者加载ONNX模型
            # 只传入模型路径和会话选项
            self.session = onnxruntime.InferenceSession(path, sess_options=opts)

        # 调用reset_states方法，重置模型的状态
        # 该方法通常用于初始化模型的内部状态变量
        self.reset_states()
        # 检查模型路径中是否包含'16k'字符串
        if '16k' in path:
            # 如果包含，发出警告提示该模型仅支持16000的采样率
            warnings.warn('This model support only 16000 sampling rate!')
            # 设置支持的采样率列表为仅包含16000
            self.sample_rates = [16000]
        else:
            # 如果不包含，设置支持的采样率列表为8000和16000
            self.sample_rates = [8000, 16000]

    def _validate_input(self, x, sr: int):
        """
    验证输入音频数据的有效性，并进行必要的预处理。

    参数:
    - x: 输入的音频数据。
    - sr: 采样率。

    返回:
    - 处理后的音频数据和采样率。
        """
        # 检查输入音频数据的维度，如果是一维的，为其增加一个维度
        # 通常是为了将单声道音频数据转换为符合模型输入要求的二维张量形式（批量维度和音频数据维度）
        if x.dim() == 1:
            x = x.unsqueeze(0)
        # 检查输入音频数据的维度，如果维度大于2，说明输入音频的维度过多不符合要求
        # 此时抛出ValueError异常，并提示输入音频块的维度情况
        if x.dim() > 2:
            raise ValueError(f"Too many dimensions for input audio chunk {x.dim()}")

        # 如果采样率不是16000且是16000的倍数，进行下采样操作
        # 这样可以将高采样率的音频数据转换为模型支持的16000采样率
        if sr != 16000 and (sr % 16000 == 0):
            # 计算下采样的步长，即每隔多少个样本取一个样本
            step = sr // 16000
            # 对音频数据进行下采样操作
            x = x[:,::step]
            # 将采样率更新为16000
            sr = 16000

        # 检查当前采样率是否在模型支持的采样率列表中
        # 如果不在列表中，说明该采样率不被支持，抛出ValueError异常并提示支持的采样率情况
        if sr not in self.sample_rates:
            raise ValueError(f"Supported sampling rates: {self.sample_rates} (or multiply of 16000)")
        # 检查输入音频块的长度是否过短
        # 通过采样率与音频数据长度的比例来判断，如果比例大于31.25，说明音频块过短
        # 此时抛出ValueError异常并提示输入音频块过短
        if sr / x.shape[1] > 31.25:
            raise ValueError("Input audio chunk is too short")

        # 返回处理后的音频数据和采样率
        return x, sr

    def reset_states(self, batch_size=1):
        """
    重置模型的状态。

    参数:
    - batch_size: 批量大小。
        """
        # 初始化模型的隐藏状态
        # 创建一个形状为 (2, batch_size, 128) 的全零张量，并将其数据类型设置为 float
        # 这里的 2 可能代表某种双向结构（如双向 RNN）的两个方向
        # batch_size 表示一次处理的样本数量
        # 128 是隐藏状态的维度
        self._state = torch.zeros((2, batch_size, 128)).float()
        # 初始化上下文张量，将其设置为长度为 0 的零张量
        # 上下文张量可能用于存储之前处理的音频片段的相关信息
        self._context = torch.zeros(0)
        # 重置上一次使用的采样率为 0
        # 这个变量用于记录上一次处理音频时的采样率
        self._last_sr = 0
        # 重置上一次使用的批量大小为 0
        # 这个变量用于记录上一次处理音频时的批量大小
        self._last_batch_size = 0

    def __call__(self, x, sr: int):
        """
    对输入的音频数据进行推理。

    参数:
    - x: 输入的音频数据。
    - sr: 采样率。

    返回:
    - 推理结果。
        """
        # 调用 _validate_input 方法验证输入音频数据的有效性，并进行必要的预处理
        # 确保输入数据符合模型的要求，同时获取处理后的音频数据和采样率
        x, sr = self._validate_input(x, sr)
        # 根据采样率确定每个音频块应包含的样本数量
        # 若采样率为 16000，则每个音频块包含 512 个样本；否则为 256 个样本
        num_samples = 512 if sr == 16000 else 256

        # 检查输入音频数据的最后一个维度（即样本数量）是否符合要求
        # 如果不符合，抛出 ValueError 异常，提示用户提供的样本数量不支持
        if x.shape[-1] != num_samples:
            raise ValueError(f"Provided number of samples is {x.shape[-1]} (Supported values: 256 for 8000 sample rate, 512 for 16000)")

        # 获取输入音频数据的批量大小，即一次处理的音频片段数量
        batch_size = x.shape[0]
        # 根据采样率确定上下文的大小
        # 若采样率为 16000，上下文大小为 64；否则为 32
        context_size = 64 if sr == 16000 else 32

        # 根据输入的变化重置状态
        # 如果上一次的批量大小为 0，说明是首次处理，调用 reset_states 方法重置模型状态
        if not self._last_batch_size:
            self.reset_states(batch_size)
        # 如果上一次的采样率不为 0 且与当前采样率不同，说明采样率发生了变化，重置模型状态
        if (self._last_sr) and (self._last_sr != sr):
            self.reset_states(batch_size)
        # 如果上一次的批量大小不为 0 且与当前批量大小不同，说明批量大小发生了变化，重置模型状态
        if (self._last_batch_size) and (self._last_batch_size != batch_size):
            self.reset_states(batch_size)

        # 如果上下文为空，初始化上下文张量
        # 创建一个形状为 (batch_size, context_size) 的全零张量作为初始上下文
        if not len(self._context):
            self._context = torch.zeros(batch_size, context_size)

        # 将上下文与输入数据拼接
        # 在维度 1 上进行拼接，将上下文信息添加到输入音频数据之前
        x = torch.cat([self._context, x], dim=1)
        # 检查采样率是否为 8000 或 16000
        # 只有这两种采样率是模型支持的
        if sr in [8000, 16000]:
            # 准备 ONNX 输入
            # 将输入音频数据、模型状态和采样率转换为 NumPy 数组，并存储在字典中
            ort_inputs = {'input': x.numpy(), 'state': self._state.numpy(), 'sr': np.array(sr, dtype='int64')}
            # 调用 ONNX 会话的 run 方法进行推理
            # 传入输出名称（这里为 None，表示获取所有输出）和输入数据字典
            ort_outs = self.session.run(None, ort_inputs)
            # 从推理结果中解包输出和新的模型状态
            out, state = ort_outs
            # 将新的模型状态从 NumPy 数组转换为 PyTorch 张量
            self._state = torch.from_numpy(state)
        else:
            # 如果采样率不支持，抛出 ValueError 异常
            raise ValueError()

        # 更新上下文和状态
        # 取拼接后数据的最后 context_size 个样本作为新的上下文
        self._context = x[..., -context_size:]
        # 记录当前使用的采样率
        self._last_sr = sr
        # 记录当前使用的批量大小
        self._last_batch_size = batch_size

        # 将推理输出从 NumPy 数组转换为 PyTorch 张量
        out = torch.from_numpy(out)
        # 返回推理结果
        return out

    def audio_forward(self, x, sr: int):
        """
    对长音频进行分段推理。

    参数:
    - x: 输入的音频数据。
    - sr: 采样率。

    返回:
    - 分段推理结果。
        """
        # 用于存储每个音频分段的推理结果
        outs = []
        # 调用 _validate_input 方法验证输入音频数据的有效性，并进行必要的预处理
        # 确保输入数据符合模型的要求，同时获取处理后的音频数据和采样率
        x, sr = self._validate_input(x, sr)
        # 重置模型的状态，为推理做准备
        self.reset_states()
        # 根据采样率确定每个音频分段应包含的样本数量
        # 若采样率为 16000，则每个音频分段包含 512 个样本；否则为 256 个样本
        num_samples = 512 if sr == 16000 else 256

        # 对音频进行填充以确保长度是 num_samples 的倍数
        # 检查音频数据的长度是否不是 num_samples 的整数倍
        if x.shape[1] % num_samples:
            # 计算需要填充的样本数量，使得音频长度能被 num_samples 整除
            pad_num = num_samples - (x.shape[1] % num_samples)
            # 使用 PyTorch 的函数对音频数据进行填充，在右侧填充零值
            x = torch.nn.functional.pad(x, (0, pad_num), 'constant', value=0.0)

        # 分段推理
        # 遍历音频数据，每次取长度为 num_samples 的分段
        for i in range(0, x.shape[1], num_samples):
            # 从音频数据中提取当前分段
            wavs_batch = x[:, i:i+num_samples]
            # 调用 __call__ 方法对当前音频分段进行推理
            out_chunk = self.__call__(wavs_batch, sr)
            # 将当前分段的推理结果添加到 outs 列表中
            outs.append(out_chunk)

        # 将分段结果拼接
        # 沿着维度 1 将所有分段的推理结果拼接成一个张量
        stacked = torch.cat(outs, dim=1)
        # 将拼接后的结果移动到 CPU 上，并返回
        return stacked.cpu()

class Validator():
    """
    模型验证类，用于加载和验证ONNX或JIT格式的模型。
    """

    def __init__(self, url, force_onnx_cpu):
        """
    初始化模型验证类。

    参数:
    - url: 模型文件的URL。
    - force_onnx_cpu: 是否强制使用CPU进行推理。
        """
        # 判断模型是否为ONNX格式
        # 通过检查URL是否以 '.onnx' 结尾来确定模型类型
        # 如果是则 self.onnx 为 True，否则为 False
        self.onnx = True if url.endswith('.onnx') else False
        # 从指定的URL下载模型文件到本地，保存为 'inf.model'
        torch.hub.download_url_to_file(url, 'inf.model')
        # 根据模型类型加载相应的模型
        if self.onnx:
            # 若为ONNX模型，导入 onnxruntime 库
            import onnxruntime
            # 判断是否强制使用CPU且CPU执行提供者可用
            if force_onnx_cpu and 'CPUExecutionProvider' in onnxruntime.get_available_providers():
                # 如果满足条件，使用CPU执行提供者加载ONNX模型
                self.model = onnxruntime.InferenceSession('inf.model', providers=['CPUExecutionProvider'])
            else:
                # 否则，使用默认的提供者加载ONNX模型
                self.model = onnxruntime.InferenceSession('inf.model')
        else:
            # 若不是ONNX模型，调用 init_jit_model 函数加载JIT模型
            self.model = init_jit_model(model_path='inf.model')

    def __call__(self, inputs: torch.Tensor):
        """
    对输入数据进行推理。

    参数:
    - inputs: 输入数据。

    返回:
    - 推理结果。
        """
        # 使用 torch.no_grad() 上下文管理器，禁止在推理过程中计算梯度，以节省内存和提高推理速度
        with torch.no_grad():
            # 判断模型是否为 ONNX 模型
            if self.onnx:
                # 若为 ONNX 模型，将输入数据转换为 CPU 上的 NumPy 数组，并以字典形式包装，键为 'input'
                ort_inputs = {'input': inputs.cpu().numpy()}
                # 调用 ONNX 模型的 run 方法进行推理，传入输出名称（这里为 None，表示获取所有输出）和输入数据字典
                outs = self.model.run(None, ort_inputs)
                # 将 ONNX 模型的输出结果（NumPy 数组）转换为 PyTorch 张量
                outs = [torch.Tensor(x) for x in outs]
            else:
                # 若不是 ONNX 模型，直接将输入数据传入模型进行推理
                outs = self.model(inputs)

        # 返回推理结果
        return outs

def read_audio(path: str, sampling_rate: int = 16000):
    """
    读取音频文件并转换为指定采样率的单声道音频。

    参数:
    - path: 音频文件路径。
    - sampling_rate: 目标采样率。

    返回:
    - 读取的音频数据。
    """
    # 获取可用的音频后端列表
    list_backends = torchaudio.list_audio_backends()

    # 确保至少有一个可用的音频后端，如果列表为空则抛出断言错误
    # 同时给出推荐的后端安装建议，不同操作系统有不同的推荐后端
    assert len(list_backends) > 0, 'The list of available backends is empty, please install backend manually. \
                                    \n Recommendations: \n \tSox (UNIX OS) \n \tSoundfile (Windows OS, UNIX OS) \n \tffmpeg (Windows OS, UNIX OS)'

    try:
        # 定义音频处理效果列表，包括将音频转换为单声道和设置目标采样率
        effects = [
            ['channels', '1'],
            ['rate', str(sampling_rate)]
        ]

        # 尝试使用 torchaudio 的 sox_effects 模块对音频文件应用上述效果并读取音频
        # 得到音频数据 wav 和采样率 sr
        wav, sr = torchaudio.sox_effects.apply_effects_file(path, effects=effects)
    except:
        # 如果上述方法失败，使用 torchaudio.load 直接加载音频文件
        wav, sr = torchaudio.load(path)

        # 检查音频是否为多声道，如果是则将其转换为单声道
        # 通过计算所有声道的平均值来实现，同时保持维度不变
        if wav.size(0) > 1:
            wav = wav.mean(dim=0, keepdim=True)

        # 检查加载的音频采样率是否与目标采样率不一致
        if sr != sampling_rate:
            # 如果不一致，创建一个重采样转换器，指定原始采样率和目标采样率
            transform = torchaudio.transforms.Resample(orig_freq=sr,
                                                       new_freq=sampling_rate)
            # 使用重采样转换器对音频数据进行重采样
            wav = transform(wav)
            # 更新采样率为目标采样率
            sr = sampling_rate

    # 确保最终的采样率与目标采样率一致，若不一致则抛出断言错误
    assert sr == sampling_rate
    # 去除音频数据中维度为 1 的维度，并返回处理后的音频数据
    return wav.squeeze(0)

def save_audio(path: str, tensor: torch.Tensor, sampling_rate: int = 16000):
    """
    保存音频数据到文件。

    参数:
    - path: 保存路径。
    - tensor: 音频数据。
    - sampling_rate: 采样率。
    """
    torchaudio.save(path, tensor.unsqueeze(0), sampling_rate, bits_per_sample=16)

def init_jit_model(model_path: str, device=torch.device('cpu')):
    """
    加载JIT格式的模型。

    参数:
    - model_path: 模型文件路径。
    - device: 设备类型。

    返回:
    - 加载的模型。
    """
    # 使用torch.jit.load函数加载指定路径的JIT模型
    # map_location=device参数用于指定将模型加载到哪个设备上（如CPU或GPU）
    model = torch.jit.load(model_path, map_location=device)
    # 将模型设置为评估模式
    # 在评估模式下，一些特定于训练的操作（如Dropout、BatchNorm等）会被关闭
    # 以确保模型在推理时的稳定性和一致性
    model.eval()
    # 返回加载并设置好评估模式的模型
    return model

def make_visualization(probs, step):
    """
    生成语音概率的可视化图表。

    参数:
    - probs: 语音概率列表。
    - step: 时间步长。
    """
    # 导入 pandas 库，用于数据处理和可视化
    import pandas as pd
    # 创建一个 DataFrame 对象，将语音概率列表作为数据，键为 'probs'
    # 并设置索引为从 0 到语音概率列表长度的时间步长值，通过乘以 step 得到对应的时间
    df = pd.DataFrame({'probs': probs},
                      index=[x * step for x in range(len(probs))])
    # 调用 DataFrame 的 plot 方法绘制可视化图表
    # figsize=(16, 8) 设置图表的大小为宽 16 单位、高 8 单位
    # kind='area' 指定图表类型为面积图，用于直观展示语音概率随时间的变化
    # ylim=[0, 1.05] 设置 y 轴的范围从 0 到 1.05，确保概率值能完整显示且有一定余量
    # xlim=[0, len(probs) * step] 设置 x 轴的范围从 0 到所有语音概率对应的总时间
    # xlabel='seconds' 设置 x 轴的标签为 'seconds'，表示时间以秒为单位
    # ylabel='speech probability' 设置 y 轴的标签为 'speech probability'，表示语音概率
    # colormap='tab20' 设置图表的颜色映射为 'tab20'，使图表更美观易读
    df.plot(figsize=(16, 8),
            kind='area', ylim=[0, 1.05], xlim=[0, len(probs) * step],
            xlabel='seconds',
            ylabel='speech probability',
            colormap='tab20')

@torch.no_grad()
def get_speech_timestamps(audio: torch.Tensor,
                          model,
                          threshold: float = 0.5,
                          sampling_rate: int = 16000,
                          min_speech_duration_ms: int = 250,
                          max_speech_duration_s: float = float('inf'),
                          min_silence_duration_ms: int = 100,
                          speech_pad_ms: int = 30,
                          return_seconds: bool = False,
                          visualize_probs: bool = False,
                          progress_tracking_callback: Callable[[float], None] = None,
                          neg_threshold: float = None,
                          window_size_samples: int = 512,):
    """
    获取音频中的语音时间戳。

    参数:
    - audio: 输入的音频数据。
    - model: 预加载的VAD模型。
    - threshold: 语音检测阈值。
    - sampling_rate: 采样率。
    - min_speech_duration_ms: 最小语音持续时间。
    - max_speech_duration_s: 最大语音持续时间。
    - min_silence_duration_ms: 最小静音持续时间。
    - speech_pad_ms: 语音填充时间。
    - return_seconds: 是否返回秒为单位的时间戳。
    - visualize_probs: 是否可视化概率。
    - progress_tracking_callback: 进度跟踪回调函数。
    - neg_threshold: 负阈值。
    - window_size_samples: 窗口大小。

    返回:
    - 语音时间戳列表。
    """
    # 检查输入的音频是否为torch张量，如果不是则尝试转换
    if not torch.is_tensor(audio):
        try:
            audio = torch.Tensor(audio)
        except:
            # 若转换失败，抛出类型错误异常
            raise TypeError("Audio cannot be casted to tensor. Cast it manually")

    # 若音频张量维度大于1，尝试挤压空维度
    if len(audio.shape) > 1:
        for i in range(len(audio.shape)):  # trying to squeeze empty dimensions
            audio = audio.squeeze(0)
        # 若挤压后维度仍大于1，说明音频可能是多声道，抛出值错误异常
        if len(audio.shape) > 1:
            raise ValueError("More than one dimension in audio. Are you trying to process audio with 2 channels?")

    # 若采样率大于16000且是16000的倍数，进行下采样
    if sampling_rate > 16000 and (sampling_rate % 16000 == 0):
        step = sampling_rate // 16000
        sampling_rate = 16000
        audio = audio[::step]
        # 发出警告提示已手动将采样率转换为16000
        warnings.warn('Sampling rate is a multiply of 16000, casting to 16000 manually!')
    else:
        step = 1

    # 检查采样率是否为支持的8000或16000，若不支持则抛出值错误异常
    if sampling_rate not in [8000, 16000]:
        raise ValueError("Currently silero VAD models support 8000 and 16000 (or multiply of 16000) sample rates")

    # 根据采样率设置窗口大小样本数
    window_size_samples = 512 if sampling_rate == 16000 else 256

    # 重置模型状态
    model.reset_states()
    # 计算最小语音样本数
    min_speech_samples = sampling_rate * min_speech_duration_ms / 1000
    # 计算语音填充样本数
    speech_pad_samples = sampling_rate * speech_pad_ms / 1000
    # 计算最大语音样本数
    max_speech_samples = sampling_rate * max_speech_duration_s - window_size_samples - 2 * speech_pad_samples
    # 计算最小静音样本数
    min_silence_samples = sampling_rate * min_silence_duration_ms / 1000
    # 计算最大语音时长时允许的最小静音样本数
    min_silence_samples_at_max_speech = sampling_rate * 98 / 1000

    # 获取音频的总样本数
    audio_length_samples = len(audio)

    # 用于存储每个窗口的语音概率
    speech_probs = []
    # 遍历音频，按窗口大小取音频块进行处理
    for current_start_sample in range(0, audio_length_samples, window_size_samples):
        chunk = audio[current_start_sample: current_start_sample + window_size_samples]
        # 若当前音频块长度小于窗口大小，进行填充
        if len(chunk) < window_size_samples:
            chunk = torch.nn.functional.pad(chunk, (0, int(window_size_samples - len(chunk))))
        # 使用模型预测当前音频块的语音概率
        speech_prob = model(chunk, sampling_rate).item()
        speech_probs.append(speech_prob)
        # 计算处理进度并通过回调函数传递
        progress = current_start_sample + window_size_samples
        if progress > audio_length_samples:
            progress = audio_length_samples
        progress_percent = (progress / audio_length_samples) * 100
        if progress_tracking_callback:
            progress_tracking_callback(progress_percent)

    # 标记是否检测到语音开始
    triggered = False
    # 存储所有语音片段信息的列表
    speeches = []
    # 当前正在处理的语音片段信息
    current_speech = {}

    # 若未指定负阈值，计算负阈值
    if neg_threshold is None:
        neg_threshold = max(threshold - 0.15, 0.01)
    # 临时存储可能的语音片段结束位置
    temp_end = 0  # to save potential segment end (and tolerate some silence)
    # 存储上一个语音片段的结束位置
    prev_end = 0
    # 存储下一个可能的语音片段开始位置
    next_start = 0  # to save potential segment limits in case of maximum segment size reached

    # 遍历每个窗口的语音概率
    for i, speech_prob in enumerate(speech_probs):
        # 若当前概率大于等于阈值且之前有临时结束位置，重置临时结束位置
        if (speech_prob >= threshold) and temp_end:
            temp_end = 0
            if next_start < prev_end:
                next_start = window_size_samples * i

        # 若当前概率大于等于阈值且未触发语音开始标记，标记语音开始
        if (speech_prob >= threshold) and not triggered:
            triggered = True
            current_speech['start'] = window_size_samples * i
            continue

        # 若已触发语音开始且当前语音时长超过最大语音时长
        if triggered and (window_size_samples * i) - current_speech['start'] > max_speech_samples:
            if prev_end:
                current_speech['end'] = prev_end
                speeches.append(current_speech)
                current_speech = {}
                if next_start < prev_end:  # previously reached silence (< neg_thres) and is still not speech (< thres)
                    triggered = False
                else:
                    current_speech['start'] = next_start
                prev_end = next_start = temp_end = 0
            else:
                current_speech['end'] = window_size_samples * i
                speeches.append(current_speech)
                current_speech = {}
                prev_end = next_start = temp_end = 0
                triggered = False
                continue

        # 若当前概率小于负阈值且已触发语音开始标记
        if (speech_prob < neg_threshold) and triggered:
            if not temp_end:
                temp_end = window_size_samples * i
            # 若当前静音时长超过最大语音时长时允许的最小静音时长，记录上一个结束位置
            if ((window_size_samples * i) - temp_end) > min_silence_samples_at_max_speech:  # condition to avoid cutting in very short silence
                prev_end = temp_end
            # 若当前静音时长小于最小静音时长，继续等待
            if (window_size_samples * i) - temp_end < min_silence_samples:
                continue
            else:
                current_speech['end'] = temp_end
                # 若当前语音片段时长大于最小语音时长，添加到语音片段列表中
                if (current_speech['end'] - current_speech['start']) > min_speech_samples:
                    speeches.append(current_speech)
                current_speech = {}
                prev_end = next_start = temp_end = 0
                triggered = False
                continue

    # 若最后还有未处理完的语音片段且时长大于最小语音时长，添加到语音片段列表中
    if current_speech and (audio_length_samples - current_speech['start']) > min_speech_samples:
        current_speech['end'] = audio_length_samples
        speeches.append(current_speech)

    # 对每个语音片段的起始和结束位置进行填充处理
    for i, speech in enumerate(speeches):
        if i == 0:
            speech['start'] = int(max(0, speech['start'] - speech_pad_samples))
        if i != len(speeches) - 1:
            silence_duration = speeches[i+1]['start'] - speech['end']
            if silence_duration < 2 * speech_pad_samples:
                speech['end'] += int(silence_duration // 2)
                speeches[i+1]['start'] = int(max(0, speeches[i+1]['start'] - silence_duration // 2))
            else:
                speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))
                speeches[i+1]['start'] = int(max(0, speeches[i+1]['start'] - speech_pad_samples))
        else:
            speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))

    # 若需要返回以秒为单位的时间戳，进行转换
    if return_seconds:
        audio_length_seconds = audio_length_samples / sampling_rate
        for speech_dict in speeches:
            speech_dict['start'] = max(round(speech_dict['start'] / sampling_rate, 1), 0)
            speech_dict['end'] = min(round(speech_dict['end'] / sampling_rate, 1), audio_length_seconds)
    # 若之前进行了下采样，对时间戳进行恢复
    elif step > 1:
        for speech_dict in speeches:
            speech_dict['start'] *= step
            speech_dict['end'] *= step

    # 若需要可视化语音概率，调用可视化函数
    if visualize_probs:
        make_visualization(speech_probs, window_size_samples / sampling_rate)

    # 返回语音时间戳列表
    return speeches
class VADIterator:
    """
    语音活动检测迭代器类，用于流式处理音频数据。
    """

    def __init__(self,
                 model,
                 threshold: float = 0.5,
                 sampling_rate: int = 16000,
                 min_silence_duration_ms: int = 100,
                 speech_pad_ms: int = 30
                 ):
        """
        初始化语音活动检测迭代器。

        参数:
        - model: 预加载的VAD模型。
        - threshold: 语音检测阈值。
        - sampling_rate: 采样率。
        - min_silence_duration_ms: 最小静音持续时间。
        - speech_pad_ms: 语音填充时间。
        """
        # 存储预加载的VAD模型
        self.model = model
        # 存储语音检测阈值
        self.threshold = threshold
        # 存储采样率
        self.sampling_rate = sampling_rate

        # 检查采样率是否为8000或16000，若不是则抛出值错误异常
        if sampling_rate not in [8000, 16000]:
            raise ValueError('VADIterator does not support sampling rates other than [8000, 16000]')

        # 计算最小静音样本数
        self.min_silence_samples = sampling_rate * min_silence_duration_ms / 1000
        # 计算语音填充样本数
        self.speech_pad_samples = sampling_rate * speech_pad_ms / 1000
        # 重置模型状态
        self.reset_states()

    def reset_states(self):
        """
        重置模型状态。
        """
        # 调用模型的重置状态方法
        self.model.reset_states()
        # 标记是否检测到语音开始，初始为False
        self.triggered = False
        # 临时存储可能的语音片段结束位置，初始为0
        self.temp_end = 0
        # 当前处理的样本位置，初始为0
        self.current_sample = 0

    @torch.no_grad()
    def __call__(self, x, return_seconds=False):
        """
        对输入的音频数据进行推理。

        参数:
        - x: 输入的音频数据。
        - return_seconds: 是否返回秒为单位的时间戳。

        返回:
        - 语音时间戳。
        """
        # 检查输入的音频是否为torch张量，如果不是则尝试转换
        if not torch.is_tensor(x):
            try:
                x = torch.Tensor(x)
            except:
                # 若转换失败，抛出类型错误异常
                raise TypeError("Audio cannot be casted to tensor. Cast it manually")

        # 获取当前音频块的窗口大小样本数
        window_size_samples = len(x[0]) if x.dim() == 2 else len(x)
        # 更新当前处理的样本位置
        self.current_sample += window_size_samples

        # 使用模型预测当前音频块的语音概率
        speech_prob = self.model(x, self.sampling_rate).item()

        # 若当前概率大于等于阈值且之前有临时结束位置，重置临时结束位置
        if (speech_prob >= self.threshold) and self.temp_end:
            self.temp_end = 0

        # 若当前概率大于等于阈值且未触发语音开始标记，标记语音开始并返回语音开始时间戳
        if (speech_prob >= self.threshold) and not self.triggered:
            self.triggered = True
            # 计算语音开始位置，考虑语音填充样本数
            speech_start = max(0, self.current_sample - self.speech_pad_samples - window_size_samples)
            # 根据是否返回秒为单位的时间戳进行相应处理
            return {'start': int(speech_start) if not return_seconds else round(speech_start / self.sampling_rate, 1)}

        # 若当前概率小于阈值减去0.15且已触发语音开始标记
        if (speech_prob < self.threshold - 0.15) and self.triggered:
            if not self.temp_end:
                # 记录临时结束位置
                self.temp_end = self.current_sample
            # 若当前静音时长小于最小静音时长，返回None
            if self.current_sample - self.temp_end < self.min_silence_samples:
                return None
            else:
                # 计算语音结束位置，考虑语音填充样本数
                speech_end = self.temp_end + self.speech_pad_samples - window_size_samples
                # 重置临时结束位置
                self.temp_end = 0
                # 标记语音结束
                self.triggered = False
                # 根据是否返回秒为单位的时间戳进行相应处理
                return {'end': int(speech_end) if not return_seconds else round(speech_end / self.sampling_rate, 1)}

        # 若以上条件都不满足，返回None
        return None
from typing import List
import torch

def collect_chunks(tss: List[dict], wav: torch.Tensor):
    """
    根据时间戳列表收集音频片段。

    参数:
    - tss: 时间戳列表，列表中的每个元素是一个字典，包含 'start' 和 'end' 键，分别表示音频片段的起始和结束位置。
    - wav: 音频数据，是一个 torch.Tensor 类型的张量。

    返回:
    - 收集的音频片段，将所有符合时间戳的音频片段拼接成一个 torch.Tensor。
    """
    # 用于存储收集到的音频片段
    chunks = []
    # 遍历时间戳列表
    for i in tss:
        # 从音频数据中提取对应时间戳的音频片段，并添加到 chunks 列表中
        chunks.append(wav[i['start']: i['end']])
    # 将收集到的所有音频片段拼接成一个张量并返回
    return torch.cat(chunks)

def drop_chunks(tss: List[dict], wav: torch.Tensor):
    """
    根据时间戳列表删除音频片段。

    参数:
    - tss: 时间戳列表，列表中的每个元素是一个字典，包含 'start' 和 'end' 键，分别表示要删除的音频片段的起始和结束位置。
    - wav: 音频数据，是一个 torch.Tensor 类型的张量。

    返回:
    - 删除后的音频片段，将所有不在时间戳范围内的音频片段拼接成一个 torch.Tensor。
    """
    # 用于存储保留的音频片段
    chunks = []
    # 记录当前处理的起始位置，初始为 0
    cur_start = 0
    # 遍历时间戳列表
    for i in tss:
        # 提取当前起始位置到时间戳起始位置之间的音频片段，并添加到 chunks 列表中
        chunks.append((wav[cur_start: i['start']]))
        # 更新当前处理的起始位置为时间戳的结束位置
        cur_start = i['end']
    # 将保留的所有音频片段拼接成一个张量并返回
    return torch.cat(chunks)