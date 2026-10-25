# Agentic Data Analyst (智能代理型分析师)

> 一个能自主执行数据分析任务的 AI Agent。给它一个业务分析目标，它会自动查数据、清洗、建模、画图，最后交付一份完整的 HTML 分析报告。

## 🏗️ 项目结构

```
AiAgent/
├── agentic_analyst/
│   ├── __init__.py          # 包定义
│   ├── agent.py             # Agent 核心引擎（ReAct 循环 + LLM 调度）
│   ├── data_generator.py    # 模拟数据生成器（含暗藏 Bug）
│   ├── main.py              # 启动入口
│   ├── tools/
│   │   ├── __init__.py
│   │   └── toolkit.py       # Agent 工具箱（SQL查询 + Python执行）
│   ├── templates/           # 报告模板（预留）
│   └── output/              # 输出目录（图表 + 报告）
├── data/
│   └── funnel_data.csv      # 生成的模拟数据
├── test_pipeline.py         # 工具链验证脚本
├── requirements.txt         # Python 依赖
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 验证工具链

```bash
python test_pipeline.py
```

### 3. 运行 Agent 分析

```bash
# 使用 OpenAI API
set OPENAI_API_KEY=sk-xxx
python agentic_analyst/main.py

# 使用其他 LLM API（Deepseek / 通义 / Moonshot 等 OpenAI 兼容接口）
python agentic_analyst/main.py ^
    --base-url https://api.deepseek.com/v1 ^
    --api-key YOUR_KEY ^
    --model deepseek-chat

# 自定义分析目标
python agentic_analyst/main.py --goal "分析9月份华东区转化率下降的原因"
```

## 🧪 测试场景

数据中暗藏了一个 Bug：**9月份华东区 iOS 端支付宝支付通道出现故障**，导致该细分人群支付成功率从 ~73% 暴跌到 ~0%，拉低整个华东区转化率约 2.4 个百分点。

Agent 的任务是在不知情的情况下，通过自主探索找出这个根因。

## 🔧 核心架构

```
用户目标 → Agent（LLM + ReAct 循环）→ 工具调用（SQL / Python）→ 分析报告
```

- **query_database**: 用 DuckDB SQL 查询数据，支持自由维度下钻
- **run_python_code**: 在受控环境中执行 Python 代码，支持 pandas/numpy/seaborn/scipy
- **ReAct Loop**: 观察→思考→行动→反思 的自主循环，最多 25 轮迭代

## 📊 输出

- `agentic_analyst/output/report.html` — 完整的分析报告
- `agentic_analyst/output/*.png` — 分析过程中生成的图表
- `agentic_analyst/output/analysis_log.json` — Agent 分析过程日志
