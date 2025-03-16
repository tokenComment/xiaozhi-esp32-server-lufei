# 从abc模块导入ABC和abstractmethod，用于定义抽象基类和抽象方法
from abc import ABC, abstractmethod
# 从自定义配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging
# 导入opuslib_next模块，用于处理Opus音频编码和解码
import opuslib_next
# 导入time模块，用于获取当前时间，处理时间相关的逻辑
import time
# 导入numpy库，用于处理数值计算和数组操作
import numpy as np
# 导入torch库，用于深度学习相关的操作，这里用于加载和使用语音活动检测模型
import torch

# 获取当前模块的名称作为标签，用于在日志记录中标识来源
TAG = __name__
# 调用设置日志的函数，获取日志记录器
logger = setup_logging()

class VAD(ABC):
    @abstractmethod
    def is_vad(self, conn, data):
        """
        抽象方法，用于检测音频数据中的语音活动。

        :param conn: 连接对象，可能包含客户端的音频缓冲区等信息
        :param data: 音频数据，通常是Opus编码的数据包
        :return: 如果检测到语音活动，返回True；否则返回False
        """
        pass


class SileroVAD(VAD):
    def __init__(self, config):
        """
        初始化SileroVAD类的实例。

        :param config: 配置字典，包含模型目录、语音活动检测阈值、最小静默时长等配置信息
        """
        # 记录日志，显示正在使用SileroVAD以及配置信息
        logger.bind(tag=TAG).info("SileroVAD", config)
        # 从本地加载Silero语音活动检测模型
        self.model, self.utils = torch.hub.load(repo_or_dir=config["model_dir"],
                                                source='local',
                                                model='silero_vad',
                                                force_reload=False)
        # 从utils中解包获取提取语音时间戳的函数
        (get_speech_timestamps, _, _, _, _) = self.utils

        # 创建Opus解码器，采样率为16000Hz，单声道
        self.decoder = opuslib_next.Decoder(16000, 1)
        # 从配置中获取语音活动检测的阈值
        self.vad_threshold = config.get("threshold")
        # 从配置中获取最小静默时长（毫秒）
        self.silence_threshold_ms = config.get("min_silence_duration_ms")

    def is_vad(self, conn, opus_packet):
        """
        检测输入的Opus音频数据包中是否存在语音活动。

        :param conn: 连接对象，包含客户端的音频缓冲区、语音活动状态等信息
        :param opus_packet: Opus编码的音频数据包
        :return: 如果检测到语音活动，返回True；否则返回False
        """
        try:
            # 解码Opus数据包为PCM音频帧
            pcm_frame = self.decoder.decode(opus_packet, 960)
            # 将解码后的PCM音频帧添加到客户端的音频缓冲区
            conn.client_audio_buffer += pcm_frame

            # 初始化语音活动标志
            client_have_voice = False
            # 处理缓冲区中的完整帧（每次处理512采样点）
            while len(conn.client_audio_buffer) >= 512 * 2:
                # 提取前512个采样点（1024字节）
                chunk = conn.client_audio_buffer[:512 * 2]
                # 从缓冲区中移除已处理的音频数据
                conn.client_audio_buffer = conn.client_audio_buffer[512 * 2:]

                # 将音频数据从字节格式转换为int16类型的numpy数组
                audio_int16 = np.frombuffer(chunk, dtype=np.int16)
                # 将int16类型的音频数据转换为float32类型，并进行归一化处理
                audio_float32 = audio_int16.astype(np.float32) / 32768.0
                # 将numpy数组转换为PyTorch张量
                audio_tensor = torch.from_numpy(audio_float32)

                # 使用Silero模型检测语音活动，得到语音概率
                speech_prob = self.model(audio_tensor, 16000).item()
                # 判断是否检测到语音活动
                client_have_voice = speech_prob >= self.vad_threshold

                # 如果之前有声音，但本次没有声音，且与上次有声音的时间差已经超过了静默阈值，则认为已经说完一句话
                if conn.client_have_voice and not client_have_voice:
                    stop_duration = time.time() * 1000 - conn.client_have_voice_last_time
                    if stop_duration >= self.silence_threshold_ms:
                        conn.client_voice_stop = True
                # 如果检测到语音活动，更新客户端的语音活动状态和最后有声音的时间
                if client_have_voice:
                    conn.client_have_voice = True
                    conn.client_have_voice_last_time = time.time() * 1000

            return client_have_voice
        except opuslib_next.OpusError as e:
            # 记录Opus解码错误的日志
            logger.bind(tag=TAG).info(f"解码错误: {e}")
        except Exception as e:
            # 记录处理音频数据包时的其他错误日志
            logger.bind(tag=TAG).error(f"Error processing audio packet: {e}")


def create_instance(class_name, *args, **kwargs) -> VAD:
    """
    根据类名创建VAD（语音活动检测）类的实例。

    :param class_name: 要创建实例的类名
    :param args: 传递给类构造函数的位置参数
    :param kwargs: 传递给类构造函数的关键字参数
    :return: VAD类的实例
    :raises ValueError: 如果指定的类名不支持，则抛出异常
    """
    # 定义类名到类对象的映射
    cls_map = {
        "SileroVAD": SileroVAD,
        # 可扩展其他SileroVAD实现
    }

    # 根据类名从映射中获取类对象
    if cls := cls_map.get(class_name):
        # 创建类的实例并返回
        return cls(*args, **kwargs)
    # 如果类名不支持，抛出异常
    raise ValueError(f"不支持的SileroVAD类型: {class_name}")