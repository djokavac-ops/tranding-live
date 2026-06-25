import time
from datetime import datetime, timezone
from typing import Dict, Any, List
import requests
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Trading PWA Live Light")

SYMBOLS = {
    "WTI": {"name": "WTI Crude Oil", "ticker": "CL=F"},
    "GOLD": {"name": "Gold", "ticker": "GC=F"},
    "NASDAQ": {"name": "Nasdaq 100", "ticker": "NQ=F"},
    "SP500": {"name": "S&P 500", "ticker": "ES=F"},
    "BTC": {"name": "Bitcoin", "ticker": "BTC-USD"},
}

POSITIONS = {
    "WTI": {"side": "BUY", "entry": 77.56, "quantity": 30.0, "stop": 68.0, "target": 80.0}
}

CACHE = {"ts": 0, "data": None}


def fetch_chart(ticker: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": "6mo", "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    data = r.json()["chart"]["result"][0]
    q = data["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(data["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        rows.append({"date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"),
                     "open": float(o), "high": float(h), "low": float(l), "close": float(c)})
    return rows


def ema(values: List[float], span: int) -> float:
    alpha = 2 / (span + 1)
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1 - alpha) * result
    return result


def rsi(values: List[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains, losses = [], []
    for i in range(-period, 0):
        ch = values[i] - values[i - 1]
        gains.append(max(ch, 0))
        losses.append(abs(min(ch, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(rows: List[dict], period: int = 14) -> float:
    if len(rows) <= period + 1:
        return 0.0
    trs, prev = [], rows[-period - 1]["close"]
    for row in rows[-period:]:
        tr = max(row["high"] - row["low"], abs(row["high"] - prev), abs(row["low"] - prev))
        trs.append(tr)
        prev = row["close"]
    return sum(trs) / len(trs)


def make_signal(rows: List[dict]) -> Dict[str, Any]:
    closes = [r["close"] for r in rows]
    price = closes[-1]
    ema20 = ema(closes[-60:] if len(closes) >= 60 else closes, 20)
    ema50 = ema(closes[-120:] if len(closes) >= 120 else closes, 50)
    ema200 = ema(closes, 200)
    rsi14 = rsi(closes)
    atr14 = atr(rows)
    trend = "BULLISH" if ema50 > ema200 else "BEARISH"
    signal, reason = "WAIT", "Nema jakog signala."
    if trend == "BULLISH" and price > ema20 and 45 <= rsi14 <= 68:
        signal, reason = "BUY WATCH", "Pozitivan trend, cena iznad EMA20, RSI nije pregrejan."
    elif trend == "BEARISH" and price < ema20 and 32 <= rsi14 <= 55:
        signal, reason = "SELL WATCH", "Negativan trend, cena ispod EMA20."
    elif rsi14 > 72:
        signal, reason = "OVERBOUGHT", "Visok RSI; ne juriti cenu posle snažnog rasta."
    elif rsi14 < 28:
        signal, reason = "OVERSOLD", "Nizak RSI; moguća korekcija, ali čekati potvrdu."
    return {"price": round(price, 4), "ema20": round(ema20, 4), "ema50": round(ema50, 4),
            "ema200": round(ema200, 4), "rsi": round(rsi14, 2), "atr": round(atr14, 4),
            "trend": trend, "signal": signal, "reason": reason,
            "long_stop": round(price - 1.5 * atr14, 4), "long_target": round(price + 2.5 * atr14, 4),
            "short_stop": round(price + 1.5 * atr14, 4), "short_target": round(price - 2.5 * atr14, 4)}


def position_metrics(symbol: str, price: float):
    p = POSITIONS.get(symbol)
    if not p:
        return None
    side, entry, qty, stop, target = p["side"].upper(), float(p["entry"]), float(p["quantity"]), float(p["stop"]), float(p["target"])
    pnl = (price - entry) * qty if side == "BUY" else (entry - price) * qty
    return {"side": side, "entry": entry, "quantity": qty, "stop": stop, "target": target,
            "pnl": round(pnl, 2),
            "to_stop_pct": round(((price - stop) / price * 100), 2) if side == "BUY" else round(((stop - price) / price * 100), 2),
            "to_target_pct": round(((target - price) / price * 100), 2) if side == "BUY" else round(((price - target) / price * 100), 2)}


@app.get("/api/market")
def market():
    now = time.time()
    if CACHE["data"] is not None and now - CACHE["ts"] < 60:
        return CACHE["data"]
    result = {}
    for key, meta in SYMBOLS.items():
        try:
            rows = fetch_chart(meta["ticker"])
            sig = make_signal(rows)
            sig.update({"name": meta["name"], "ticker": meta["ticker"],
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "position": position_metrics(key, sig["price"])})
            result[key] = sig
        except Exception as e:
            result[key] = {"name": meta["name"], "error": str(e)}
    CACHE.update({"ts": now, "data": result})
    return result


@app.get("/api/symbol/{symbol}")
def symbol(symbol: str):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return {"error": "Nepoznat simbol"}
    meta = SYMBOLS[symbol]
    return {"symbol": symbol, "name": meta["name"], "rows": fetch_chart(meta["ticker"])[-120:]}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
