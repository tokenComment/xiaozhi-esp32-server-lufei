# 导入struct模块，用于处理二进制数据的打包和解包
import struct

def decode_opus_from_file(input_file):
    """
    从指定的p3文件中解码Opus数据，将解码后的Opus数据包存储在列表中，并计算数据的总时长。

    :param input_file: 包含Opus数据的p3文件的路径
    :return: 一个元组，包含两个元素：
             - 一个列表，列表中的每个元素为一个Opus数据包
             - 数据的总时长（以秒为单位）
    """
    # 用于存储解码后的Opus数据包
    opus_datas = []
    # 记录文件中Opus数据的总帧数
    total_frames = 0
    # 定义文件的采样率，单位为赫兹
    sample_rate = 16000
    # 定义每一帧Opus数据的时长，单位为毫秒
    frame_duration_ms = 60
    # 根据采样率和帧时长计算每一帧的样本数量
    frame_size = int(sample_rate * frame_duration_ms / 1000)

    # 以二进制只读模式打开输入文件
    with open(input_file, 'rb') as f:
        while True:
            # 从文件中读取4字节的头部信息
            header = f.read(4)
            # 如果没有读取到头部信息，说明文件已读完，退出循环
            if not header:
                break

            # 使用struct.unpack函数解包头部信息
            # '>BBH' 表示大端字节序，依次解析为一个无符号字节、一个无符号字节和一个无符号短整型
            # 这里只关心最后一个值，即Opus数据的长度
            _, _, data_len = struct.unpack('>BBH', header)

            # 根据头部信息中指定的长度，从文件中读取Opus数据
            opus_data = f.read(data_len)
            # 检查读取到的Opus数据长度是否与头部信息中指定的长度一致
            if len(opus_data) != data_len:
                # 如果不一致，抛出异常提示数据长度不匹配
                raise ValueError(f"Data length({len(opus_data)}) mismatch({data_len}) in the file.")

            # 将读取到的Opus数据添加到列表中
            opus_datas.append(opus_data)
            # 总帧数加1
            total_frames += 1

    # 根据总帧数和每一帧的时长计算数据的总时长，单位为秒
    total_duration = (total_frames * frame_duration_ms) / 1000.0
    # 返回解码后的Opus数据包列表和总时长
    return opus_datas, total_duration