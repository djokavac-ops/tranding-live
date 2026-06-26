import time
from datetime import datetime, timezone
from typing import List, Dict, Any
import requests
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Trading PWA Auto Demo")

SYMBOLS = {
    "WTI": {"name": "WTI Crude Oil", "ticker": "CL=F", "group": "Commodities"},
    "GOLD": {"name": "Gold", "ticker": "GC=F", "group": "Commodities"},
    "NASDAQ": {"name": "Nasdaq 100", "ticker": "NQ=F", "group": "Indices"},
    "SP500": {"name": "S&P 500", "ticker": "ES=F", "group": "Indices"},
    "BTC": {"name": "Bitcoin", "ticker": "BTC-USD", "group": "Crypto"},
    "AAPL": {"name": "Apple", "ticker": "AAPL", "group": "Stocks"},
    "MSFT": {"name": "Microsoft", "ticker": "MSFT", "group": "Stocks"},
    "NVDA": {"name": "Nvidia", "ticker": "NVDA", "group": "Stocks"},
    "TSLA": {"name": "Tesla", "ticker": "TSLA", "group": "Stocks"},
    "AMZN": {"name": "Amazon", "ticker": "AMZN", "group": "Stocks"},
    "GOOGL": {"name": "Alphabet", "ticker": "GOOGL", "group": "Stocks"},
    "META": {"name": "Meta", "ticker": "META", "group": "Stocks"},
    "AMD": {"name": "AMD", "ticker": "AMD", "group": "Stocks"},
    "NFLX": {"name": "Netflix", "ticker": "NFLX", "group": "Stocks"},
}

POSITIONS = {
    "WTI": {"side": "BUY", "entry": 77.56, "quantity": 30.0, "stop": 68.0, "target": 80.0}
}

CACHE = {"ts": 0, "data": None}

def fetch_chart(ticker: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": "1y", "interval": "1d"}
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
    if len(rows) < 60:
        raise ValueError("Nema dovoljno podataka.")
    return rows

def ema(values: List[float], span: int) -> float:
    alpha = 2 / (span + 1)
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1 - alpha) * result
    return result

def rsi(values: List[float], period: int = 14) -> float:
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
    trs, prev = [], rows[-period - 1]["close"]
    for row in rows[-period:]:
        tr = max(row["high"] - row["low"], abs(row["high"] - prev), abs(row["low"] - prev))
        trs.append(tr)
        prev = row["close"]
    return sum(trs) / len(trs)

def pct_change(values: List[float], n: int) -> float:
    if len(values) <= n:
        return 0.0
    return (values[-1] / values[-n-1] - 1) * 100

def smart_signal(rows: List[dict]) -> Dict[str, Any]:
    closes = [r["close"] for r in rows]
    price = closes[-1]
    e20 = ema(closes[-80:], 20)
    e50 = ema(closes[-160:] if len(closes) >= 160 else closes, 50)
    e200 = ema(closes, 200)
    r = rsi(closes)
    a = atr(rows)
    ch5 = pct_change(closes, 5)
    ch20 = pct_change(closes, 20)

    score = 0
    reasons = []
    if price > e20:
        score += 1; reasons.append("cena iznad EMA20")
    else:
        score -= 1; reasons.append("cena ispod EMA20")
    if e20 > e50:
        score += 1; reasons.append("EMA20 iznad EMA50")
    else:
        score -= 1; reasons.append("EMA20 ispod EMA50")
    if e50 > e200:
        score += 2; reasons.append("srednjoročni trend pozitivan")
    else:
        score -= 2; reasons.append("srednjoročni trend negativan")
    if 50 <= r <= 68:
        score += 1; reasons.append("RSI zdrav momentum")
    elif r > 72:
        score -= 1; reasons.append("RSI pregrejan")
    elif r < 40:
        score -= 1; reasons.append("RSI slab")
    if ch5 > 0 and ch20 > 0:
        score += 1; reasons.append("5d i 20d momentum pozitivni")
    elif ch5 < 0 and ch20 < 0:
        score -= 1; reasons.append("5d i 20d momentum negativni")

    if score >= 5:
        signal, action = "STRONG BUY", "Demo-bot sme da razmatra LONG."
    elif score >= 3:
        signal, action = "BUY WATCH", "Pratiti za mogući LONG; slabije od strong signala."
    elif score <= -5:
        signal, action = "STRONG SELL", "Demo-bot sme da razmatra SHORT."
    elif score <= -3:
        signal, action = "SELL WATCH", "Pratiti za mogući SHORT; slabije od strong signala."
    else:
        signal, action = "WAIT", "Bez trejda."

    trend = "BULLISH" if e50 > e200 else "BEARISH"
    if signal in ("STRONG SELL", "SELL WATCH"):
        stop = price + 1.5 * a
        target = price - 2.5 * a
        side = "SELL"
    else:
        stop = price - 1.5 * a
        target = price + 2.5 * a
        side = "BUY"

    rr = abs(target - price) / abs(price - stop) if abs(price - stop) else 0

    return {
        "price": round(price, 4), "ema20": round(e20, 4), "ema50": round(e50, 4),
        "ema200": round(e200, 4), "rsi": round(r, 2), "atr": round(a, 4),
        "change_5d": round(ch5, 2), "change_20d": round(ch20, 2), "trend": trend,
        "score": score, "signal": signal, "action": action, "reason": "; ".join(reasons[:5]),
        "entry": round(price, 4), "stop": round(stop, 4), "target": round(target, 4),
        "risk_reward": round(rr, 2), "suggested_side": side
    }

def position_metrics(symbol: str, price: float):
    p = POSITIONS.get(symbol)
    if not p:
        return None
    side, entry, qty, stop, target = p["side"].upper(), float(p["entry"]), float(p["quantity"]), float(p["stop"]), float(p["target"])
    pnl = (price - entry) * qty if side == "BUY" else (entry - price) * qty
    return {"side": side, "entry": entry, "quantity": qty, "stop": stop, "target": target,
            "pnl": round(pnl, 2)}

@app.get("/api/market")
def market():
    now = time.time()
    if CACHE["data"] is not None and now - CACHE["ts"] < 60:
        return CACHE["data"]
    result = {}
    for key, meta in SYMBOLS.items():
        try:
            rows = fetch_chart(meta["ticker"])
            sig = smart_signal(rows)
            sig.update({"name": meta["name"], "ticker": meta["ticker"], "group": meta["group"],
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "position": position_metrics(key, sig["price"])})
            result[key] = sig
        except Exception as e:
            result[key] = {"name": meta["name"], "ticker": meta["ticker"], "group": meta["group"], "error": str(e)}
    CACHE.update({"ts": now, "data": result})
    return result

@app.get("/api/symbol/{symbol}")
def symbol(symbol: str):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return {"error": "Nepoznat simbol"}
    meta = SYMBOLS[symbol]
    return {"symbol": symbol, "name": meta["name"], "rows": fetch_chart(meta["ticker"])[-180:]}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
