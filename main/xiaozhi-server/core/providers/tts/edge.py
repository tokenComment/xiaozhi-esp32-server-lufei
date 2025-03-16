import os
import uuid
import edge_tts
from datetime import datetime
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        """
        初始化TTSProvider类的实例，该类用于实现文本转语音（TTS）功能。

        :param config: 一个包含配置信息的字典，至少应包含 'voice' 键，用于指定语音类型。
        :param delete_audio_file: 一个布尔值，指示是否在完成某些操作后删除生成的音频文件，
                                  该参数会传递给父类的构造函数进行处理。
        """
        # 调用父类TTSProviderBase的构造函数，传入配置信息和删除音频文件的标志
        super().__init__(config, delete_audio_file)
        # 从配置字典中获取语音类型，如果没有提供则默认为 None
        self.voice = config.get("voice")

    def generate_filename(self, extension=".mp3"):
        """
        生成一个唯一的文件名，用于保存文本转语音后生成的音频文件。

        :param extension: 音频文件的扩展名，默认为 ".mp3"。
        :return: 包含完整路径和文件名的字符串，文件名由固定前缀、当前日期、唯一的 UUID 和文件扩展名组成。
        """
        # 使用 os.path.join 函数将输出文件路径、固定前缀、当前日期、唯一的 UUID 和文件扩展名组合成完整的文件名
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将输入的文本转换为语音，并将生成的语音保存为音频文件。

        :param text: 要转换为语音的文本内容。
        :param output_file: 用于保存生成音频文件的完整路径。
        """
        # 创建一个 edge_tts.Communicate 对象，指定要转换的文本和使用的语音类型
        communicate = edge_tts.Communicate(text, voice=self.voice)
        # 异步调用 communicate 对象的 save 方法，将生成的语音保存到指定的输出文件中
        await communicate.save(output_file)