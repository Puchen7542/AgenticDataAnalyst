"""
电商广告投放数据集生成器 (Ads ROI Attribution)

业务背景：
- 2024年8月-10月，覆盖4大广告渠道（抖音巨量引擎、腾讯广告AMS、小红书聚光、快手磁力引擎）
- 出价策略：oCPM（转化出价）、CPC（点击出价）、NOBID（最大转化）
- 人群定向：高潜拉新包、精准复购包、破圈泛人群
- 核心指标：曝光量、点击量、消耗金额(Cost)、加购数、支付订单数、支付GMV、ROI(GMV/Cost)、CPC、CTR

🐛 预设暗藏事故（Blind Test）：
10月中旬起，小红书渠道的【破圈泛人群】采用了【NOBID(最大转化/通投爆量)】策略，
导致系统为了跑出消耗疯狂采买劣质流量：
消耗暴涨 3 倍，但转化极低（虚假点击/误触），造成该细分 ROI 从 3.8 暴跌至 0.45，
最终严重拖垮了 10 月份全盘的综合 ROI！
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def generate_ads_data(output_path: str = "data/ads_performance.csv", seed: int = 1024) -> str:
    np.random.seed(seed)
    
    channels = ["抖音巨量", "腾讯广告", "小红书", "快手磁力"]
    bidding_strategies = ["oCPM", "CPC", "NOBID"]
    target_audiences = ["高潜拉新", "精准复购", "破圈泛人群"]
    categories = ["美妆护肤", "服饰鞋包", "3C数码"]
    
    # 基础基准值 (CTR, CVR, 客单价)
    base_channel_profile = {
        "抖音巨量": {"ctr": 0.025, "cvr": 0.045, "cpc": 1.8, "base_aov": 220},
        "腾讯广告": {"ctr": 0.018, "cvr": 0.040, "cpc": 1.5, "base_aov": 260},
        "小红书":   {"ctr": 0.035, "cvr": 0.055, "cpc": 2.2, "base_aov": 310},
        "快手磁力": {"ctr": 0.028, "cvr": 0.038, "cpc": 1.2, "base_aov": 160},
    }
    
    audience_factors = {
        "高潜拉新": {"ctr_f": 1.0, "cvr_f": 1.0, "cpc_f": 1.1},
        "精准复购": {"ctr_f": 1.4, "cvr_f": 1.8, "cpc_f": 1.3},
        "破圈泛人群": {"ctr_f": 0.8, "cvr_f": 0.6, "cpc_f": 0.8},
    }
    
    bid_factors = {
        "oCPM": {"cvr_f": 1.2, "spend_boost": 1.0},
        "CPC":  {"cvr_f": 0.9, "spend_boost": 0.8},
        "NOBID": {"cvr_f": 1.0, "spend_boost": 1.3},
    }
    
    start_date = datetime(2024, 8, 1)
    end_date = datetime(2024, 10, 31)
    
    records = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        month_str = f"{current_date.year}-{current_date.month:02d}"
        is_october_bug_period = (current_date.month == 10 and current_date.day >= 8)
        
        for ch in channels:
            cp = base_channel_profile[ch]
            for bid in bidding_strategies:
                bf = bid_factors[bid]
                for aud in target_audiences:
                    af = audience_factors[aud]
                    for cat in categories:
                        # 基础预算与消耗计算
                        base_cost = np.random.uniform(800, 2500) * bf["spend_boost"]
                        cpc = cp["cpc"] * af["cpc_f"] * np.random.uniform(0.9, 1.1)
                        ctr = cp["ctr"] * af["ctr_f"] * np.random.uniform(0.9, 1.1)
                        cvr = cp["cvr"] * af["cvr_f"] * bf["cvr_f"] * np.random.uniform(0.9, 1.1)
                        aov = cp["base_aov"] * np.random.uniform(0.95, 1.05)
                        
                        # ------------------------------------------------------------------
                        # 🐛 注入暗藏灾难事故：
                        # 10月8日开始，小红书 + 破圈泛人群 + NOBID 策略暴走：
                        # 消耗飙升 3.5 倍，但转化率暴跌 85%（全是垃圾流量/误触点击）
                        # ------------------------------------------------------------------
                        if is_october_bug_period and ch == "小红书" and aud == "破圈泛人群" and bid == "NOBID":
                            base_cost = base_cost * 3.5  # 预算通投暴烧
                            cvr = cvr * 0.12            # 转化雪崩
                            cpc = cpc * 1.25            # 流量竞价被抬高
                        
                        cost = round(base_cost, 2)
                        clicks = max(int(cost / max(cpc, 0.1)), 10)
                        impressions = int(clicks / max(ctr, 0.001))
                        orders = max(int(clicks * cvr), 0)
                        gmv = round(orders * aov, 2)
                        roi = round(gmv / cost, 4) if cost > 0 else 0.0
                        
                        records.append({
                            "日期": date_str,
                            "月份": month_str,
                            "渠道": ch,
                            "出价策略": bid,
                            "人群定向": aud,
                            "商品品类": cat,
                            "曝光量": impressions,
                            "点击量": clicks,
                            "消耗金额": cost,
                            "成交订单数": orders,
                            "成交GMV": gmv,
                            "点击率CTR": round(clicks / impressions, 4) if impressions > 0 else 0,
                            "转化率CVR": round(orders / clicks, 4) if clicks > 0 else 0,
                            "平均CPC": round(cost / clicks, 2) if clicks > 0 else 0,
                            "投资回报率ROI": roi
                        })
                        
        current_date += timedelta(days=1)
        
    df = pd.DataFrame(records)
    
    # 注入少量常规业务噪点与脏数据（50条左右）
    dirty_indices = np.random.choice(len(df), size=40, replace=False)
    for idx in dirty_indices:
        p = np.random.random()
        if p < 0.4:
            df.loc[idx, "消耗金额"] = -100.0  # 异常负数消耗
        elif p < 0.7:
            df.loc[idx, "成交GMV"] = None     # 缺失值
        else:
            df.loc[idx, "点击量"] = 9999999   # 爬虫异常暴增
            
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    
    print(f"✅ 广告数据集生成完毕: 共 {len(df)} 行 -> {output_path}")
    print(f"   时间跨度: {df['日期'].min()} ~ {df['日期'].max()}")
    
    # 打印给系统自检的验证信息（不告诉 Agent）
    m_agg = df[df["消耗金额"] > 0].groupby("月份").agg({"消耗金额": "sum", "成交GMV": "sum"})
    m_agg["全盘ROI"] = (m_agg["成交GMV"] / m_agg["消耗金额"]).round(3)
    print("\n[自检] 各月全盘广告大盘 ROI 走势:")
    print(m_agg)
    return output_path

if __name__ == "__main__":
    generate_ads_data()
