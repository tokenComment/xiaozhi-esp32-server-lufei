import time
import aiohttp
import asyncio
from tabulate import tabulate
from typing import Dict, List
from core.utils.llm import create_instance as create_llm_instance
from core.utils.tts import create_instance as create_tts_instance
from core.utils.util import read_config
import statistics
from config.settings import get_config_file
import inspect
import os
import logging

# 设置全局日志级别为WARNING，抑制INFO级别日志
logging.basicConfig(level=logging.WARNING)


class AsyncPerformanceTester:
    def __init__(self):
        # 读取配置文件，get_config_file 函数应该用于获取配置文件路径，read_config 函数用于读取配置文件内容
        self.config = read_config(get_config_file())
        # 从配置文件中获取测试语句列表，如果配置文件中没有相应配置，则使用默认的测试语句列表
        self.test_sentences = self.config.get("module_test", {}).get(
            "test_sentences",
            ["你好，请介绍一下你自己", "What's the weather like today?",
             "请用100字概括量子计算的基本原理和应用前景"]
        )
        # 初始化结果字典，用于存储不同模块（如大语言模型、文本转语音）的性能测试结果以及组合测试结果
        self.results = {
            "llm": {},
            "tts": {},
            "combinations": []
        }

    async def _check_ollama_service(self, base_url: str, model_name: str) -> bool:
        """异步检查Ollama服务状态"""
        # 创建一个异步的 HTTP 客户端会话，用于发送 HTTP 请求
        async with aiohttp.ClientSession() as session:
            try:
                # 检查服务是否可用
                # 向 Ollama 服务的 /api/version 端点发送 GET 请求
                async with session.get(f"{base_url}/api/version") as response:
                    # 如果响应状态码不是 200，表示服务不可用，打印错误信息并返回 False
                    if response.status != 200:
                        print(f"🚫 Ollama服务未启动或无法访问: {base_url}")
                        return False

                # 检查模型是否存在
                # 向 Ollama 服务的 /api/tags 端点发送 GET 请求，获取可用模型列表
                async with session.get(f"{base_url}/api/tags") as response:
                    # 如果响应状态码为 200，表示成功获取模型列表
                    if response.status == 200:
                        # 异步解析响应的 JSON 数据
                        data = await response.json()
                        # 从 JSON 数据中提取模型列表
                        models = data.get("models", [])
                        # 检查指定的模型名称是否在可用模型列表中
                        if not any(model["name"] == model_name for model in models):
                            # 如果模型不存在，打印错误信息并返回 False
                            print(f"🚫 Ollama模型 {model_name} 未找到，请先使用 ollama pull {model_name} 下载")
                            return False
                    else:
                        # 如果无法获取模型列表，打印错误信息并返回 False
                        print(f"🚫 无法获取Ollama模型列表")
                        return False
                # 如果服务和模型都正常，返回 True
                return True
            except Exception as e:
                # 如果在检查过程中出现异常，打印错误信息并返回 False
                print(f"🚫 无法连接到Ollama服务: {str(e)}")
                return False

    async def _test_tts(self, tts_name: str, config: Dict) -> Dict:
        """异步测试单个TTS性能"""
        try:
            # 设置日志级别，将 core.providers.tts.base 模块的日志级别设置为 WARNING，减少不必要的日志输出
            logging.getLogger("core.providers.tts.base").setLevel(logging.WARNING)

            # 定义可能包含访问令牌的字段列表
            token_fields = ["access_token", "api_key", "token"]
            # 检查配置中是否存在未配置的访问令牌，如果配置中包含 "你的" 或 "placeholder" 等占位符，认为未配置
            if any(field in config and any(x in config[field] for x in ["你的", "placeholder"]) for field in
                token_fields):
                # 若未配置，打印跳过信息并返回错误结果
                print(f"⏭️  TTS {tts_name} 未配置access_token/api_key，已跳过")
                return {"name": tts_name, "type": "tts", "errors": 1}

            # 从配置中获取模块类型，如果未指定则使用 TTS 名称
            module_type = config.get('type', tts_name)
            # 创建 TTS 实例，调用 create_tts_instance 函数，传入模块类型、配置信息，并设置删除音频文件
            tts = create_tts_instance(
                module_type,
                config,
                delete_audio_file=True
            )

            # 打印开始测试的信息
            print(f"🎵 测试 TTS: {tts_name}")

            # 生成一个临时文件名
            tmp_file = tts.generate_filename()
            # 调用 TTS 实例的 text_to_speak 方法，将 "连接测试" 文本转换为语音并保存到临时文件
            await tts.text_to_speak("连接测试", tmp_file)

            # 检查临时文件是否生成，如果文件不存在，认为连接失败
            if not tmp_file or not os.path.exists(tmp_file):
                print(f"❌ {tts_name} 连接失败")
                return {"name": tts_name, "type": "tts", "errors": 1}

            # 初始化总耗时为 0
            total_time = 0
            # 确定测试句子的数量，取前两个测试句子
            test_count = len(self.test_sentences[:2])

            # 遍历前两个测试句子
            for i, sentence in enumerate(self.test_sentences[:2], 1):
                # 记录开始时间
                start = time.time()
                # 生成一个新的临时文件名
                tmp_file = tts.generate_filename()
                # 调用 TTS 实例的 text_to_speak 方法，将测试句子转换为语音并保存到临时文件
                await tts.text_to_speak(sentence, tmp_file)
                # 计算本次转换的耗时
                duration = time.time() - start
                # 累加总耗时
                total_time += duration

                # 检查临时文件是否生成，如果文件存在，打印成功信息；否则打印失败信息并返回错误结果
                if tmp_file and os.path.exists(tmp_file):
                    print(f"✓ {tts_name} [{i}/{test_count}]")
                else:
                    print(f"✗ {tts_name} [{i}/{test_count}]")
                    return {"name": tts_name, "type": "tts", "errors": 1}

            # 测试成功，返回包含 TTS 名称、类型、平均耗时和错误数量的结果字典
            return {
                "name": tts_name,
                "type": "tts",
                "avg_time": total_time / test_count,
                "errors": 0
            }

        except Exception as e:
            # 若测试过程中出现异常，打印错误信息并返回错误结果
            print(f"⚠️ {tts_name} 测试失败: {str(e)}")
            return {"name": tts_name, "type": "tts", "errors": 1}

    async def _test_llm(self, llm_name: str, config: Dict) -> Dict:
        """异步测试单个LLM性能"""
        try:
            # 对于Ollama，跳过api_key检查并进行特殊处理
            if llm_name == "Ollama":
                # 从配置中获取Ollama服务的基础URL，若未配置则使用默认值
                base_url = config.get('base_url', 'http://localhost:11434')
                # 从配置中获取Ollama使用的模型名称
                model_name = config.get('model_name')
                # 若未配置模型名称，打印错误信息并返回包含错误信息的字典
                if not model_name:
                    print(f"🚫 Ollama未配置model_name")
                    return {"name": llm_name, "type": "llm", "errors": 1}
                # 调用 _check_ollama_service 方法检查Ollama服务和模型是否可用，若不可用则返回错误信息
                if not await self._check_ollama_service(base_url, model_name):
                    return {"name": llm_name, "type": "llm", "errors": 1}
            else:
                # 对于非Ollama的LLM，检查api_key是否配置，若包含占位符则跳过该LLM的测试
                if "api_key" in config and any(x in config["api_key"] for x in ["你的", "placeholder", "sk-xxx"]):
                    print(f"🚫 跳过未配置的LLM: {llm_name}")
                    return {"name": llm_name, "type": "llm", "errors": 1}

            # 获取实际类型（兼容旧配置），若配置中未指定 type 则使用 llm_name
            module_type = config.get('type', llm_name)
            # 根据模块类型和配置创建LLM实例
            llm = create_llm_instance(module_type, config)

            # 统一使用UTF-8编码，将测试句子列表中的每个句子进行编码和解码操作
            test_sentences = [s.encode('utf-8').decode('utf-8') for s in self.test_sentences]

            # 创建所有句子的测试任务
            sentence_tasks = []
            # 遍历测试句子列表，为每个句子创建一个测试任务
            for sentence in test_sentences:
                sentence_tasks.append(self._test_single_sentence(llm_name, llm, sentence))

            # 并发执行所有句子测试，使用 asyncio.gather 并发执行所有测试任务并等待结果
            sentence_results = await asyncio.gather(*sentence_tasks)

            # 处理结果，过滤掉结果列表中为 None 的项，得到有效的结果列表
            valid_results = [r for r in sentence_results if r is not None]
            # 若有效结果列表为空，说明可能配置错误，打印警告信息并返回错误信息
            if not valid_results:
                print(f"⚠️  {llm_name} 无有效数据，可能配置错误")
                return {"name": llm_name, "type": "llm", "errors": 1}

            # 从有效结果列表中提取每个测试句子的首token响应时间和完整响应时间
            first_token_times = [r["first_token_time"] for r in valid_results]
            response_times = [r["response_time"] for r in valid_results]

            # 过滤异常数据，计算完整响应时间的平均值
            mean = statistics.mean(response_times)
            # 计算完整响应时间的标准差，若响应时间列表长度小于等于1则标准差为0
            stdev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            # 过滤掉大于平均值加3倍标准差的响应时间，得到过滤后的响应时间列表
            filtered_times = [t for t in response_times if t <= mean + 3 * stdev]

            # 若过滤后的响应时间列表长度小于测试句子数量的一半，说明有效数据不足，可能网络不稳定，打印警告信息并返回错误信息
            if len(filtered_times) < len(test_sentences) * 0.5:
                print(f"⚠️  {llm_name} 有效数据不足，可能网络不稳定")
                return {"name": llm_name, "type": "llm", "errors": 1}

            # 若测试正常完成，返回包含LLM名称、类型、平均响应时间、平均首token响应时间、首token响应时间标准差、完整响应时间标准差和错误数量的字典
            return {
                "name": llm_name,
                "type": "llm",
                "avg_response": sum(response_times) / len(response_times),
                "avg_first_token": sum(first_token_times) / len(first_token_times),
                "std_first_token": statistics.stdev(first_token_times) if len(first_token_times) > 1 else 0,
                "std_response": statistics.stdev(response_times) if len(response_times) > 1 else 0,
                "errors": 0
            }
        except Exception as e:
            # 若测试过程中出现异常，打印错误信息并返回包含错误信息的字典
            print(f"LLM {llm_name} 测试失败: {str(e)}")
            return {"name": llm_name, "type": "llm", "errors": 1}

    async def _test_single_sentence(self, llm_name: str, llm, sentence: str) -> Dict:
        """测试单个句子的性能"""
        try:
            # 打印开始测试的提示信息，截取句子的前20个字符展示
            print(f"📝 {llm_name} 开始测试: {sentence[:20]}...")
            # 记录测试开始的时间
            sentence_start = time.time()
            # 标记是否接收到首个有效 token，初始为 False
            first_token_received = False
            # 用于存储首个有效 token 出现的时间，初始为 None
            first_token_time = None

            async def process_response():
                """
            处理LLM的响应，检测首个有效 token 并记录时间
                """
                # 声明外部作用域的变量，以便在内部函数中修改
                nonlocal first_token_received, first_token_time
                # 调用 LLM 的 response 方法获取响应的每个数据块
                for chunk in llm.response("perf_test", [{"role": "user", "content": sentence}]):
                    # 如果还未接收到首个有效 token 且当前数据块不为空
                    if not first_token_received and chunk.strip() != '':
                        # 计算从测试开始到首个有效 token 出现的时间
                        first_token_time = time.time() - sentence_start
                        # 标记已接收到首个有效 token
                        first_token_received = True
                        # 打印首个有效 token 出现的时间
                        print(f"✓ {llm_name} 首个Token: {first_token_time:.3f}s")
                    # 以生成器的方式返回每个数据块
                    yield chunk

            # 用于存储 LLM 响应的所有数据块
            response_chunks = []
            # 异步遍历处理响应的生成器，将每个数据块添加到列表中
            async for chunk in process_response():
                response_chunks.append(chunk)

            # 计算从测试开始到完整响应结束的总时间
            response_time = time.time() - sentence_start
            # 打印完整响应结束的时间
            print(f"✓ {llm_name} 完成响应: {response_time:.3f}s")

            # 如果没有检测到首个有效 token，将总响应时间作为首个有效 token 的时间
            if first_token_time is None:
                first_token_time = response_time

            # 返回包含 LLM 名称、类型、首个有效 token 时间和完整响应时间的字典
            return {
                "name": llm_name,
                "type": "llm",
                "first_token_time": first_token_time,
                "response_time": response_time
            }
        except Exception as e:
            # 如果测试过程中出现异常，打印错误信息并返回 None
            print(f"⚠️ {llm_name} 句子测试失败: {str(e)}")
            return None

    def _generate_combinations(self):
        """生成最佳组合建议"""
        # 筛选出有效的大语言模型（LLM）
        # 条件为该LLM测试无错误且平均首个token响应时间大于等于0.05秒
        valid_llms = [
            k for k, v in self.results["llm"].items()
            if v["errors"] == 0 and v["avg_first_token"] >= 0.05
        ]
        # 筛选出有效的文本转语音（TTS）模型
        # 条件为该TTS测试无错误
        valid_tts = [k for k, v in self.results["tts"].items() if v["errors"] == 0]

        # 找出基准值
        # 计算有效LLM中平均首个token响应时间的最小值，若没有有效LLM则设为1
        min_first_token = min([self.results["llm"][llm]["avg_first_token"] for llm in valid_llms]) if valid_llms else 1
        # 计算有效TTS中平均响应时间的最小值，若没有有效TTS则设为1
        min_tts_time = min([self.results["tts"][tts]["avg_time"] for tts in valid_tts]) if valid_tts else 1

        # 遍历所有有效的LLM和TTS进行组合
        for llm in valid_llms:
            for tts in valid_tts:
                # 计算相对性能分数（越小越好）
                # LLM的相对性能分数为该LLM的平均首个token响应时间除以最小平均首个token响应时间
                llm_score = self.results["llm"][llm]["avg_first_token"] / min_first_token
                # TTS的相对性能分数为该TTS的平均响应时间除以最小平均响应时间
                tts_score = self.results["tts"][tts]["avg_time"] / min_tts_time

                # 计算稳定性分数（标准差/平均值，越小越稳定）
                # LLM的稳定性分数为该LLM的首个token响应时间的标准差除以平均首个token响应时间
                llm_stability = self.results["llm"][llm]["std_first_token"] / self.results["llm"][llm][
                    "avg_first_token"]

                # 综合得分（考虑性能和稳定性）
                # 性能权重0.7，稳定性权重0.3
                # 计算LLM的最终得分，综合考虑性能和稳定性
                llm_final_score = llm_score * 0.7 + llm_stability * 0.3

                # 总分 = LLM得分(70%) + TTS得分(30%)
                # 计算LLM和TTS组合的总得分
                total_score = llm_final_score * 0.7 + tts_score * 0.3

                # 将组合信息添加到结果的组合列表中
                self.results["combinations"].append({
                    "llm": llm,
                    "tts": tts,
                    "score": total_score,
                    "details": {
                        "llm_first_token": self.results["llm"][llm]["avg_first_token"],
                        "llm_stability": llm_stability,
                        "tts_time": self.results["tts"][tts]["avg_time"]
                    }
                })

        # 分数越小越好
        # 对组合列表按总得分进行排序，得分小的排在前面
        self.results["combinations"].sort(key=lambda x: x["score"])

    def _print_results(self):
        """打印测试结果"""
        # 初始化用于存储LLM性能数据的表格
        llm_table = []
        # 遍历LLM测试结果
        for name, data in self.results["llm"].items():
            # 只处理测试无错误的LLM
            if data["errors"] == 0:
                # 计算LLM的稳定性，即首字响应时间的标准差与平均首字响应时间的比值
                stability = data["std_first_token"] / data["avg_first_token"]
                # 将LLM的相关数据添加到表格中，包括模型名称、首字耗时、总耗时和稳定性
                llm_table.append([
                    name,  # 不需要固定宽度，让tabulate自己处理对齐
                    f"{data['avg_first_token']:.3f}秒",
                    f"{data['avg_response']:.3f}秒",
                    f"{stability:.3f}"
                ])

        # 如果LLM表格中有数据
        if llm_table:
            # 打印LLM性能排行标题
            print("\nLLM 性能排行:")
            # 使用tabulate库将LLM表格数据格式化为表格并打印
            print(tabulate(
                llm_table,
                headers=["模型名称", "首字耗时", "总耗时", "稳定性"],
                tablefmt="github",
                colalign=("left", "right", "right", "right"),
                disable_numparse=True
            ))
        else:
            # 如果LLM表格中没有数据，打印警告信息
            print("\n⚠️ 没有可用的LLM模块进行测试。")

        # 初始化用于存储TTS性能数据的表格
        tts_table = []
        # 遍历TTS测试结果
        for name, data in self.results["tts"].items():
            # 只处理测试无错误的TTS
            if data["errors"] == 0:
                # 将TTS的相关数据添加到表格中，包括模型名称和合成耗时
                tts_table.append([
                    name,  # 不需要固定宽度
                    f"{data['avg_time']:.3f}秒"
                ])

        # 如果TTS表格中有数据
        if tts_table:
            # 打印TTS性能排行标题
            print("\nTTS 性能排行:")
            # 使用tabulate库将TTS表格数据格式化为表格并打印
            print(tabulate(
                tts_table,
                headers=["模型名称", "合成耗时"],
                tablefmt="github",
                colalign=("left", "right"),
                disable_numparse=True
            ))
        else:
            # 如果TTS表格中没有数据，打印警告信息
            print("\n⚠️ 没有可用的TTS模块进行测试。")

        # 如果有可用的模块组合建议
        if self.results["combinations"]:
            # 打印推荐配置组合标题
            print("\n推荐配置组合 (得分越小越好):")
            # 初始化用于存储组合方案数据的表格
            combo_table = []
            # 遍历前5个组合方案
            for combo in self.results["combinations"][:5]:
                # 将组合方案的相关数据添加到表格中，包括组合名称、综合得分、LLM首字耗时、稳定性和TTS合成耗时
                combo_table.append([
                    f"{combo['llm']} + {combo['tts']}",  # 不需要固定宽度
                    f"{combo['score']:.3f}",
                    f"{combo['details']['llm_first_token']:.3f}秒",
                    f"{combo['details']['llm_stability']:.3f}",
                    f"{combo['details']['tts_time']:.3f}秒"
                ])

            # 使用tabulate库将组合方案表格数据格式化为表格并打印
            print(tabulate(
                combo_table,
                headers=["组合方案", "综合得分", "LLM首字耗时", "稳定性", "TTS合成耗时"],
                tablefmt="github",
                colalign=("left", "right", "right", "right", "right"),
                disable_numparse=True
            ))
        else:
            # 如果没有可用的模块组合建议，打印警告信息
            print("\n⚠️ 没有可用的模块组合建议。")

    def _process_results(self, all_results):
        """处理测试结果"""
        # 遍历所有的测试结果
        for result in all_results:
            # 检查当前测试结果是否没有错误
            if result["errors"] == 0:
                # 判断当前测试结果的类型是否为大语言模型（LLM）
                if result["type"] == "llm":
                    # 如果是LLM类型，将该结果以模型名称为键，存储到 self.results 字典的 "llm" 键对应的子字典中
                    self.results["llm"][result["name"]] = result
                else:
                    # 如果不是LLM类型，默认认为是文本转语音（TTS）类型，将该结果以模型名称为键，存储到 self.results 字典的 "tts" 键对应的子字典中
                    self.results["tts"][result["name"]] = result

    async def run(self):
        """执行全量异步测试"""
        # 打印提示信息，表明开始筛选可用模块
        print("🔍 开始筛选可用模块...")

        # 创建一个空列表，用于存储所有的测试任务
        all_tasks = []

        # 处理LLM测试任务
        # 遍历配置中LLM部分的所有模块及其配置
        for llm_name, config in self.config.get("LLM", {}).items():
            # 检查配置的有效性
            if llm_name == "CozeLLM":
                # 检查 bot_id 和 user_id 是否包含占位符
                if any(x in config.get("bot_id", "") for x in ["你的"]) \
                        or any(x in config.get("user_id", "") for x in ["你的"]):
                    # 若包含占位符，打印跳过信息
                    print(f"⏭️  LLM {llm_name} 未配置bot_id/user_id，已跳过")
                    continue
            # 检查 api_key 是否包含占位符
            elif "api_key" in config and any(x in config["api_key"] for x in ["你的", "placeholder", "sk-xxx"]):
                # 若包含占位符，打印跳过信息
                print(f"⏭️  LLM {llm_name} 未配置api_key，已跳过")
                continue

            # 对于 Ollama 模块，先检查服务状态
            if llm_name == "Ollama":
                # 获取 Ollama 的 base_url，若未配置则使用默认值
                base_url = config.get('base_url', 'http://localhost:11434')
                # 获取 Ollama 的 model_name
                model_name = config.get('model_name')
                if not model_name:
                    # 若未配置 model_name，打印错误信息并跳过
                    print(f"🚫 Ollama未配置model_name")
                    continue

                # 异步检查 Ollama 服务状态，若服务不可用则跳过
                if not await self._check_ollama_service(base_url, model_name):
                    continue

            # 打印添加 LLM 测试任务的信息
            print(f"📋 添加LLM测试任务: {llm_name}")
            # 获取模块类型，若未配置则使用模块名称
            module_type = config.get('type', llm_name)
            # 创建 LLM 实例
            llm = create_llm_instance(module_type, config)

            # 为每个测试句子创建独立的测试任务
            for sentence in self.test_sentences:
                # 对句子进行编码和解码，确保编码格式为 utf-8
                sentence = sentence.encode('utf-8').decode('utf-8')
                # 将测试任务添加到 all_tasks 列表中
                all_tasks.append(self._test_single_sentence(llm_name, llm, sentence))

        # 处理TTS测试任务
        # 遍历配置中 TTS 部分的所有模块及其配置
        for tts_name, config in self.config.get("TTS", {}).items():
            # 定义需要检查的令牌字段
            token_fields = ["access_token", "api_key", "token"]
            # 检查令牌字段是否包含占位符
            if any(field in config and any(x in config[field] for x in ["你的", "placeholder"]) for field in
                token_fields):
                # 若包含占位符，打印跳过信息
                print(f"⏭️  TTS {tts_name} 未配置access_token/api_key，已跳过")
                continue
            # 打印添加 TTS 测试任务的信息
            print(f"🎵 添加TTS测试任务: {tts_name}")
            # 将 TTS 测试任务添加到 all_tasks 列表中
            all_tasks.append(self._test_tts(tts_name, config))

        # 打印找到的可用 LLM 模块数量
        print(
            f"\n✅ 找到 {len([t for t in all_tasks if 'test_single_sentence' in str(t)]) / len(self.test_sentences):.0f} 个可用LLM模块")
        # 打印找到的可用 TTS 模块数量
        print(f"✅ 找到 {len([t for t in all_tasks if '_test_tts' in str(t)])} 个可用TTS模块")
        # 打印提示信息，表明开始并发测试所有模块
        print("\n⏳ 开始并发测试所有模块...\n")

        # 并发执行所有测试任务，并获取结果
        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # 处理LLM结果
        # 创建一个空字典，用于存储 LLM 测试结果
        llm_results = {}
        # 遍历所有测试结果，筛选出 LLM 类型的结果
        for result in [r for r in all_results if r and isinstance(r, dict) and r.get("type") == "llm"]:
            # 获取 LLM 模块名称
            llm_name = result["name"]
            if llm_name not in llm_results:
                # 若该 LLM 模块结果未在 llm_results 中，初始化其结果
                llm_results[llm_name] = {
                    "name": llm_name,
                    "type": "llm",
                    "first_token_times": [],
                    "response_times": [],
                    "errors": 0
                }
            # 将该 LLM 模块的首次令牌时间添加到对应的列表中
            llm_results[llm_name]["first_token_times"].append(result["first_token_time"])
            # 将该 LLM 模块的响应时间添加到对应的列表中
            llm_results[llm_name]["response_times"].append(result["response_time"])

        # 计算LLM平均值和标准差
        # 遍历 llm_results 中的所有 LLM 模块结果
        for llm_name, data in llm_results.items():
            # 检查该 LLM 模块的首次令牌时间数量是否达到测试句子数量的一半以上
            if len(data["first_token_times"]) >= len(self.test_sentences) * 0.5:
                # 计算平均响应时间
                avg_response = sum(data["response_times"]) / len(data["response_times"])
                # 计算平均首次令牌时间
                avg_first_token = sum(data["first_token_times"]) / len(data["first_token_times"])
                # 计算首次令牌时间的标准差
                std_first_token = statistics.stdev(data["first_token_times"]) if len(
                    data["first_token_times"]) > 1 else 0
                # 计算响应时间的标准差
                std_response = statistics.stdev(data["response_times"]) if len(data["response_times"]) > 1 else 0
                # 将计算结果存储到 self.results 中
                self.results["llm"][llm_name] = {
                    "name": llm_name,
                    "type": "llm",
                    "avg_response": avg_response,
                    "avg_first_token": avg_first_token,
                    "std_first_token": std_first_token,
                    "std_response": std_response,
                    "errors": 0
                }

        # 处理TTS结果
        # 遍历所有测试结果，筛选出 TTS 类型且无错误的结果
        for result in [r for r in all_results if r and isinstance(r, dict) and r.get("type") == "tts"]:
            if result["errors"] == 0:
                # 将无错误的 TTS 结果存储到 self.results 中
                self.results["tts"][result["name"]] = result

        # 生成组合建议并打印结果
        # 打印提示信息，表明开始生成测试报告
        print("\n📊 生成测试报告...")
        # 生成组合建议
        self._generate_combinations()
        # 打印测试结果
        self._print_results()


async def main():
    # 创建一个 AsyncPerformanceTester 类的实例
    # AsyncPerformanceTester 类应该是用于进行异步性能测试的类，不过代码里未给出其定义
    tester = AsyncPerformanceTester()
    # 调用 tester 对象的 run 方法，该方法应该是一个异步方法，用于执行性能测试操作
    # await 关键字用于等待该异步方法执行完成
    await tester.run()

# 当该脚本作为主程序运行时执行以下代码
if __name__ == "__main__":
    # 使用 asyncio.run 函数来运行异步的 main 函数
    # asyncio.run 函数会自动创建并管理事件循环，确保异步代码能够正确执行
    asyncio.run(main())