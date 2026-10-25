"""Quick font rendering test"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentic_analyst.tools.toolkit import init_database, run_python_code

init_database('data/funnel_data.csv')

code = '''
df = db_conn.execute("""
    SELECT "月份", "大区", AVG("整体转化率") as avg_rate
    FROM funnel_data WHERE "浏览量" > 0 AND "浏览量" < 100000
    GROUP BY "月份", "大区" ORDER BY "大区", "月份"
""").fetchdf()

fig, ax = plt.subplots(figsize=(10, 6))
for region in df["大区"].unique():
    d = df[df["大区"] == region]
    ax.plot(d["月份"], d["avg_rate"], marker="o", linewidth=2, label=region)
ax.set_title("各大区月度转化率趋势", fontsize=16, fontweight="bold")
ax.set_xlabel("月份")
ax.set_ylabel("平均转化率")
ax.legend()
plt.savefig(f"{output_dir}/font_test.png")
print("Chart saved OK")
'''

result = run_python_code(code)
print(result)
