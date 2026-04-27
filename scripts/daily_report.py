#!/usr/bin/env python3
"""
每日 00631L 報告生成腳本
由 cron job 呼叫，發送到 Telegram
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_core import (
    analyze_panic,
    analyze_right,
    fetch_00631L,
    fetch_TAIFEX_metrics,
    fetch_TWII,
    fetch_foreign_spot,
    fetch_market_breadth,
    fetch_premium,
    generate_report,
    send_telegram,
)


def _safe_fetch(name, fetcher, default=None):
    try:
        return fetcher()
    except Exception as exc:
        print(f"{name} failed: {exc}")
        return default


def main():
    print("00631L 每日報告生成中...")

    # 取得資料
    df_00631l = _safe_fetch("fetch_00631L", lambda: fetch_00631L("3mo"))
    df_twii = _safe_fetch("fetch_TWII", lambda: fetch_TWII("3mo"))
    taifex = _safe_fetch("fetch_TAIFEX_metrics", fetch_TAIFEX_metrics)
    market = _safe_fetch("fetch_market_breadth", fetch_market_breadth)
    premium = _safe_fetch("fetch_premium", fetch_premium)
    foreign = _safe_fetch("fetch_foreign_spot", fetch_foreign_spot)

    # 分析
    analysis = analyze_right(df_00631l, df_twii)
    panic = analyze_panic(df_00631l)

    # 生成報告
    report = generate_report(
        analysis=analysis,
        panic=panic,
        taifex=taifex,
        market=market,
        premium=premium,
        foreign=foreign,
    )

    # 發送
    ok = send_telegram(report)
    print("報告已發送" if ok else "報告生成完成，但 Telegram 發送失敗")


if __name__ == "__main__":
    main()
