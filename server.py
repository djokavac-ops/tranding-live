import os
from datetime import datetime, timezone
from typing import Dict, Any

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

load_dotenv()

app = FastAPI(title="Trading PWA Live")

SYMBOLS = {
    "WTI": {"name": "WTI Crude Oil", "ticker": "CL=F"},
    "GOLD": {"name": "Gold", "ticker": "GC=F"},
    "NASDAQ": {"name": "Nasdaq 100", "ticker": "NQ=F"},
    "SP500": {"name": "S&P 500", "ticker": "ES=F"},
    "BTC": {"name": "Bitcoin", "ticker": "BTC-USD"},
}

# Ručno unesi svoje pozicije ovde ili kasnije poveži Capital.com API.
POSITIONS = {
    "WTI": {
        "side": "BUY",
        "entry": 77.56,
        "quantity": 30.0,
        "stop": 68.0,
        "target": 80.0,
    }
}


def download(ticker: str, period="6mo", interval="1d") -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df.dropna()


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["EMA20"] = out["Close"].ewm(span=20, adjust=False).mean()
    out["EMA50"] = out["Close"].ewm(span=50, adjust=False).mean()
    out["EMA200"] = out["Close"].ewm(span=200, adjust=False).mean()
    out["RSI14"] = RSIIndicator(out["Close"], window=14).rsi()
    out["ATR14"] = AverageTrueRange(out["High"], out["Low"], out["Close"], window=14).average_true_range()
    return out.dropna()


def make_signal(row: pd.Series) -> Dict[str, Any]:
    price = float(row["Close"])
    ema20 = float(row["EMA20"])
    ema50 = float(row["EMA50"])
    ema200 = float(row["EMA200"])
    rsi = float(row["RSI14"])
    atr = float(row["ATR14"])

    trend = "BULLISH" if ema50 > ema200 else "BEARISH"
    signal = "WAIT"
    reason = "Nema jakog signala."

    if trend == "BULLISH" and price > ema20 and 45 <= rsi <= 68:
        signal = "BUY WATCH"
        reason = "Pozitivan trend, cena iznad EMA20, RSI nije pregrejan."
    elif trend == "BEARISH" and price < ema20 and 32 <= rsi <= 55:
        signal = "SELL WATCH"
        reason = "Negativan trend, cena ispod EMA20."
    elif rsi > 72:
        signal = "OVERBOUGHT"
        reason = "Visok RSI; ne juriti cenu posle snažnog rasta."
    elif rsi < 28:
        signal = "OVERSOLD"
        reason = "Nizak RSI; moguća korekcija, ali čekati potvrdu."

    return {
        "price": round(price, 4),
        "ema20": round(ema20, 4),
        "ema50": round(ema50, 4),
        "ema200": round(ema200, 4),
        "rsi": round(rsi, 2),
        "atr": round(atr, 4),
        "trend": trend,
        "signal": signal,
        "reason": reason,
        "long_stop": round(price - 1.5 * atr, 4),
        "long_target": round(price + 2.5 * atr, 4),
        "short_stop": round(price + 1.5 * atr, 4),
        "short_target": round(price - 2.5 * atr, 4),
    }


def position_metrics(symbol: str, price: float):
    p = POSITIONS.get(symbol)
    if not p:
        return None
    side = p["side"].upper()
    entry = float(p["entry"])
    qty = float(p["quantity"])
    stop = float(p["stop"])
    target = float(p["target"])

    pnl = (price - entry) * qty if side == "BUY" else (entry - price) * qty
    risk = max(0, (entry - stop) * qty) if side == "BUY" else max(0, (stop - entry) * qty)
    potential = max(0, (target - entry) * qty) if side == "BUY" else max(0, (entry - target) * qty)
    to_stop_pct = ((price - stop) / price * 100) if side == "BUY" else ((stop - price) / price * 100)
    to_target_pct = ((target - price) / price * 100) if side == "BUY" else ((price - target) / price * 100)

    return {
        "side": side,
        "entry": entry,
        "quantity": qty,
        "stop": stop,
        "target": target,
        "pnl": round(pnl, 2),
        "risk_to_stop": round(risk, 2),
        "potential_to_target": round(potential, 2),
        "to_stop_pct": round(to_stop_pct, 2),
        "to_target_pct": round(to_target_pct, 2),
    }


def send_telegram(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"sent": False, "reason": "Telegram nije podešen."}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    return {"sent": r.ok, "status_code": r.status_code}


@app.get("/api/market")
def market():
    result = {}
    for key, meta in SYMBOLS.items():
        df = download(meta["ticker"])
        if df.empty:
            result[key] = {"error": "Nema podataka."}
            continue
        dfi = indicators(df)
        last = dfi.iloc[-1]
        sig = make_signal(last)
        sig["name"] = meta["name"]
        sig["ticker"] = meta["ticker"]
        sig["updated_at"] = datetime.now(timezone.utc).isoformat()
        sig["position"] = position_metrics(key, sig["price"])
        result[key] = sig
    return result


@app.get("/api/symbol/{symbol}")
def symbol(symbol: str):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return {"error": "Nepoznat simbol"}
    meta = SYMBOLS[symbol]
    df = indicators(download(meta["ticker"]))
    rows = []
    for idx, row in df.tail(120).iterrows():
        rows.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "ema20": round(float(row["EMA20"]), 4),
            "ema50": round(float(row["EMA50"]), 4),
            "ema200": round(float(row["EMA200"]), 4),
        })
    return {"symbol": symbol, "name": meta["name"], "rows": rows}


@app.post("/api/test-alert")
def test_alert():
    return send_telegram("Trading PWA test alert: sve radi.")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
