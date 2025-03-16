# 导入os模块，用于与操作系统进行交互，如文件路径操作、目录处理等
import os
# 导入json模块，用于处理JSON数据，如将数据写入JSON文件或从JSON文件读取数据
import json
# 导入yaml模块，用于处理YAML格式的配置文件
import yaml
# 导入socket模块，用于网络通信，这里用于获取本地IP地址
import socket
# 导入subprocess模块，用于创建新的进程，执行外部命令，如检查ffmpeg是否安装
import subprocess
# 导入logging模块，用于记录程序运行过程中的信息，如错误信息、调试信息等
import logging
# 导入re模块，用于正则表达式操作，这里用于从字符串中提取JSON部分
import re
from datetime import datetime


def get_project_dir():
    """
    获取项目的根目录。

    通过多次调用os.path.dirname函数，从当前文件的绝对路径逐步向上查找，最终得到项目根目录。

    :return: 项目根目录的路径，路径末尾带有斜杠。
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + '/'


def get_local_ip():
    """
    获取本地机器的IP地址。

    尝试创建一个UDP套接字并连接到Google的DNS服务器（8.8.8.8:80），
    然后通过getsockname方法获取本地IP地址。如果出现异常，则返回默认的本地回环地址127.0.0.1。

    :return: 本地机器的IP地址，如果获取失败则返回"127.0.0.1"。
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to Google's DNS servers
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        return "127.0.0.1"


def read_config(config_path):
    """
    从指定路径的YAML文件中读取配置信息。

    :param config_path: YAML配置文件的路径。
    :return: 解析后的配置信息，通常是一个字典。
    """
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    return config


def write_json_file(file_path, data):
    """
    将数据写入指定路径的JSON文件。

    :param file_path: 要写入的JSON文件的路径。
    :param data: 要写入文件的数据，可以是字典、列表等可序列化的数据类型。
    """
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def is_punctuation_or_emoji(char):
    """
    检查字符是否为空格、指定标点或表情符号。

    :param char: 要检查的字符。
    :return: 如果字符是空格、指定标点或表情符号，则返回True；否则返回False。
    """
    # 定义需要去除的中英文标点（包括全角/半角）
    punctuation_set = {
        '，', ',',  # 中文逗号 + 英文逗号
        '。', '.',  # 中文句号 + 英文句号
        '！', '!',  # 中文感叹号 + 英文感叹号
        '-', '－',  # 英文连字符 + 中文全角横线
        '、'  # 中文顿号
    }
    if char.isspace() or char in punctuation_set:
        return True
    # 检查表情符号（保留原有逻辑）
    code_point = ord(char)
    emoji_ranges = [
        (0x1F600, 0x1F64F), (0x1F300, 0x1F5FF),
        (0x1F680, 0x1F6FF), (0x1F900, 0x1F9FF),
        (0x1FA70, 0x1FAFF), (0x2600, 0x26FF),
        (0x2700, 0x27BF)
    ]
    return any(start <= code_point <= end for start, end in emoji_ranges)


def get_string_no_punctuation_or_emoji(s):
    """
    去除字符串首尾的空格、标点符号和表情符号。

    :param s: 要处理的字符串。
    :return: 去除首尾空格、标点符号和表情符号后的字符串。
    """
    chars = list(s)
    # 处理开头的字符
    start = 0
    while start < len(chars) and is_punctuation_or_emoji(chars[start]):
        start += 1
    # 处理结尾的字符
    end = len(chars) - 1
    while end >= start and is_punctuation_or_emoji(chars[end]):
        end -= 1
    return ''.join(chars[start:end + 1])


def remove_punctuation_and_length(text):
    """
    去除字符串中的全角和半角标点符号以及空格，并返回处理后字符串的长度和处理后的字符串。

    :param text: 要处理的字符串。
    :return: 一个元组，包含处理后字符串的长度和处理后的字符串。如果处理后字符串为 "Yeah"，则长度为0，字符串为空。
    """
    # 全角符号和半角符号的Unicode范围
    full_width_punctuations = '！＂＃＄％＆＇（）＊＋，－。／：；＜＝＞？＠［＼］＾＿｀｛｜｝～'
    half_width_punctuations = r'!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~'
    space = ' '  # 半角空格
    full_width_space = '　'  # 全角空格

    # 去除全角和半角符号以及空格
    result = ''.join([char for char in text if
                      char not in full_width_punctuations and char not in half_width_punctuations and char not in space and char not in full_width_space])

    if result == "Yeah":
        return 0, ""
    return len(result), result


def check_model_key(modelType, modelKey):
    """
    检查模型密钥是否包含特定字符 "你"，如果包含则记录错误日志并返回False。

    :param modelType: 模型的类型，用于错误日志的提示信息。
    :param modelKey: 模型的密钥。
    :return: 如果密钥不包含 "你"，则返回True；否则返回False。
    """
    if "你" in modelKey:
        logging.error("你还没配置" + modelType + "的密钥，请在配置文件中配置密钥，否则无法正常工作")
        return False
    return True


def check_ffmpeg_installed():
    """
    检查系统中是否正确安装了ffmpeg。

    尝试执行ffmpeg -version命令，如果命令执行成功且输出中包含 "ffmpeg version"，则认为ffmpeg已安装；
    否则，抛出ValueError异常，提示用户安装ffmpeg。

    :raises ValueError: 如果ffmpeg未安装，抛出异常并提供安装建议。
    """
    ffmpeg_installed = False
    try:
        # 执行ffmpeg -version命令，并捕获输出
        result = subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True  # 如果返回码非零则抛出异常
        )
        # 检查输出中是否包含版本信息（可选）
        output = result.stdout + result.stderr
        if 'ffmpeg version' in output.lower():
            ffmpeg_installed = True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        # 命令执行失败或未找到
        ffmpeg_installed = False
    if not ffmpeg_installed:
        error_msg = "您的电脑还没正确安装ffmpeg\n"
        error_msg += "\n建议您：\n"
        error_msg += "1、按照项目的安装文档，正确进入conda环境\n"
        error_msg += "2、查阅安装文档，如何在conda环境中安装ffmpeg\n"
        raise ValueError(error_msg)


def extract_json_from_string(input_string):
    """
    从字符串中提取JSON部分。

    使用正则表达式查找字符串中第一个匹配的JSON对象，并返回该JSON对象的字符串表示。

    :param input_string: 要处理的字符串。
    :return: 提取的JSON字符串，如果未找到则返回None。
    """
    pattern = r'(\{.*\})'
    match = re.search(pattern, input_string)
    if match:
        return match.group(1)  # 返回提取的 JSON 字符串
    return None