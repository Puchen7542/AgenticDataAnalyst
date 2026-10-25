"""
数据生成器 - 生成带有暗藏 Bug 的电商转化漏斗数据

数据设计：
- 基础数据：2024年7月-9月，5个大区（华东/华南/华北/华中/西南），
  4个渠道（抖音/微信/百度/自然流量），3个终端（iOS/Android/PC），
  3个支付方式（支付宝/微信支付/银行卡）。
- 暗藏案发现场：
  9月份，华东区 iOS 端 支付宝支付渠道出了 Bug，导致该细分人群
  支付转化率从正常的 ~65% 暴跌到 ~5%，拉低了整个华东区转化率约 3-4 个百分点。
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


def generate_funnel_data(output_path: str = "data/funnel_data.csv", seed: int = 42) -> str:
    """生成电商转化漏斗数据集"""
    np.random.seed(seed)

    # 维度定义
    regions = ["华东", "华南", "华北", "华中", "西南"]
    channels = ["抖音", "微信", "百度", "自然流量"]
    platforms = ["iOS", "Android", "PC"]
    payment_methods = ["支付宝", "微信支付", "银行卡"]

    # 基础转化率参数（正常情况下）
    base_rates = {
        "browse_to_cart": 0.38,      # 浏览 -> 加入购物车
        "cart_to_order": 0.55,       # 加入购物车 -> 提交订单
        "order_to_pay": 0.65,        # 提交订单 -> 支付成功
    }

    # 各维度对转化率的微调系数（围绕 1.0 轻微波动）
    region_factors = {"华东": 1.08, "华南": 1.04, "华北": 1.00, "华中": 0.96, "西南": 0.92}
    channel_factors = {"抖音": 0.93, "微信": 1.06, "百度": 0.98, "自然流量": 1.10}
    platform_factors = {"iOS": 1.06, "Android": 1.02, "PC": 0.95}
    payment_factors = {"支付宝": 1.04, "微信支付": 1.02, "银行卡": 0.94}

    # 流量分布权重
    region_traffic = {"华东": 0.30, "华南": 0.25, "华北": 0.20, "华中": 0.15, "西南": 0.10}
    channel_traffic = {"抖音": 0.35, "微信": 0.25, "百度": 0.20, "自然流量": 0.20}
    platform_traffic = {"iOS": 0.40, "Android": 0.45, "PC": 0.15}
    payment_traffic = {"支付宝": 0.40, "微信支付": 0.45, "银行卡": 0.15}

    records = []

    # 日期范围：2024-07-01 ~ 2024-09-30
    start_date = datetime(2024, 7, 1)
    end_date = datetime(2024, 9, 30)

    current_date = start_date
    while current_date <= end_date:
        month = current_date.month
        weekday = current_date.weekday()

        # 周末流量略高
        weekend_boost = 1.12 if weekday >= 5 else 1.0

        for region in regions:
            for channel in channels:
                for platform in platforms:
                    # 每天每个（大区×渠道×终端）的基础浏览量
                    # 提高基础量到 3000，确保小细分也有足够样本
                    base_views = int(
                        3000
                        * region_traffic[region]
                        * channel_traffic[channel]
                        * platform_traffic[platform]
                        * weekend_boost
                        * np.random.uniform(0.85, 1.15)
                    )

                    if base_views < 20:
                        base_views = 20

                    # 计算各环节转化率
                    r_factor = region_factors[region]
                    c_factor = channel_factors[channel]
                    p_factor = platform_factors[platform]

                    browse_to_cart = np.clip(
                        base_rates["browse_to_cart"] * r_factor * c_factor * p_factor
                        * np.random.uniform(0.93, 1.07),
                        0.15, 0.65
                    )
                    cart_to_order = np.clip(
                        base_rates["cart_to_order"] * r_factor * p_factor
                        * np.random.uniform(0.93, 1.07),
                        0.25, 0.80
                    )
                    order_to_pay_base = np.clip(
                        base_rates["order_to_pay"] * r_factor * p_factor
                        * np.random.uniform(0.93, 1.07),
                        0.30, 0.85
                    )

                    for pay_method in payment_methods:
                        pm_factor = payment_factors[pay_method]

                        final_order_to_pay = np.clip(
                            order_to_pay_base * pm_factor,
                            0.25, 0.90
                        )

                        # ===========================================================
                        # BUG 注入：9月 + 华东 + iOS + 支付宝
                        # 支付成功率从正常的 ~65% 暴跌到 ~5%
                        # ===========================================================
                        if (month == 9
                            and region == "华东"
                            and platform == "iOS"
                            and pay_method == "支付宝"):
                            final_order_to_pay = np.random.uniform(0.03, 0.07)

                        # 按支付方式分配流量
                        pm_traffic_share = payment_traffic[pay_method]
                        views = max(int(base_views * pm_traffic_share), 5)

                        # 逐层计算漏斗
                        cart_adds = max(int(views * browse_to_cart), 1)
                        orders = max(int(cart_adds * cart_to_order), 1)
                        payments = max(int(orders * final_order_to_pay), 0)

                        # 客单价（元）
                        avg_price = np.random.uniform(80, 350) * pm_factor * r_factor
                        gmv = round(payments * avg_price, 2)

                        records.append({
                            "日期": current_date.strftime("%Y-%m-%d"),
                            "月份": f"{current_date.year}-{current_date.month:02d}",
                            "星期": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][weekday],
                            "大区": region,
                            "渠道": channel,
                            "终端": platform,
                            "支付方式": pay_method,
                            "浏览量": views,
                            "加入购物车": cart_adds,
                            "提交订单": orders,
                            "支付成功": payments,
                            "GMV": gmv,
                            "浏览到加购率": round(cart_adds / views, 4) if views > 0 else 0,
                            "加购到下单率": round(orders / cart_adds, 4) if cart_adds > 0 else 0,
                            "下单到支付率": round(payments / orders, 4) if orders > 0 else 0,
                            "整体转化率": round(payments / views, 4) if views > 0 else 0,
                        })

        current_date += timedelta(days=1)

    df = pd.DataFrame(records)

    # 注入少量脏数据（Agent 需要识别和处理）
    dirty_indices = np.random.choice(len(df), size=int(len(df) * 0.003), replace=False)
    for idx in dirty_indices:
        corruption_type = np.random.choice(["negative", "null_gmv", "extreme"])
        if corruption_type == "negative":
            df.loc[idx, "浏览量"] = -1
        elif corruption_type == "null_gmv":
            df.loc[idx, "GMV"] = None
        elif corruption_type == "extreme":
            df.loc[idx, "浏览量"] = 999999

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"[OK] Data generated: {len(df)} rows -> {output_path}")
    print(f"     Date range: {df['日期'].min()} ~ {df['日期'].max()}")
    print(f"     Dimensions: {len(regions)} regions x {len(channels)} channels x {len(platforms)} platforms x {len(payment_methods)} payments")
    print(f"     Dirty rows injected: {len(dirty_indices)}")

    # 验证 Bug 效果
    sept_hd = df[(df["月份"] == "2024-09") & (df["大区"] == "华东")]
    sept_hd_ios_ali = sept_hd[(sept_hd["终端"] == "iOS") & (sept_hd["支付方式"] == "支付宝")]
    aug_hd = df[(df["月份"] == "2024-08") & (df["大区"] == "华东")]
    aug_hd_ios_ali = aug_hd[(aug_hd["终端"] == "iOS") & (aug_hd["支付方式"] == "支付宝")]

    print(f"\n     [Bug Check]")
    print(f"     Aug East-iOS-Alipay pay_rate: {aug_hd_ios_ali['下单到支付率'].mean():.4f}")
    print(f"     Sep East-iOS-Alipay pay_rate: {sept_hd_ios_ali['下单到支付率'].mean():.4f}")
    print(f"     Aug East overall conv_rate:   {aug_hd['整体转化率'].mean():.4f}")
    print(f"     Sep East overall conv_rate:   {sept_hd['整体转化率'].mean():.4f}")

    return output_path


if __name__ == "__main__":
    generate_funnel_data()
