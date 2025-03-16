from config.logger import setup_logging
import json
from core.handle.sendAudioHandle import send_stt_message
from core.utils.util import remove_punctuation_and_length


TAG = __name__  # 定义日志标签，用于在日志中标识模块名称
logger = setup_logging()  # 初始化日志记录器，用于记录程序运行过程中的日志信息

# 处理用户意图
async def handle_user_intent(conn, text):
    """
    在开始聊天之前处理用户意图。
    
    参数:
        conn: 客户端连接对象
        text: 用户的文本输入
    
    返回:
        bool: 如果意图已处理返回True，否则返回False，继续常规聊天流程。
    """
    # 检查是否有明确的退出命令
    if await check_direct_exit(conn, text):
        return True

    if conn.use_function_call_mode:
        # 如果启用了function calling模式，直接返回False，跳过意图分析
        return False

    # 使用LLM进行意图分析
    intent = await analyze_intent_with_llm(conn, text)

    if not intent:
        return False

    # 处理意图识别结果
    return await process_intent_result(conn, intent, text)


# 检查是否有明确的退出命令
async def check_direct_exit(conn, text):
    """检查是否有明确的退出命令"""
    _, text = remove_punctuation_and_length(text)  # 去除标点符号并限制文本长度
    cmd_exit = conn.cmd_exit  # 获取退出命令列表
    for cmd in cmd_exit:
        if text == cmd:
            logger.bind(tag=TAG).info(f"识别到明确的退出命令: {text}")
            await conn.close()  # 关闭连接
            return True
    return False


# 使用LLM分析用户意图
async def analyze_intent_with_llm(conn, text):
    """使用LLM分析用户意图"""
    if not hasattr(conn, 'intent') or not conn.intent:
        logger.bind(tag=TAG).warning("意图识别服务未初始化")
        return None

    # 获取对话历史记录
    dialogue = conn.dialogue
    try:
        # 调用LLM意图检测接口
        intent_result = await conn.intent.detect_intent(conn, dialogue.dialogue, text)

        # 尝试解析JSON结果
        try:
            intent_data = json.loads(intent_result)
            if "intent" in intent_data:
                return intent_data["intent"]
        except json.JSONDecodeError:
            # 如果不是JSON格式，尝试直接获取意图文本
            return intent_result.strip()

    except Exception as e:
        logger.bind(tag=TAG).error(f"意图识别失败: {str(e)}")

    return None


# 处理意图识别结果
async def process_intent_result(conn, intent, original_text):
    """处理意图识别结果"""
    # 处理退出意图
    if "结束聊天" in intent:
        logger.bind(tag=TAG).info(f"识别到退出意图: {intent}")

        # 如果正在播放音乐，可以关了（TODO）
        await send_stt_message(conn, original_text)  # 发送语音消息
        conn.executor.submit(conn.chat_and_close, original_text)  # 提交关闭聊天任务
        return True

    # 处理播放音乐意图
    if "播放音乐" in intent:
        logger.bind(tag=TAG).info(f"识别到音乐播放意图: {intent}")
        await conn.music_handler.handle_music_command(conn, intent)  # 处理音乐播放命令
        return True

    # 其他意图处理可以在这里扩展

    # 默认返回False，表示继续常规聊天流程
    return False