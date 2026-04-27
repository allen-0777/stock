"""
stock_core/reporter.py
每日報告生成與發送
"""

import os
from datetime import datetime

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6702902886")


def send_telegram(msg, token=None, chat_id=None):
    """發送 Telegram 訊息"""
    t = token or TELEGRAM_BOT_TOKEN
    c = chat_id or TELEGRAM_CHAT_ID
    if not t:
        return False
    url = f"https://api.telegram.org/bot{t}/sendMessage"
    try:
        r = requests.post(
            url,
            json={
                "chat_id": c,
                "text": msg,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return r.json().get("ok", False)
    except Exception:
        return False


def _fmt_num(value, digits=2, default="N/A"):
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return default


def _fmt_pct(value, digits=2, default="N/A"):
    try:
        return f"{float(value):+,.{digits}f}%"
    except (TypeError, ValueError):
        return default


def _line_items(items, empty="□ 無"):
    if not items:
        return empty
    return "\n".join(items)


def generate_report(
    analysis,
    taifex=None,
    market=None,
    premium=None,
    foreign=None,
    panic=None,
):
    """生成完整的 00631L 每日報告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not analysis:
        return (
            "📊 *00631L 每日交易報告*\n"
            f"更新時間：{now}\n\n"
            "⚠️ 無法產生技術分析：00631L 價格資料不足或取得失敗。"
        )

    price = _fmt_num(analysis.get("price"))
    chg = _fmt_pct(analysis.get("chg"))
    signal = analysis.get("signal", "N/A")
    trend = analysis.get("trend", "N/A")
    score = analysis.get("score", 0)

    lines = [
        "📊 *00631L 每日交易報告*",
        f"更新時間：{now}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "*一、右側順勢交易*",
        f"現價：`{price}`（{chg}）",
        f"趨勢：`{trend}`｜條件分數：`{score}/4`",
        f"訊號：*{signal}*",
        "",
        "*技術指標*",
        f"20MA：`{_fmt_num(analysis.get('ma20'))}`｜50MA：`{_fmt_num(analysis.get('ma50'))}`｜5MA：`{_fmt_num(analysis.get('ma5'))}`",
        f"MACD：`{analysis.get('macd_signal', 'N/A')}`｜Hist：`{_fmt_num(analysis.get('hist'), 3)}`",
        f"RSI14：`{_fmt_num(analysis.get('r14'), 1)}`｜RSI5：`{_fmt_num(analysis.get('r5'), 1)}`｜AO：`{_fmt_num(analysis.get('ao'), 2)}`",
        f"ADX：`{_fmt_num(analysis.get('adx'), 1)}`｜+DI：`{_fmt_num(analysis.get('pdi'), 1)}`｜-DI：`{_fmt_num(analysis.get('mdi'), 1)}`",
        f"量能：`{_fmt_num(analysis.get('vol_ratio'), 1)}x`｜ATR：`{_fmt_num(analysis.get('atr'), 2)}`",
        "",
        "*進場條件已滿足*",
        _line_items(analysis.get("entry_ok")),
        "",
        "*尚未滿足*",
        _line_items(analysis.get("entry_fail")),
        "",
        "*離場/風控檢查*",
        _line_items(analysis.get("exit_items")),
        f"移動停利參考：`{_fmt_num(analysis.get('trailing_stop'))}`",
        f"停損參考：`{_fmt_num(analysis.get('stop_loss'))}`",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "*二、恐慌抄底雷達*",
    ]

    if panic:
        panic_signal = "✅ 觸發" if panic.get("is_panic") else "未觸發"
        lines.append(f"狀態：*{panic_signal}*｜條件：`{panic.get('cnt', 0)}/4`")
        for name, ok, detail in panic.get("det", []):
            mark = "□" if ok else "◇"
            lines.append(f"{mark} {name}：{detail}")
    else:
        lines.append("N/A")

    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "*三、籌碼與市場寬度*"])

    if taifex:
        lines.extend(
            [
                f"外資大台淨 OI：`{_fmt_num(taifex.get('tx_net_oi'), 0)}` 口（{taifex.get('tx_date', 'N/A')}）",
                f"散戶小台多空比：`{_fmt_pct(taifex.get('mtx_ratio'))}`",
                f"融資餘額增減：`{_fmt_num(taifex.get('margin_chg'))}` 億",
            ]
        )
    else:
        lines.append("期貨/融資資料：N/A")

    if foreign:
        buy = _fmt_num(foreign.get("buy"), 1)
        sell = _fmt_num(foreign.get("sell"), 1)
        net = _fmt_num(foreign.get("net"), 1)
        lines.append(
            f"外資現貨：買 `{buy}` 億｜賣 `{sell}` 億｜淨額 `{net}` 億"
        )
    else:
        lines.append("外資現貨：N/A")

    if market:
        up = market.get("up", 0)
        down = market.get("down", 0)
        same = market.get("same", 0)
        breadth = up - down
        lines.append(
            f"騰落家數：上漲 `{up}`｜下跌 `{down}`｜持平 `{same}`｜ADL `{breadth:+,}`（{market.get('date', 'N/A')}）"
        )
    else:
        lines.append("市場寬度：N/A")

    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "*四、折溢價*"])
    if premium:
        premium_value = premium.get("premium")
        premium_text = _fmt_pct(premium_value) if premium_value is not None else "N/A"
        lines.extend(
            [
                f"市價：`{_fmt_num(premium.get('price'))}`｜NAV：`{_fmt_num(premium.get('nav'))}`",
                f"折溢價：`{premium_text}`",
                f"備註：{premium.get('note', 'N/A')}",
            ]
        )
    else:
        lines.append("折溢價資料：N/A")

    lines.extend(
        [
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "*五、結論*",
            _summary_text(analysis, panic, taifex, market, premium, foreign),
        ]
    )
    return "\n".join(lines)


def _summary_text(analysis, panic=None, taifex=None, market=None, premium=None, foreign=None):
    score = analysis.get("score", 0)
    trend = analysis.get("trend", "N/A")
    parts = []

    if score >= 3:
        parts.append("順勢條件偏多，可依停損與部位控管執行。")
    elif trend == "空頭":
        parts.append("趨勢偏弱，右側交易仍以等待轉強為主。")
    else:
        parts.append("條件尚未完整，維持觀望並等待量價或趨勢確認。")

    if panic and panic.get("is_panic"):
        parts.append("恐慌雷達達標，若採左側策略需分批且嚴控風險。")

    if taifex and taifex.get("tx_net_oi", 0) < 0:
        parts.append("外資期貨淨 OI 偏空，追價需保守。")

    if market and market.get("down", 0) > market.get("up", 0):
        parts.append("市場寬度偏弱，個股/ETF 反彈延續性需觀察。")

    if foreign and foreign.get("net", 0) < 0:
        parts.append("外資現貨為賣超，籌碼面尚未明顯轉佳。")

    if premium and premium.get("premium") is not None and premium.get("premium") > 1:
        parts.append("00631L 溢價偏高，進場價格需留意追高風險。")

    return "\n".join(parts)
