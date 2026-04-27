"""
stock_core/indicators.py
技術指標計算模組（純函數，無 API 依賴）
"""

import pandas as pd
import numpy as np


def safe_float(val):
    """安全轉換為浮點數"""
    if val is None:
        return None
    try:
        f = float(val)
        return None if np.isnan(f) or np.isinf(f) else f
    except Exception:
        return None


def MA(s, period):
    return s.rolling(period).mean()


def EMA(s, period):
    return s.ewm(span=period, adjust=False).mean()


def MACD(s, fast=12, slow=26, signal=9):
    """回傳 (macd_line, signal_line, histogram)"""
    ema_fast = EMA(s, fast)
    ema_slow = EMA(s, slow)
    macd_line = ema_fast - ema_slow
    signal_line = EMA(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def RSI(s, period=14):
    delta = s.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def AO(h, l, fast=5, slow=34):
    """Awesome Oscillator"""
    med = (h + l) / 2
    return MA(med, fast) - MA(med, slow)


def ATR(h, l, c, period=14):
    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def BB(s, period=20, std_dev=2):
    m = MA(s, period)
    s_std = s.rolling(period).std()
    upper = m + std_dev * s_std
    lower = m - std_dev * s_std
    return upper, m, lower


def ADX_DMI(h, l, c, period=14):
    """計算 ADX, +DI, -DI"""
    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    up_move = h - h.shift(1)
    down_move = l.shift(1) - l
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr_s = tr.rolling(period).mean()
    plus_di = (plus_dm.rolling(period).mean() / atr_s) * 100
    minus_di = (minus_dm.rolling(period).mean() / atr_s) * 100
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx_val = dx.rolling(period).mean()
    return adx_val, plus_di, minus_di


def analyze_right(df, df_twii=None):
    """
    右側順勢交易分析
    回傳完整分析結果 dict
    """
    if df is None or len(df) < 50:
        return None
    c, h, l = df["Close"], df["High"], df["Low"]
    price = c.iloc[-1]
    prev = c.iloc[-2]
    ma20 = MA(c, 20).iloc[-1]
    ma50 = MA(c, 50).iloc[-1]
    ma5 = MA(c, 5).iloc[-1]
    mc, sc, hc = MACD(c)
    mc_p = mc.iloc[-2]
    sc_p = sc.iloc[-2]
    r14 = RSI(c, 14).iloc[-1]
    r5 = RSI(c, 5).iloc[-1]
    aoc = AO(h, l).iloc[-1]
    atr_val = ATR(h, l, c, 14).iloc[-1]
    adx_val, plus_di, minus_di = ADX_DMI(h, l, c, 14)
    adx = adx_val.iloc[-1] if not adx_val.isna().iloc[-1] else 0
    pdi = plus_di.iloc[-1] if not plus_di.isna().iloc[-1] else 0
    mdi = minus_di.iloc[-1] if not minus_di.isna().iloc[-1] else 0
    vol = df["Volume"]
    vol_ma5 = vol.rolling(5).mean().iloc[-1]
    vol_ratio = vol.iloc[-1] / vol_ma5 if vol_ma5 and vol_ma5 > 0 else 0

    # 進場條件
    e1 = price > ma20
    e2 = mc_p < sc_p and mc.iloc[-1] > sc.iloc[-1]
    e3 = vol_ratio >= 1.3
    e4 = adx >= 25 and pdi > mdi
    entry_ok = []
    entry_fail = []
    if e1:
        entry_ok.append("□ 價格突破站上 20MA")
    else:
        entry_fail.append("□ 價格在 20MA 之下")
    if e2:
        entry_ok.append("□ MACD 黃金交叉")
    else:
        entry_fail.append("□ MACD 未黃金交叉")
    if e3:
        entry_ok.append(f"□ 成交量 {vol_ratio:.1f}x")
    else:
        entry_fail.append(f"□ 成交量不足（{vol_ratio:.1f}x）")
    if e4:
        entry_ok.append(f"□ ADX {adx:.1f} > 25 且 +DI>{mdi:.1f}")
    else:
        entry_fail.append(f"□ ADX {adx:.1f} < 25 或 +DI < -DI")

    # 離場條件
    exit_items = []
    if price < ma20 and mc.iloc[-1] < sc.iloc[-1]:
        exit_items.append("□ 跌破 20MA + MACD 死亡交叉")
    exit_items.append("□ 持有 > 7 天需檢視")
    if adx < 20 or pdi < mdi:
        exit_items.append(f"□ ADX轉弱 {adx:.1f} 或 +DI < -DI")

    trend = "多頭" if ma20 > ma50 and price > ma20 else "空頭" if ma20 < ma50 and price < ma20 else "盤整"
    score = sum([e1, e2, e3, e4])
    trailing_stop = min(ma5, df["Low"].iloc[-1]) if ma5 else df["Low"].iloc[-1]
    stop_loss = trailing_stop if trailing_stop and trailing_stop < price else price * 0.95

    macd_signal = (
        "▲ 黃金交叉"
        if (mc_p < sc_p and mc.iloc[-1] > sc.iloc[-1])
        else ("▼ 死亡交叉" if (mc.iloc[-1] < sc.iloc[-1] and hc.iloc[-1] < 0) else "─ 盤整")
    )

    return {
        "price": price,
        "prev": prev,
        "chg": (price - prev) / prev * 100 if prev else 0,
        "ma20": ma20,
        "ma50": ma50,
        "ma5": ma5,
        "macd_signal": macd_signal,
        "hist": hc.iloc[-1],
        "r14": r14,
        "r5": r5,
        "ao": aoc,
        "adx": adx,
        "pdi": pdi,
        "mdi": mdi,
        "vol_ratio": vol_ratio,
        "atr": atr_val,
        "trend": trend,
        "score": score,
        "signal": "🟢 進場訊號出現" if score >= 3 else "🟡 觀望（條件未完全滿足）",
        "entry_ok": entry_ok,
        "entry_fail": entry_fail,
        "exit_items": [x for x in exit_items if x],
        "trailing_stop": trailing_stop,
        "stop_loss": stop_loss,
        "prev_low": df["Low"].iloc[-1],
    }


def analyze_panic(df):
    """
    恐慌抄底雷達（需達成 2+ 項）
    """
    if df is None or len(df) < 25:
        return None
    c, h, l = df["Close"], df["High"], df["Low"]
    price = c.iloc[-1]
    ma20_v = MA(c, 20).iloc[-1]
    r14 = RSI(c, 14).iloc[-1]
    upper, mid, lower = BB(c, 20, 2)
    bl = lower.iloc[-1]
    bias = (price - ma20_v) / ma20_v * 100
    vol = df["Volume"]
    vol_ma20 = vol.rolling(20).mean().iloc[-1]
    vol_ratio = vol.iloc[-1] / vol_ma20 if vol_ma20 > 0 else 0
    body = abs(c.iloc[-1] - c.iloc[-2])
    lower_shadow = min(c.iloc[-1], c.iloc[-2]) - min(df["Low"].iloc[-1], df["Low"].iloc[-2])

    det = []
    c1 = bias <= -5
    det.append(("BIAS 負乖離過大", c1, f"BIAS={bias:.1f}%（需<=-5%）"))
    c2 = price <= bl
    det.append(("布林通道下軌", c2, f"下軌={bl:.0f}｜{'已觸發' if c2 else '未觸發'}"))
    c3 = r14 <= 25
    det.append(("RSI 極端超賣", c3, f"RSI(14)={r14:.1f}（需<=25）"))
    c4 = vol_ratio >= 2.0 and lower_shadow > body
    det.append(("恐慌爆量+長下影", c4, f"放量={vol_ratio:.1f}x｜下影={lower_shadow:.0f} vs實體={body:.0f}"))

    cnt = sum(d[1] for d in det)
    return {"cnt": cnt, "det": det, "is_panic": cnt >= 2}
