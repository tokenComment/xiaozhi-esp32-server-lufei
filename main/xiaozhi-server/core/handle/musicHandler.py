from config.logger import setup_logging
import os
import random
import difflib
import re
import traceback
from pathlib import Path
import time
from core.handle.sendAudioHandle import send_stt_message
from core.utils import p3

TAG = __name__  # 定义日志标签，用于在日志中标识模块名称
logger = setup_logging()  # 初始化日志记录器


def _extract_song_name(text):
    """
    从用户输入中提取歌名。

    参数:
        text (str): 用户输入的文本。

    返回:
        str: 提取到的歌名，如果未提取到则返回 None。

    逻辑:
        检查文本中是否包含关键词（如“播放音乐”），并提取关键词后的部分作为歌名。
    """
    for keyword in ["播放音乐"]:  # 定义关键词
        if keyword in text:
            parts = text.split(keyword)  # 按关键词分割文本
            if len(parts) > 1:
                return parts[1].strip()  # 返回关键词后的部分（去除多余空格）
    return None


def _find_best_match(potential_song, music_files):
    """
    在音乐文件列表中查找与输入歌名最匹配的文件。

    参数:
        potential_song (str): 用户输入的歌名（可能不完整）。
        music_files (list): 音乐文件列表。

    返回:
        str: 最匹配的音乐文件名，如果没有匹配项则返回 None。

    逻辑:
        使用 difflib.SequenceMatcher 计算输入歌名与每个音乐文件名的相似度，
        返回相似度最高的文件（相似度需大于 0.4）。
    """
    best_match = None
    highest_ratio = 0

    for music_file in music_files:
        song_name = os.path.splitext(music_file)[0]  # 去掉文件扩展名
        ratio = difflib.SequenceMatcher(None, potential_song, song_name).ratio()  # 计算相似度
        if ratio > highest_ratio and ratio > 0.4:  # 确保相似度足够高
            highest_ratio = ratio
            best_match = music_file
    return best_match


class MusicManager:
    """
    管理音乐文件的类。

    属性:
        music_dir (Path): 音乐文件夹路径。
        music_ext (tuple): 支持的音乐文件扩展名。

    功能:
        扫描指定目录及其子目录，获取支持的音乐文件列表。
    """

    def __init__(self, music_dir, music_ext):
        """
        初始化 MusicManager。

        参数:
            music_dir (str): 音乐文件夹路径。
            music_ext (tuple): 支持的音乐文件扩展名。
        """
        self.music_dir = Path(music_dir)  # 转换为 Path 对象
        self.music_ext = music_ext

    def get_music_files(self):
        """
        获取指定目录及其子目录中的音乐文件列表。

        返回:
            list: 音乐文件列表（相对路径）。
        """
        music_files = []
        for file in self.music_dir.rglob("*"):  # 遍历目录及其子目录
            if file.is_file():  # 确保是文件
                ext = file.suffix.lower()  # 获取文件扩展名
                if ext in self.music_ext:  # 检查扩展名是否支持
                    music_files.append(str(file.relative_to(self.music_dir)))  # 添加相对路径
        return music_files


class MusicHandler:
    """
    处理音乐播放请求的类。

    功能:
        - 初始化音乐配置。
        - 处理用户输入的音乐播放指令。
        - 播放本地音乐文件。
    """

    def __init__(self, config):
        """
        初始化 MusicHandler。

        参数:
            config (dict): 配置信息，包含音乐目录、支持的文件类型等。
        """
        self.config = config

        if "music" in self.config:  # 从配置中读取音乐设置
            self.music_config = self.config["music"]
            self.music_dir = os.path.abspath(self.music_config.get("music_dir", "./music"))  # 音乐目录
            self.music_ext = self.music_config.get("music_ext", (".mp3", ".wav", ".p3"))  # 支持的文件类型
            self.refresh_time = self.music_config.get("refresh_time", 60)  # 刷新间隔
        else:
            self.music_dir = os.path.abspath("./music")  # 默认音乐目录
            self.music_ext = (".mp3", ".wav", ".p3")  # 默认支持的文件类型
            self.refresh_time = 60  # 默认刷新间隔

        # 获取音乐文件列表
        self.music_files = MusicManager(self.music_dir, self.music_ext).get_music_files()
        self.scan_time = time.time()  # 上次扫描时间
        logger.bind(tag=TAG).debug(f"找到的音乐文件: {self.music_files}")

    async def handle_music_command(self, conn, text):
        """
        处理用户输入的音乐播放指令。

        参数:
            conn: 客户端连接对象。
            text (str): 用户输入的文本。

        逻辑:
            1. 提取歌名（如果用户指定了具体歌名）。
            2. 在音乐文件列表中查找最匹配的歌曲。
            3. 播放匹配的歌曲或随机播放一首。
        """
        clean_text = re.sub(r'[^\w\s]', '', text).strip()  # 去除标点符号
        logger.bind(tag=TAG).debug(f"检查是否是音乐命令: {clean_text}")

        # 尝试匹配具体歌名
        if os.path.exists(self.music_dir):  # 确保音乐目录存在
            if time.time() - self.scan_time > self.refresh_time:  # 检查是否需要刷新文件列表
                self.music_files = MusicManager(self.music_dir, self.music_ext).get_music_files()
                self.scan_time = time.time()
                logger.bind(tag=TAG).debug(f"刷新的音乐文件: {self.music_files}")

            potential_song = _extract_song_name(clean_text)  # 提取歌名
            if potential_song:
                best_match = _find_best_match(potential_song, self.music_files)  # 查找最匹配的歌曲
                if best_match:
                    logger.bind(tag=TAG).info(f"找到最匹配的歌曲: {best_match}")
                    await self.play_local_music(conn, specific_file=best_match)  # 播放匹配的歌曲
                    return True
        # 如果未找到匹配的歌曲，随机播放一首
        await self.play_local_music(conn)
        return True

    async def play_local_music(self, conn, specific_file=None):
        """
        播放本地音乐文件。

        参数:
            conn: 客户端连接对象。
            specific_file (str, optional): 指定播放的音乐文件名。如果未指定，则随机播放一首。

        逻辑:
            1. 确保音乐目录存在。
            2. 如果指定了文件，则直接播放；否则随机选择一首。
            3. 将音乐文件转换为 Opus 数据并发送给客户端。
        """
        try:
            if not os.path.exists(self.music_dir):  # 检查音乐目录是否存在
                logger.bind(tag=TAG).error(f"音乐目录不存在: {self.music_dir}")
                return

            # 确定播放的音乐文件
            if specific_file:
                selected_music = specific_file
                music_path = os.path.join(self.music_dir, specific_file)
            else:
                if not self.music_files:  # 如果没有找到音乐文件
                    logger.bind(tag=TAG).error("未找到音乐文件")
                    return
                selected_music = random.choice(self.music_files)  # 随机选择一首
                music_path = os.path.join(self.music_dir, selected_music)

            if not os.path.exists(music_path):  # 检查文件是否存在
                logger.bind(tag=TAG).error(f"选定的音乐文件不存在: {music_path}")
                return

            # 发送播放信息给客户端
            text = f"正在播放{selected_music}"
            await send_stt_message(conn, text)
            conn.tts_first_text_index = 0
            conn.tts_last_text_index = 0
            conn.llm_finish_task = True

            # 将音乐文件转换为 Opus 数据
            if music_path.endswith(".p3"):
                opus_packets, duration = p3.decode_opus_from_file(music_path)
            else:
                opus_packets, duration = conn.tts.audio_to_opus_data(music_path)

            # 将 Opus 数据放入播放队列
            conn.audio_play_queue.put((opus_packets, selected_music, 0))

        except Exception as e:
            logger.bind(tag=TAG).error(f"播放音乐失败: {str(e)}")
            logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")