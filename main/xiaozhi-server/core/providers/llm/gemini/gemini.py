# 导入Google生成式AI库，用于与Gemini模型进行交互
import google.generativeai as genai
# 从核心工具模块导入检查模型密钥的函数
from core.utils.util import check_model_key
# 从核心的大语言模型（LLM）提供程序基础模块中导入基类
from core.providers.llm.base import LLMProviderBase

# 定义一个大语言模型（LLM）提供程序类，继承自LLMProviderBase基类
class LLMProvider(LLMProviderBase):
    # 类的初始化方法，在创建该类的实例时会被调用
    def __init__(self, config):
        """
        初始化Gemini LLM Provider。

        :param config: 包含配置信息的字典，其中应包含 'model_name'（可选，默认为 'gemini-1.5-pro'）和 'api_key'。
        """
        # 从配置字典中获取模型名称，如果没有提供则使用默认值 'gemini-1.5-pro'
        self.model_name = config.get("model_name", "gemini-1.5-pro")
        # 从配置字典中获取API密钥
        self.api_key = config.get("api_key")

        # 调用检查模型密钥的函数，检查是否有有效的API密钥
        have_key = check_model_key("LLM", self.api_key)

        # 如果没有有效的API密钥，直接返回，不进行后续初始化操作
        if not have_key:
            return

        try:
            # 使用获取到的API密钥初始化Gemini客户端
            genai.configure(api_key=self.api_key)
            # 根据指定的模型名称创建一个生成式模型实例
            self.model = genai.GenerativeModel(self.model_name)

            # 设置生成参数，用于控制模型生成文本的行为
            self.generation_config = {
                # 温度参数，控制生成文本的随机性，值越高越随机
                "temperature": 0.7,
                # 核采样概率，用于筛选可能的下一个词
                "top_p": 0.9,
                # 核采样数量，用于筛选可能的下一个词
                "top_k": 40,
                # 最大输出令牌数，限制生成文本的长度
                "max_output_tokens": 2048,
            }
            # 初始化聊天会话为None，后续会根据需要创建
            self.chat = None
        except Exception as e:
            # 记录错误日志，表明Gemini初始化失败，并包含具体的异常信息
            logger.bind(tag=TAG).error(f"Gemini初始化失败: {e}")
            # 如果初始化失败，将模型实例设置为None
            self.model = None

    # 定义一个生成器方法，用于处理对话响应
    def response(self, session_id, dialogue):
        """
        生成Gemini对话响应。

        :param session_id: 表示当前会话的唯一标识符。
        :param dialogue: 包含对话消息的列表，每个消息是一个字典，包含 'role' 和 'content' 键。
        :return: 一个生成器，逐块生成Gemini模型返回的答案。
        """
        # 检查模型是否正确初始化，如果没有则通过生成器返回错误提示信息并结束方法
        if not self.model:
            yield "【Gemini服务未正确初始化】"
            return

        try:
            # 初始化一个空列表，用于存储对话历史
            chat_history = []
            # 遍历对话列表，除了最后一条消息，将其转换为适合Gemini模型的格式
            for msg in dialogue[:-1]:  # 历史对话
                # 根据消息的角色（assistant或user），将其转换为模型能识别的角色（model或user）
                role = "model" if msg["role"] == "assistant" else "user"
                # 去除消息内容的首尾空格
                content = msg["content"].strip()
                # 如果内容不为空，则将其添加到对话历史列表中
                if content:
                    chat_history.append({
                        "role": role,
                        "parts": [content]
                    })

            # 获取对话列表中的最后一条消息的内容，作为当前要发送的消息
            current_msg = dialogue[-1]["content"]

            # 使用指定的对话历史创建一个新的聊天会话
            chat = self.model.start_chat(history=chat_history)

            # 向模型发送当前消息，并开启流式响应模式，同时应用之前设置的生成参数
            response = chat.send_message(
                current_msg,
                stream=True,
                generation_config=self.generation_config
            )

            # 遍历流式响应的每个块
            for chunk in response:
                # 检查块是否有 'text' 属性，并且该属性不为空
                if hasattr(chunk, 'text') and chunk.text:
                    # 通过生成器逐块返回模型生成的文本
                    yield chunk.text

        except Exception as e:
            # 将异常信息转换为字符串
            error_msg = str(e)
            # 记录错误日志，表明Gemini响应生成错误，并包含具体的错误信息
            logger.bind(tag=TAG).error(f"Gemini响应生成错误: {error_msg}")

            # 根据不同的错误信息，通过生成器返回友好的提示信息
            if "Rate limit" in error_msg:
                yield "【Gemini服务请求太频繁,请稍后再试】"
            elif "Invalid API key" in error_msg:
                yield "【Gemini API key无效】"
            else:
                yield f"【Gemini服务响应异常: {error_msg}】"