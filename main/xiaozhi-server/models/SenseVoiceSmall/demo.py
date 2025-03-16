# 从funasr库中导入AutoModel类，该类可用于自动加载和使用预训练模型
from funasr import AutoModel
# 从funasr库的后处理工具模块中导入rich_transcription_postprocess函数，用于对转录结果进行后处理
from funasr.utils.postprocess_utils import rich_transcription_postprocess

# 定义模型所在的目录，这里指定为当前目录
model_dir = "./"

# 使用AutoModel类创建一个模型实例
model = AutoModel(
    # 指定模型所在的目录，用于加载模型
    model=model_dir,
    # 指定语音活动检测（VAD）模型为fsmn - vad
    vad_model="fsmn-vad",
    # 为VAD模型传递参数，这里设置单个语音片段的最大时长为30000毫秒
    vad_kwargs={"max_single_segment_time": 30000},
    # 注释掉的代码，若取消注释可指定使用的设备为CUDA设备（如GPU），这里指定为cuda:0
    # device="cuda:0",
    # 指定模型从Hugging Face的模型库中加载
    hub="hf",
)

# 进行语音识别，输入为英文语音文件
res = model.generate(
    # 指定输入的语音文件路径，这里是模型目录下的example/en.mp3文件
    input=f"{model.model_path}/example/en.mp3",
    # 用于缓存识别结果，这里传入空字典
    cache={},
    # 指定识别的语言，设置为"auto"表示自动检测语言，也可手动指定为"zn", "en", "yue", "ja", "ko", "nospeech"等
    language="auto",
    # 是否使用逆文本标准化（ITN）技术，开启后可对识别结果进行规范化处理
    use_itn=True,
    # 批量处理的时间长度，单位为秒，这里设置为60秒
    batch_size_s=60,
    # 是否合并VAD检测出的语音片段
    merge_vad=True,
    # 合并语音片段的最大时长，单位为秒，这里设置为15秒
    merge_length_s=15,
)

# 对识别结果进行后处理，提取出转录的文本
text = rich_transcription_postprocess(res[0]["text"])
# 打印经过后处理的转录文本
print(text)