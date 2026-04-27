"""
stock_core - 台股分析核心模組
"""

from .data_fetcher import (
    fetch_00631L,
    fetch_TWII,
    fetch_TSM,
    fetch_TAIFEX_metrics,
    fetch_market_breadth,
    fetch_premium,
    fetch_foreign_spot,
    fetch_USDTWD,
)

from .indicators import (
    MA,
    EMA,
    MACD,
    RSI,
    AO,
    ATR,
    BB,
    ADX_DMI,
    analyze_right,
    analyze_panic,
    safe_float,
)

from .reporter import (
    send_telegram,
    generate_report,
)

__all__ = [
    # data_fetcher
    "fetch_00631L",
    "fetch_TWII",
    "fetch_TSM",
    "fetch_TAIFEX_metrics",
    "fetch_market_breadth",
    "fetch_premium",
    "fetch_foreign_spot",
    "fetch_USDTWD",
    # indicators
    "MA",
    "EMA",
    "MACD",
    "RSI",
    "AO",
    "ATR",
    "BB",
    "ADX_DMI",
    "analyze_right",
    "analyze_panic",
    "safe_float",
    # reporter
    "send_telegram",
    "generate_report",
]
