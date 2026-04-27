"""
stock_core/data_fetcher.py
所有外部資料 API 的統一封裝
"""

import os
from datetime import date, datetime, timedelta
import re
import warnings

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

warnings.filterwarnings("ignore")

# === 環境變數讀取（FinMind Token）===
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")


def _finmind_loader():
    from FinMind.data import DataLoader

    dl = DataLoader()
    if FINMIND_TOKEN:
        try:
            dl.login_by_token(api_token=FINMIND_TOKEN)
        except Exception:
            pass
    return dl


def fetch_00631L(period="3mo"):
    """取得 00631L 歷史報價（Yahoo Finance）"""
    import yfinance as yf

    df = yf.Ticker("00631L.TW").history(period=period)
    return df if not df.empty else None


def fetch_TWII(period="3mo"):
    """取得加權指數（Yahoo Finance）"""
    import yfinance as yf

    df = yf.Ticker("^TWII").history(period=period)
    return df if not df.empty else None


def fetch_TSM(period="3mo"):
    """取得台積電 ADR"""
    import yfinance as yf

    df = yf.Ticker("TSM").history(period=period)
    return df if not df.empty else None


def fetch_TAIFEX_metrics():
    """取得期貨三大法人 + 融資融券數據（FinMind）"""
    dl = _finmind_loader()
    today = date.today().strftime("%Y-%m-%d")

    # 外資大台淨 OI
    df_tx = dl.taiwan_futures_institutional_investors(
        futures_id="TX", start_date="2026-01-01", end_date=today
    )
    latest_tx = df_tx["date"].max()
    df_tx_f = df_tx[
        (df_tx["date"] == latest_tx)
        & df_tx["institutional_investors"].str.contains("資", na=False)
    ]
    tx_net_oi = int(
        df_tx_f.iloc[-1]["long_open_interest_balance_volume"]
        - df_tx_f.iloc[-1]["short_open_interest_balance_volume"]
    )

    # 散戶小台多空比（MTX）
    df_mtx = dl.taiwan_futures_daily(
        futures_id="MTX", start_date="2026-01-01", end_date=today
    )
    df_mtx_p = df_mtx[df_mtx["trading_session"] == "position"]
    latest_mtx = df_mtx_p["date"].max()
    df_mtx_l = df_mtx_p[df_mtx_p["date"] == latest_mtx]
    total_oi = int(df_mtx_l["open_interest"].sum())
    df_mtx_i = dl.taiwan_futures_institutional_investors(
        futures_id="MTX", start_date="2026-01-01", end_date=today
    )
    df_mtx_i = df_mtx_i[df_mtx_i["date"] == latest_mtx]
    inst_l = int(df_mtx_i["long_open_interest_balance_volume"].sum())
    inst_s = int(df_mtx_i["short_open_interest_balance_volume"].sum())
    r_long = total_oi - inst_l
    r_short = total_oi - inst_s
    mtx_ratio = round((r_long - r_short) / total_oi * 100, 2) if total_oi > 0 else 0

    # 融資餘額增減
    df_marg = dl.taiwan_stock_margin_purchase_short_sale_total(
        start_date="2026-01-01", end_date=today
    )
    df_mp = df_marg[df_marg["name"] == "MarginPurchase"].sort_values("date")
    lat = df_mp.iloc[-1]
    prv = df_mp.iloc[-2]
    margin_chg = (float(lat["TodayBalance"]) - float(prv["YesBalance"])) / 1e6

    return {
        "tx_net_oi": tx_net_oi,
        "tx_date": str(latest_tx),
        "mtx_ratio": mtx_ratio,
        "margin_chg": round(margin_chg, 2),
        "total_oi": total_oi,
        "inst_l": inst_l,
        "inst_s": inst_s,
    }


def fetch_market_breadth():
    """取得台股 ADL 騰落指標（TWSE）"""
    from urllib.request import Request, urlopen
    import ssl
    import json

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for days_back in range(7):
        d = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d}&response=json"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urlopen(req, timeout=10, context=ctx).read()
        data = json.loads(raw.decode("utf-8"))
        for t in data.get("tables", []):
            if "漲跌證券數合計" in t.get("title", ""):
                up = down = same = 0
                for row in t.get("data", []):
                    label = row[0] if row else ""
                    vstr = row[2] if len(row) > 2 else (row[1] if len(row) > 1 else "")
                    try:
                        val = int(
                            re.sub(r"\([^)]*\)", "", vstr).replace(",", "").strip()
                        )
                    except Exception:
                        val = 0
                    if "上漲" in label:
                        up = val
                    elif "下跌" in label:
                        down = val
                    elif "持平" in label:
                        same = val
                return {"up": up, "down": down, "same": same, "date": d}
    return None


def fetch_premium():
    """取得 00631L 折溢價"""
    import yfinance as yf

    t = yf.Ticker("00631L.TW")
    df = t.history(period="5d")
    if df is None or df.empty:
        return None
    price = float(df["Close"].iloc[-1])
    try:
        nav = t.info.get("navPrice", None)
        nav = float(nav) if (nav and nav > 0) else None
    except Exception:
        nav = None
    if nav is None or nav <= 0:
        return {"price": price, "nav": None, "premium": None, "note": "navPrice取得失敗"}
    premium = (price - nav) / nav * 100
    return {"price": price, "nav": nav, "premium": premium, "note": "navPrice落後1天，僅供參考"}


def fetch_foreign_spot():
    """取得外資現貨買賣超（FinMind）"""
    dl = _finmind_loader()
    today = date.today().strftime("%Y-%m-%d")
    df = dl.taiwan_stock_institutional_investors_total(
        start_date=today, end_date=today
    )
    fi = df[df["name"] == "Foreign_Investor"]
    if fi.empty:
        return None
    row = fi.iloc[-1]
    net = (float(row["buy"]) - float(row["sell"])) / 1e8
    return {
        "net": round(net, 1),
        "buy": round(float(row["buy"]) / 1e8, 1),
        "sell": round(float(row["sell"]) / 1e8, 1),
    }


def fetch_USDTWD():
    """取得美元/台幣匯率"""
    try:
        dl = _finmind_loader()
        today = date.today().strftime("%Y-%m-%d")
        df = dl.taiwan_ExchangeRate(start_date=today, end_date=today)
        if df is None or df.empty:
            return None
        row = df.iloc[-1]
        return {"rate": float(row.get("exchange_rate", 0)), "date": str(row.get("date", ""))}
    except Exception:
        return None
