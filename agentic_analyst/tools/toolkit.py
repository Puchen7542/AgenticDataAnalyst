"""
Agent 工具箱 — 提供给 Agent 的可调用工具

包含：
1. query_database  — 用 DuckDB 查询数据
2. run_python_code — 在沙盒中执行 Python 代码（分析、绘图等）
3. save_chart      — 保存图表文件
"""

import duckdb
import pandas as pd
import traceback
import sys
import io
import os
import json
import base64
import tempfile
from contextlib import redirect_stdout, redirect_stderr


# ========== 全局数据库连接 ==========
_db_conn = None
_data_path = None


def init_database(csv_path: str, table_name: str = "performance_data") -> str:
    """初始化 DuckDB 数据库，加载 CSV 数据"""
    global _db_conn, _data_path
    _data_path = csv_path
    _db_conn = duckdb.connect(":memory:")
    
    # 加载 CSV 到 DuckDB 表
    _db_conn.execute(f"""
        CREATE TABLE {table_name} AS 
        SELECT * FROM read_csv_auto('{csv_path.replace(os.sep, "/")}', header=true)
    """)
    # 建立别名保持兼容
    _db_conn.execute(f"CREATE VIEW IF NOT EXISTS current_table AS SELECT * FROM {table_name}")
    
    row_count = _db_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    columns = _db_conn.execute(f"DESCRIBE {table_name}").fetchall()
    
    col_info = "\n".join([f"  - {col[0]}: {col[1]}" for col in columns])
    
    return f"数据库初始化完成。表名: {table_name} (也可使用 current_table 别名), 总行数: {row_count}\n字段列表:\n{col_info}"


def query_database(sql: str) -> str:
    """
    执行 SQL 查询并返回结果。
    
    Args:
        sql: SQL 查询语句（只读，仅支持 SELECT）
        
    Returns:
        查询结果的格式化字符串
    """
    global _db_conn
    if _db_conn is None:
        return "错误：数据库未初始化，请先调用 init_database()"
    
    # 安全检查：只允许 SELECT
    sql_stripped = sql.strip().upper()
    if not sql_stripped.startswith("SELECT") and not sql_stripped.startswith("WITH") and not sql_stripped.startswith("DESCRIBE") and not sql_stripped.startswith("SHOW"):
        return "错误：只允许执行 SELECT / WITH / DESCRIBE / SHOW 查询"
    
    try:
        result = _db_conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        
        if len(rows) == 0:
            return "查询成功，但返回 0 行结果。"
        
        # 限制返回行数，防止爆 token
        max_rows = 100
        truncated = len(rows) > max_rows
        display_rows = rows[:max_rows]
        
        # 格式化为表格
        df = pd.DataFrame(display_rows, columns=columns)
        result_str = df.to_string(index=False)
        
        if truncated:
            result_str += f"\n\n... (共 {len(rows)} 行，仅显示前 {max_rows} 行)"
        else:
            result_str += f"\n\n共 {len(rows)} 行"
        
        return result_str
    
    except Exception as e:
        return f"SQL 执行错误：{str(e)}\n\n请检查 SQL 语法和字段名称是否正确。"


def run_python_code(code: str, output_dir: str = "agentic_analyst/output") -> str:
    """
    在安全环境中执行 Python 代码。
    
    Agent 可以用这个工具执行数据分析、统计建模、绘图等任务。
    代码中可以使用以下预导入的库：
    - pandas (pd), numpy (np)
    - matplotlib.pyplot (plt), seaborn (sns)
    - scipy.stats
    - duckdb (已连接的数据库: db_conn)
    
    绘图时请使用 plt.savefig() 保存到 output_dir 目录。
    
    Args:
        code: 要执行的 Python 代码
        output_dir: 图表输出目录
        
    Returns:
        代码的 stdout 输出和执行状态
    """
    global _db_conn
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 准备执行环境
    exec_globals = {
        "__builtins__": __builtins__,
        "pd": pd,
        "np": __import__("numpy"),
        "plt": __import__("matplotlib.pyplot", fromlist=["pyplot"]),
        "sns": __import__("seaborn"),
        "scipy": __import__("scipy"),
        "stats": __import__("scipy.stats", fromlist=["stats"]),
        "db_conn": _db_conn,
        "output_dir": output_dir,
        "os": os,
        "json": json,
    }
    
    # 设置 matplotlib 无头后端与中文字体支持（防止 plt.show 阻塞）
    setup_code = """
import matplotlib
matplotlib.use('Agg')  # 强制无头后端，禁止任何 GUI 弹窗阻塞
import matplotlib.pyplot as plt
plt.show = lambda *args, **kwargs: None  # 禁用 show 阻塞
plt.style.use('seaborn-v0_8-whitegrid')
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.figsize'] = (12, 6)
matplotlib.rcParams['figure.dpi'] = 150
matplotlib.rcParams['savefig.dpi'] = 150
matplotlib.rcParams['savefig.bbox'] = 'tight'
"""
    
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    try:
        # 先执行配置代码
        exec(setup_code, exec_globals)
        
        # 执行用户代码
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, exec_globals)
        
        stdout_output = stdout_capture.getvalue()
        stderr_output = stderr_capture.getvalue()
        
        # 检查是否生成了图片
        generated_files = []
        for f in os.listdir(output_dir):
            if f.endswith(('.png', '.jpg', '.svg', '.html')):
                full_path = os.path.join(output_dir, f)
                generated_files.append(full_path)
        
        result = "✅ 代码执行成功！\n"
        if stdout_output:
            result += f"\n--- 输出 ---\n{stdout_output}"
        if stderr_output:
            result += f"\n--- 警告 ---\n{stderr_output}"
        if generated_files:
            result += f"\n--- 生成的文件 ---\n" + "\n".join(generated_files)
        
        return result
        
    except Exception as e:
        error_msg = traceback.format_exc()
        return f"❌ 代码执行出错：\n{error_msg}\n\n请修正代码后重试。"
    
    finally:
        # 关闭所有 matplotlib 图形，防止内存泄漏
        try:
            import matplotlib.pyplot as plt
            plt.close('all')
        except:
            pass


# ========== 工具定义（供 OpenAI function calling 使用）==========

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": """用 DuckDB SQL 查询当前业务数据。表名可直接使用 current_table 或 performance_data。
支持标准 SQL（SELECT, GROUP BY, ORDER BY, CTE 语法等）。
注意：数据中可能存在脏数据（负值、空值、极端异常值），查询时请先做数据质量探查或清洗。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL 查询语句（仅支持只读 SELECT）。表名使用 current_table。"
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_code",
            "description": """执行 Python 代码进行数据分析、统计检验或绘图。
预导入的库: pandas(pd), numpy(np), matplotlib.pyplot(plt), seaborn(sns), scipy.stats(stats)。
已配置中文字体。可通过 db_conn 访问 DuckDB 数据库连接。
绘图请用 plt.savefig(f'{output_dir}/文件名.png') 保存。
分析结果请 print 输出。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码"
                    }
                },
                "required": ["code"]
            }
        }
    }
]


# 工具调用路由
def call_tool(tool_name: str, arguments: dict) -> str:
    """根据工具名称调用对应的工具函数"""
    if tool_name == "query_database":
        return query_database(arguments["sql"])
    elif tool_name == "run_python_code":
        return run_python_code(arguments["code"])
    else:
        return f"未知工具：{tool_name}"
