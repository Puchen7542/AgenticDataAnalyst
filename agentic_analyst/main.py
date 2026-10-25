"""
启动入口 — Agentic Data Analyst

用法：
  python -m agentic_analyst.main --goal "分析为什么9月份华东区的转化率下降了"

或直接运行：
  python main.py
"""

import argparse
import os
import sys
import io

# 修复 Windows 终端 UTF-8 编码
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentic_analyst.data_generator import generate_funnel_data
from agentic_analyst.agent import AgenticAnalyst


def main():
    parser = argparse.ArgumentParser(description="Agentic Data Analyst - 智能代理型分析师")
    parser.add_argument(
        "--goal", 
        type=str,
        default="请深入分析9月份华东区整体转化率下降的根本原因，找出是哪个具体维度（渠道、终端、支付方式等）的哪个细分导致了下降，量化其影响程度，并给出行动建议。",
        help="分析目标（自然语言描述）"
    )
    parser.add_argument("--data", type=str, default="data/funnel_data.csv", help="数据文件路径")
    parser.add_argument("--generate-data", action="store_true", default=True, help="是否先生成模拟数据")
    parser.add_argument("--api-key", type=str, default=None, help="LLM API Key")
    parser.add_argument("--base-url", type=str, default=None, help="LLM API Base URL")
    parser.add_argument("--model", type=str, default="gpt-4o", help="LLM 模型名称")
    parser.add_argument("--max-iterations", type=int, default=25, help="最大迭代次数")
    
    args = parser.parse_args()
    
    # 生成数据
    if args.generate_data and not os.path.exists(args.data):
        print("📊 正在生成模拟业务数据...")
        generate_funnel_data(args.data)
        print()
    
    # 检查 API Key
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  请设置 OPENAI_API_KEY 环境变量或通过 --api-key 参数传入")
        print("   示例: set OPENAI_API_KEY=sk-xxx")
        print("   或者使用其他兼容 API: --base-url https://your-api.com/v1 --api-key your-key --model your-model")
        sys.exit(1)
    
    # 创建 Agent 并执行分析
    agent = AgenticAnalyst(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        max_iterations=args.max_iterations,
        verbose=True,
    )
    
    report_path = agent.analyze(goal=args.goal, data_path=args.data)
    
    # 打开报告
    if report_path and report_path.endswith('.html') and os.path.exists(report_path):
        abs_path = os.path.abspath(report_path)
        print(f"\n🌐 正在打开报告: {abs_path}")
        os.system(f'start "" "{abs_path}"')


if __name__ == "__main__":
    main()
