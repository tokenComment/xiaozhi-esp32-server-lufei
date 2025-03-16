# 从上级目录的 base 模块中导入 MemoryProviderBase 基类和日志记录器，MemoryProviderBase 作为基类为当前类提供基础功能和属性，日志记录器用于记录程序运行过程中的信息和错误
from ..base import MemoryProviderBase, logger
# 导入 time 模块，用于获取当前时间并进行时间格式化，以便记录记忆更新的时间等操作
import time
# 导入 json 模块，用于处理 JSON 数据，如解析和生成 JSON 字符串，这对于与大语言模型交互获取记忆数据以及存储记忆数据至关重要
import json
# 导入 os 模块，用于进行文件和目录操作，如检查文件是否存在，以便加载和保存记忆文件
import os
# 导入 yaml 模块，用于处理 YAML 数据，如加载和保存 YAML 文件，因为记忆数据以 YAML 格式存储在文件中
import yaml
# 从 core.utils.util 模块中导入 get_project_dir 函数，用于获取项目的根目录，以便构建记忆文件的路径
from core.utils.util import get_project_dir

# 定义短期记忆提示信息，它是一个字符串，包含了记忆管理的规则和要求，这些规则用于指导大语言模型如何根据对话记录总结用户的重要信息，以构建可生长的动态记忆网络，提供个性化服务。包括三维度记忆评估（时效性、情感强度、关联密度）、动态更新机制（如名字变更处理）、空间优化策略（信息压缩术和淘汰预警）以及规定的记忆结构（以特定的 JSON 格式呈现）
short_term_memory_prompt = """
# 时空记忆编织者

## 核心使命
构建可生长的动态记忆网络，在有限空间内保留关键信息的同时，智能维护信息演变轨迹
根据对话记录，总结user的重要信息，以便在未来的对话中提供更个性化的服务

## 记忆法则
### 1. 三维度记忆评估（每次更新必执行）
| 维度       | 评估标准                  | 权重分 |
|------------|---------------------------|--------|
| 时效性     | 信息新鲜度（按对话轮次） | 40%    |
| 情感强度   | 含💖标记/重复提及次数     | 35%    |
| 关联密度   | 与其他信息的连接数量      | 25%    |

### 2. 动态更新机制
**名字变更处理示例：**
原始记忆："曾用名": ["张三"], "现用名": "张三丰"
触发条件：当检测到「我叫X」「称呼我Y」等命名信号时
操作流程：
1. 将旧名移入"曾用名"列表
2. 记录命名时间轴："2024-02-15 14:32:启用张三丰"
3. 在记忆立方追加：「从张三到张三丰的身份蜕变」

### 3. 空间优化策略
- **信息压缩术**：用符号体系提升密度
  - ✅"张三丰[北/软工/🐱]"
  - ❌"北京软件工程师，养猫"
- **淘汰预警**：当总字数≥900时触发
  1. 删除权重分<60且3轮未提及的信息
  2. 合并相似条目（保留时间戳最近的）

## 记忆结构
输出格式必须为可解析的json字符串，不需要解释、注释和说明，保存记忆时仅从对话提取信息，不要混入示例内容
```json
{
  "时空档案": {
    "身份图谱": {
      "现用名": "",
      "特征标记": [] 
    },
    "记忆立方": [
      {
        "事件": "入职新公司",
        "时间戳": "2024-03-20",
        "情感值": 0.9,
        "关联项": ["下午茶"],
        "保鲜期": 30 
      }
    ]
  },
  "关系网络": {
    "高频话题": {"职场": 12},
    "暗线联系": [""]
  },
  "待响应": {
    "紧急事项": ["需立即处理的任务"], 
    "潜在关怀": ["可主动提供的帮助"]
  },
  "高光语录": [
    "最打动人心的瞬间，强烈的情感表达，user的原话"
  ]
}
```
"""
# 定义一个函数，用于从包含 JSON 代码块的文本中提取出 JSON 数据
def extract_json_data(json_code):
    # 查找文本中 JSON 代码块的起始标记 "```json"
    start = json_code.find("```json")
    # 从起始标记之后开始查找 JSON 代码块的结束标记 "```"
    end = json_code.find("```", start + 1)
    # 打印起始和结束位置（调试用，可根据需要启用或禁用）
    # print("start:", start, "end:", end)
    # 如果没有找到起始或结束标记
    if start == -1 or end == -1:
        try:
            # 尝试直接将文本解析为 JSON 数据
            jsonData = json.loads(json_code)
            # 如果解析成功，返回原文本
            return json_code
        except Exception as e:
            # 如果解析失败，打印错误信息
            print("Error:", e)
        # 如果提取和解析都失败，返回空字符串
        return ""
    # 提取出 JSON 代码块的内容
    jsonData = json_code[start + 7:end]
    return jsonData

# 获取当前模块的名称，作为日志记录的标签
TAG = __name__

# 定义 MemoryProvider 类，继承自 MemoryProviderBase 基类，用于管理用户的短期记忆
class MemoryProvider(MemoryProviderBase):
    def __init__(self, config):
        # 调用父类的初始化方法，继承父类的属性和方法
        super().__init__(config)
        # 初始化短期记忆为空字符串，用于存储用户的短期记忆信息
        self.short_momery = ""
        # 构建存储记忆的 YAML 文件的路径，使用项目根目录和指定的文件名
        self.memory_path = get_project_dir() + 'data/.memory.yaml'
        # 调用 load_memory 方法，从文件中加载记忆数据
        self.load_memory()

    def init_memory(self, role_id, llm):
        # 调用父类的 init_memory 方法，进行父类相关的初始化操作
        super().init_memory(role_id, llm)
        # 调用 load_memory 方法，从文件中加载记忆数据
        self.load_memory()

    def load_memory(self):
        # 初始化一个空字典，用于存储从文件中加载的所有记忆数据
        all_memory = {}
        # 检查记忆文件是否存在
        if os.path.exists(self.memory_path):
            # 以只读模式打开记忆文件
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                # 使用 yaml.safe_load 方法加载文件内容，如果文件为空则返回空字典
                all_memory = yaml.safe_load(f) or {}
        # 检查当前角色的记忆是否存在于所有记忆数据中
        if self.role_id in all_memory:
            # 如果存在，将该角色的记忆赋值给 short_momery 属性
            self.short_momery = all_memory[self.role_id]

    def save_memory_to_file(self):
        # 初始化一个空字典，用于存储从文件中加载的所有记忆数据
        all_memory = {}
        # 检查记忆文件是否存在
        if os.path.exists(self.memory_path):
            # 以只读模式打开记忆文件
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                # 使用 yaml.safe_load 方法加载文件内容，如果文件为空则返回空字典
                all_memory = yaml.safe_load(f) or {}
        # 将当前角色的短期记忆更新到所有记忆数据中
        all_memory[self.role_id] = self.short_momery
        # 以写入模式打开记忆文件
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            # 使用 yaml.dump 方法将更新后的所有记忆数据保存到文件中，允许使用 Unicode 字符
            yaml.dump(all_memory, f, allow_unicode=True)

    async def save_memory(self, msgs):
        # 检查大语言模型是否已经设置
        if self.llm is None:
            # 如果未设置，记录错误日志并返回 None
            logger.bind(tag=TAG).error("LLM is not set for memory provider")
            return None
        # 检查对话消息的数量是否少于 2 条
        if len(msgs) < 2:
            # 如果少于 2 条，返回 None
            return None
        # 初始化一个空字符串，用于存储对话消息的文本
        msgStr = ""
        # 遍历对话消息列表
        for msg in msgs:
            if msg.role == "user":
                # 如果消息角色是用户，将用户消息添加到文本中
                msgStr += f"User: {msg.content}\n"
            elif msg.role == "assistant":
                # 如果消息角色是助手，将助手消息添加到文本中
                msgStr += f"Assistant: {msg.content}\n"
        # 检查短期记忆是否不为空
        if len(self.short_momery) > 0:
            # 如果不为空，添加历史记忆提示和历史记忆内容
            msgStr += "历史记忆：\n"
            msgStr += self.short_momery
        # 获取当前时间并格式化为指定的字符串格式
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        # 将当前时间添加到文本中
        msgStr += f"当前时间：{time_str}"
        # 调用大语言模型的非流式响应方法，根据短期记忆提示和对话文本生成新的记忆
        result = self.llm.response_no_stream(short_term_memory_prompt, msgStr)
        # 从生成的结果中提取 JSON 数据
        json_str = extract_json_data(result)
        try:
            # 尝试将提取的 JSON 数据解析为 Python 对象，检查 JSON 格式是否正确
            json_data = json.loads(json_str)
            # 如果解析成功，将提取的 JSON 数据赋值给短期记忆
            self.short_momery = json_str
        except Exception as e:
            # 如果解析失败，打印错误信息
            print("Error:", e)
        # 调用 save_memory_to_file 方法，将更新后的短期记忆保存到文件中
        self.save_memory_to_file()
        # 记录信息日志，表明记忆保存成功
        logger.bind(tag=TAG).info(f"Save memory successful - Role: {self.role_id}")
        # 返回更新后的短期记忆
        return self.short_momery

    async def query_memory(self, query: str) -> str:
        # 返回当前角色的短期记忆
        return self.short_momery