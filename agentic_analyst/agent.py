"""
Agent 核心引擎 — ReAct 模式的自主数据分析 Agent

实现"观察 -> 思考 -> 行动 -> 反思"的自主分析循环。
使用 OpenAI-compatible API 的 function calling 能力。
"""

import json
import os
import sys
import io
import time

# 修复 Windows 终端编码（防止多次重包装导致流被关闭）
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from openai import OpenAI
from .tools.toolkit import TOOL_DEFINITIONS, call_tool, init_database


# ========== Agent 系统提示词 ==========

SYSTEM_PROMPT = """你是一位资深的数据分析师 Agent（代号：DataSherlock）。你的工作方式不是简单回答问题，而是像一位真正的业务分析师一样，自主完成完整的分析任务。

## 你的核心能力
1. **自主查数据**：通过 SQL 查询 DuckDB 数据库
2. **自主编程分析**：编写 Python 代码做统计分析、数据清洗、可视化
3. **假设驱动**：像侦探一样，先提假设，再用数据验证或推翻

## 你的分析方法论

### 第一步：理解问题与数据（Inspector 阶段）
- 先查看数据结构和样本
- 明确关键指标的定义和计算口径
- 识别需要分析的时间范围和对比基准

### 第二步：全局扫描（Overview 阶段）
- 用 SQL 做维度下钻，找出哪些维度的变化贡献了最大的异动
- 注意数据质量问题（空值、负值、异常值），必要时做清洗

### 第三步：假设验证循环（Hypothesis Testing 阶段）
- 基于初步发现，形成 MECE（互相独立、完全穷尽）的假设树
- 对每个假设设计验证查询
- 用统计方法（如同比环比、方差分析、贡献度分解）验证假设
- 逐步缩小范围，锁定根因

### 第四步：深度诊断（Deep Dive 阶段）
- 对锁定的根因做时间序列分析
- 计算影响的量化指标（贡献了多少个百分点的变化）
- 生成高质量可视化图表

### 第五步：撰写报告（Reporting 阶段）
- 用金字塔原理组织结论：先说结论、再说证据
- 必须输出至少 2-3 张图表
- 提供可落地的业务建议

## 重要规则
1. 每次执行操作前，先用一句话说明你要做什么、为什么
2. 如果 SQL 或代码报错，分析错误原因并自动修正重试
3. 不要凭空编造数据——所有结论必须有查询结果支撑
4. 数据中可能有脏数据（负值、空值、极端值），要做清洗
5. 绘图时必须保存到 output_dir 目录，使用中文标签
6. 最终要输出一份结构化的分析报告
"""


REPORT_PROMPT = """基于你刚才完成的所有分析工作，现在请生成一份结构化的 HTML 分析报告。

报告格式要求：
1. 使用精美的 HTML 格式，直接输出 HTML 代码
2. 包含以下部分：
   - 📊 Executive Summary（管理层摘要）：2-3 句话总结核心发现
   - 🔍 分析背景与目标
   - 📈 关键发现（逐条列出，标注量化数据）
   - 📉 根因深度分析（附图表引用）
   - 💡 行动建议（3-5 条可落地的建议）
   - 📋 数据附录（关键统计数据表格）
3. 图表以 base64 嵌入 <img> 标签
4. 配色使用专业的商务蓝色调
5. 确保中文字体显示正常

请直接用 run_python_code 工具生成完整的 HTML 报告文件，保存到 output_dir/report.html。
"""


class AgenticAnalyst:
    """自主数据分析 Agent"""
    
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = "gpt-4o",
        max_iterations: int = 25,
        verbose: bool = True,
    ):
        """
        初始化 Agent。
        
        Args:
            api_key: OpenAI API Key（或兼容 API）
            base_url: API 基础 URL（可选，用于接入其他 LLM）
            model: 模型名称
            max_iterations: 最大迭代次数（防止无限循环）
            verbose: 是否打印详细过程
        """
        self.model = model
        self.max_iterations = max_iterations
        self.verbose = verbose
        
        client_kwargs = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url
            
        self.client = OpenAI(**client_kwargs)
        self.messages = []
        self.analysis_log = []  # 记录分析过程
        self.generated_charts = []  # 记录生成的图表路径
    
    def _log(self, role: str, content: str, truncate: int = 500):
        """日志输出"""
        if self.verbose:
            display = content[:truncate] + "..." if len(content) > truncate else content
            print(f"\n{'='*60}", flush=True)
            print(f"[{role.upper()}]", flush=True)
            print(f"{display}", flush=True)
            print(f"{'='*60}", flush=True)
    
    def load_data(self, csv_path: str) -> str:
        """加载数据到 DuckDB"""
        result = init_database(csv_path)
        self._log("SYSTEM", f"数据库加载: {result}")
        return result
    
    def _chat_completion(self, messages: list, tools: list = None) -> dict:
        """调用 LLM"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # 分析任务需要低温度
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message
    
    def analyze(self, goal: str, data_path: str) -> str:
        """
        执行完整的分析任务。
        
        Args:
            goal: 用户的分析目标（自然语言描述）
            data_path: 数据文件路径
            
        Returns:
            最终的分析报告路径
        """
        print(f"\n{'🚀'*20}", flush=True)
        print(f"DataSherlock Agent 启动", flush=True)
        print(f"分析目标: {goal}", flush=True)
        print(f"数据路径: {data_path}", flush=True)
        print(f"{'🚀'*20}\n", flush=True)
        
        # 1. 加载数据
        db_info = self.load_data(data_path)
        
        # 2. 构建初始消息
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""## 分析任务

**目标**：{goal}

**数据源信息**：
{db_info}

请开始你的分析工作。记住：
1. 先用 SQL 了解数据全貌
2. 按维度逐层下钻找异动
3. 锁定根因后做量化验证
4. 最后生成可视化图表

开始吧，DataSherlock！"""}
        ]
        
        # 3. ReAct 循环
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n🔄 迭代 {iteration}/{self.max_iterations}", flush=True)
            
            # 调用 LLM
            try:
                response = self._chat_completion(self.messages, tools=TOOL_DEFINITIONS)
            except Exception as e:
                print(f"❌ API 调用失败: {e}")
                time.sleep(2)
                continue
            
            # 处理响应
            if response.content:
                self._log("AGENT 思考", response.content)
                self.analysis_log.append({
                    "iteration": iteration,
                    "type": "thinking",
                    "content": response.content
                })
            
            # 如果没有工具调用，说明分析完成
            if not response.tool_calls:
                self._log("AGENT", "分析阶段完成，没有更多工具调用。")
                self.messages.append({"role": "assistant", "content": response.content})
                break
            
            # 处理工具调用
            self.messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response.tool_calls
                ]
            })
            
            for tool_call in response.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    func_args = {"error": "无法解析参数"}
                
                self._log("TOOL CALL", f"{func_name}({json.dumps(func_args, ensure_ascii=False)[:300]})")
                
                # 执行工具
                result = call_tool(func_name, func_args)
                
                self._log("TOOL RESULT", result)
                
                self.analysis_log.append({
                    "iteration": iteration,
                    "type": "tool_call",
                    "tool": func_name,
                    "args_preview": json.dumps(func_args, ensure_ascii=False)[:200],
                    "result_preview": result[:300]
                })
                
                # 记录生成的图表
                if "生成的文件" in result:
                    for line in result.split("\n"):
                        if line.strip().endswith(('.png', '.jpg', '.svg', '.html')):
                            self.generated_charts.append(line.strip())
                
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        
        # 4. 生成最终报告
        print(f"\n{'📝'*20}")
        print("进入报告生成阶段...")
        print(f"{'📝'*20}\n")
        
        self.messages.append({
            "role": "user",
            "content": REPORT_PROMPT
        })
        
        # 报告生成也可能需要多次工具调用
        report_iterations = 0
        while report_iterations < 5:
            report_iterations += 1
            
            try:
                response = self._chat_completion(self.messages, tools=TOOL_DEFINITIONS)
            except Exception as e:
                print(f"❌ 报告生成 API 调用失败: {e}")
                break
            
            if response.content:
                self._log("REPORT AGENT", response.content)
            
            if not response.tool_calls:
                self.messages.append({"role": "assistant", "content": response.content})
                break
            
            self.messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response.tool_calls
                ]
            })
            
            for tool_call in response.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                self._log("REPORT TOOL", f"{func_name}")
                
                result = call_tool(func_name, func_args)
                self._log("REPORT RESULT", result)
                
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        
        # 5. 保存分析日志
        log_path = "agentic_analyst/output/analysis_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.analysis_log, f, ensure_ascii=False, indent=2)
        
        # 检查报告生成路径
        candidates = [
            "agentic_analyst/output/report.html",
            "output/report.html",
            "./report.html"
        ]
        report_path = None
        for c in candidates:
            if os.path.exists(c):
                report_path = os.path.abspath(c)
                break
                
        if report_path:
            print(f"\n{'✅'*20}", flush=True)
            print(f"分析完成！报告已保存至: {report_path}", flush=True)
            print(f"分析日志: {log_path}", flush=True)
            print(f"生成图表: {len(self.generated_charts)} 张", flush=True)
            print(f"总迭代次数: {iteration + report_iterations}", flush=True)
            print(f"{'✅'*20}", flush=True)
            return report_path
        else:
            print(f"\n⚠️ 报告文件未生成，请检查分析日志: {log_path}", flush=True)
            return log_path
