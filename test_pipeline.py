"""
快速验证脚本 — 不调用 LLM，直接测试工具链是否正常工作

验证：
1. 数据生成器能否正常生成带 Bug 的数据
2. DuckDB 能否正常加载和查询
3. Python 代码执行器能否正常运行分析和绘图
"""

import os
import sys
import io

# 修复 Windows 终端 UTF-8 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentic_analyst.data_generator import generate_funnel_data
from agentic_analyst.tools.toolkit import init_database, query_database, run_python_code


def test_pipeline():
    print("=" * 60)
    print("🧪 Agentic Data Analyst — 工具链验证")
    print("=" * 60)
    
    # 1. 生成数据
    print("\n📊 [1/4] 生成模拟数据...")
    data_path = generate_funnel_data("data/funnel_data.csv")
    assert os.path.exists(data_path), "数据文件未生成！"
    print("   ✅ 数据生成成功")
    
    # 2. 加载到 DuckDB
    print("\n🗄️  [2/4] 加载数据到 DuckDB...")
    db_info = init_database(data_path)
    print(f"   {db_info}")
    print("   ✅ DuckDB 加载成功")
    
    # 3. SQL 查询测试
    print("\n🔍 [3/4] 测试 SQL 查询...")
    
    # 3a. 按月份和大区汇总转化率
    result = query_database("""
        SELECT 月份, 大区, 
               ROUND(AVG(整体转化率), 4) as 平均转化率,
               SUM(浏览量) as 总浏览量,
               SUM(支付成功) as 总支付数
        FROM funnel_data 
        WHERE 浏览量 > 0 AND 浏览量 < 100000
        GROUP BY 月份, 大区
        ORDER BY 大区, 月份
    """)
    print(f"   月度大区转化率:\n{result}")
    
    # 3b. 锁定华东9月异动细分
    result2 = query_database("""
        SELECT 月份, 终端, 支付方式,
               ROUND(AVG(下单到支付率), 4) as 平均支付率,
               SUM(提交订单) as 总订单数,
               SUM(支付成功) as 总支付数
        FROM funnel_data 
        WHERE 大区 = '华东' AND 浏览量 > 0 AND 浏览量 < 100000
        GROUP BY 月份, 终端, 支付方式
        ORDER BY 终端, 支付方式, 月份
    """)
    print(f"\n   华东区按终端×支付方式的支付率:\n{result2}")
    print("   ✅ SQL 查询成功")
    
    # 4. Python 代码执行测试（含绘图）
    print("\n🐍 [4/4] 测试 Python 代码执行与绘图...")
    
    chart_code = '''
import pandas as pd

# 从 DuckDB 获取数据
df = db_conn.execute("""
    SELECT 月份, 大区, 
           AVG(整体转化率) as avg_rate
    FROM funnel_data 
    WHERE 浏览量 > 0 AND 浏览量 < 100000
    GROUP BY 月份, 大区
    ORDER BY 大区, 月份
""").fetchdf()

print("查询结果：")
print(df.to_string(index=False))

# 绘制折线图
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))

for region in df["大区"].unique():
    region_data = df[df["大区"] == region]
    ax.plot(region_data["月份"], region_data["avg_rate"], marker="o", linewidth=2, label=region)

ax.set_title("各大区月度转化率趋势", fontsize=16, fontweight="bold")
ax.set_xlabel("月份", fontsize=12)
ax.set_ylabel("平均转化率", fontsize=12)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

# 标注华东9月的异常点
hd_sept = df[(df["大区"] == "华东") & (df["月份"] == "2024-09")]
if not hd_sept.empty:
    ax.annotate("⚠️ 异常下降", 
                xy=("2024-09", hd_sept["avg_rate"].values[0]),
                xytext=("2024-09", hd_sept["avg_rate"].values[0] + 0.01),
                fontsize=12, color="red", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="red"))

plt.tight_layout()
plt.savefig(f"{output_dir}/test_chart.png")
print(f"\\n图表已保存到 {output_dir}/test_chart.png")
'''
    
    result3 = run_python_code(chart_code)
    print(f"   {result3}")
    print("   ✅ Python 执行成功")
    
    # 最终汇总
    print("\n" + "=" * 60)
    print("🎉 所有工具链验证通过！")
    print("=" * 60)
    print("\n下一步：设置 OPENAI_API_KEY 后运行 Agent:")
    print("  python agentic_analyst/main.py --goal '分析9月份华东区转化率下降的原因'")
    print("\n如果使用其他 LLM API（如 Deepseek, Claude 等兼容接口）:")
    print("  python agentic_analyst/main.py --base-url https://api.deepseek.com/v1 --api-key YOUR_KEY --model deepseek-chat")


if __name__ == "__main__":
    test_pipeline()
