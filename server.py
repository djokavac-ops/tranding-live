import os, time, json, sqlite3, math
from datetime import datetime, timezone, date
from pathlib import Path
from typing import List, Dict, Any
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles

load_dotenv()

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "trading_ai_pro.db"
WATCHLIST_PATH = APP_DIR / "watchlist.json"

app = FastAPI(title="Trading AI Pro Paper + Capital Ready")

CACHE = {"market_ts": 0, "market": None}

DEFAULT_SETTINGS = {
    "account_size": 5000.0,
    "daily_target": 50.0,
    "daily_max_loss": 50.0,
    "risk_per_trade_pct": 0.5,
    "max_trades_per_day": 3,
    "min_confidence": 72,
    "min_risk_reward": 1.35,
    "auto_paper_enabled": True,
    "trading_mode": "paper",
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS paper_trades(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,
        group_name TEXT NOT NULL,
        side TEXT NOT NULL,
        entry REAL NOT NULL,
        current_price REAL NOT NULL,
        stop REAL NOT NULL,
        target REAL NOT NULL,
        qty REAL NOT NULL,
        confidence INTEGER NOT NULL,
        risk_reward REAL NOT NULL,
        status TEXT NOT NULL,
        pnl REAL NOT NULL,
        reason TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS decisions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        symbol TEXT NOT NULL,
        decision TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        reason TEXT NOT NULL
    )
    """)
    for k, v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, json.dumps(v)))
    conn.commit()
    conn.close()

init_db()

def get_settings():
    conn = db()
    rows = conn.execute("SELECT key,value FROM settings").fetchall()
    conn.close()
    s = DEFAULT_SETTINGS.copy()
    for r in rows:
        try: s[r["key"]] = json.loads(r["value"])
        except Exception: s[r["key"]] = r["value"]
    return s

def save_settings(payload):
    conn = db()
    c = conn.cursor()
    for k, v in payload.items():
        if k in DEFAULT_SETTINGS:
            c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, json.dumps(v)))
    conn.commit()
    conn.close()
    return get_settings()

def load_symbols():
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["symbols"]

def today():
    return date.today().isoformat()

def fetch_chart_yahoo(ticker, range_="1y", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(url, params={"range": range_, "interval": interval}, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
    r.raise_for_status()
    data = r.json()["chart"]["result"][0]
    q = data["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(data["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        v = q.get("volume", [0] * len(data["timestamp"]))[i]
        if None in (o, h, l, c): continue
        rows.append({
            "date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"),
            "open": float(o), "high": float(h), "low": float(l), "close": float(c),
            "volume": float(v or 0)
        })
    if len(rows) < 90:
        raise ValueError("Not enough data")
    return rows

def ema(vals, span):
    alpha = 2 / (span + 1)
    out = vals[0]
    for v in vals[1:]:
        out = alpha*v + (1-alpha)*out
    return out

def sma(vals, n):
    vals = vals[-n:] if len(vals) >= n else vals
    return sum(vals)/len(vals) if vals else 0

def rsi(vals, n=14):
    if len(vals) <= n: return 50
    gains, losses = [], []
    for i in range(-n, 0):
        ch = vals[i] - vals[i-1]
        gains.append(max(ch, 0))
        losses.append(abs(min(ch, 0)))
    ag, al = sum(gains)/n, sum(losses)/n
    if al == 0: return 100
    rs = ag/al
    return 100 - 100/(1+rs)

def atr(rows, n=14):
    if len(rows) <= n+1: return 0
    trs = []
    prev = rows[-n-1]["close"]
    for row in rows[-n:]:
        tr = max(row["high"]-row["low"], abs(row["high"]-prev), abs(row["low"]-prev))
        trs.append(tr); prev = row["close"]
    return sum(trs)/len(trs)

def macd(vals):
    e12 = ema(vals[-80:], 12)
    e26 = ema(vals[-100:], 26)
    line = e12 - e26
    return line

def bollinger_position(vals, n=20):
    recent = vals[-n:]
    mean = sum(recent)/len(recent)
    variance = sum((x-mean)**2 for x in recent)/len(recent)
    sd = math.sqrt(variance)
    upper, lower = mean + 2*sd, mean - 2*sd
    price = vals[-1]
    if upper == lower: return 0.5
    return (price - lower) / (upper - lower)

def pct(vals, n):
    if len(vals) <= n: return 0
    return (vals[-1] / vals[-n-1] - 1) * 100

def analyze(rows, meta):
    closes = [x["close"] for x in rows]
    vols = [x["volume"] for x in rows]
    price = closes[-1]
    e20, e50, e200 = ema(closes[-80:], 20), ema(closes[-160:], 50), ema(closes, 200)
    r = rsi(closes)
    a = atr(rows)
    m = macd(closes)
    bb = bollinger_position(closes)
    ch5, ch20, ch60 = pct(closes, 5), pct(closes, 20), pct(closes, 60)
    vol_factor = vols[-1] / sma(vols, 20) if sma(vols, 20) > 0 else 1
    recent_high = max(x["high"] for x in rows[-20:])
    recent_low = min(x["low"] for x in rows[-20:])

    score = 50
    reasons = []

    if price > e20: score += 6; reasons.append("cena iznad EMA20")
    else: score -= 6; reasons.append("cena ispod EMA20")
    if e20 > e50: score += 8; reasons.append("EMA20 iznad EMA50")
    else: score -= 8; reasons.append("EMA20 ispod EMA50")
    if e50 > e200: score += 12; reasons.append("glavni trend pozitivan")
    else: score -= 12; reasons.append("glavni trend negativan")
    if m > 0: score += 5; reasons.append("MACD pozitivan")
    else: score -= 5; reasons.append("MACD negativan")
    if 50 <= r <= 67: score += 7; reasons.append("RSI zdrav")
    elif r > 75: score -= 8; reasons.append("RSI pregrejan")
    elif r < 35: score -= 8; reasons.append("RSI slab/oversold")
    if ch5 > 0 and ch20 > 0: score += 8; reasons.append("kratki i mesečni momentum pozitivni")
    elif ch5 < 0 and ch20 < 0: score -= 8; reasons.append("kratki i mesečni momentum negativni")
    if ch60 > 0: score += 4
    else: score -= 4
    if price > recent_high * 0.995: score += 4; reasons.append("blizu 20d breakout-a")
    if price < recent_low * 1.005: score -= 4; reasons.append("blizu 20d breakdown-a")
    if vol_factor > 1.35: score += 3; reasons.append("pojačan volumen")
    if bb > 0.95: score -= 4; reasons.append("cena visoko u Bollinger opsegu")
    if bb < 0.05: score -= 2; reasons.append("cena nisko u Bollinger opsegu")

    score = max(0, min(100, round(score)))

    if score >= 80:
        signal, side = "STRONG BUY", "BUY"
    elif score >= 66:
        signal, side = "BUY WATCH", "BUY"
    elif score <= 20:
        signal, side = "STRONG SELL", "SELL"
    elif score <= 34:
        signal, side = "SELL WATCH", "SELL"
    else:
        signal, side = "WAIT", "WAIT"

    min_stop = max(a * 1.5, price * 0.01)
    min_target = max(a * 2.5, price * 0.015)
    if side == "SELL":
        stop, target = price + min_stop, price - min_target
    else:
        stop, target = price - min_stop, price + min_target

    rr = abs(target-price) / abs(price-stop) if abs(price-stop) else 0
    risk = "LOW" if a/price < 0.025 else "MEDIUM" if a/price < 0.055 else "HIGH"

    return {
        "symbol": None, "name": meta["name"], "ticker": meta["ticker"], "group": meta["group"],
        "price": round(price,4), "signal": signal, "side": side, "confidence": int(score),
        "risk": risk, "trend": "BULLISH" if e50 > e200 else "BEARISH",
        "rsi": round(r,2), "atr": round(a,4), "macd": round(m,4), "bollinger_pos": round(bb,2),
        "ema20": round(e20,4), "ema50": round(e50,4), "ema200": round(e200,4),
        "change_5d": round(ch5,2), "change_20d": round(ch20,2), "change_60d": round(ch60,2),
        "entry": round(price,4), "stop": round(stop,4), "target": round(target,4), "risk_reward": round(rr,2),
        "reason": "; ".join(reasons[:8]), "updated_at": datetime.now(timezone.utc).isoformat()
    }

def market(force=False):
    now = time.time()
    if not force and CACHE["market"] and now-CACHE["market_ts"] < 60:
        return CACHE["market"]
    out = {}
    for symbol, meta in load_symbols().items():
        if not meta.get("enabled", True): continue
        try:
            rows = fetch_chart_yahoo(meta["ticker"])
            item = analyze(rows, meta)
            item["symbol"] = symbol
            out[symbol] = item
            log_decision(symbol, item["signal"], item["confidence"], item["reason"])
        except Exception as e:
            out[symbol] = {"symbol": symbol, "name": meta["name"], "ticker": meta["ticker"], "group": meta["group"], "error": str(e)}
    CACHE["market"], CACHE["market_ts"] = out, now
    return out

def log_decision(symbol, decision, confidence, reason):
    conn = db()
    conn.execute("INSERT INTO decisions(ts,symbol,decision,confidence,reason) VALUES(?,?,?,?,?)",
                 (datetime.now(timezone.utc).isoformat(), symbol, decision, confidence, reason))
    conn.commit(); conn.close()

def trades_today():
    conn = db()
    rows = conn.execute("SELECT * FROM paper_trades WHERE day=? ORDER BY id DESC", (today(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def open_trades():
    conn = db()
    rows = conn.execute("SELECT * FROM paper_trades WHERE status='OPEN' ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def pnl_today():
    return round(sum(float(x["pnl"]) for x in trades_today()), 2)

def send_telegram(text):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN",""), os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat_id: return {"sent": False}
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        return {"sent": r.ok}
    except Exception:
        return {"sent": False}

def update_open_trades(snapshot):
    conn = db()
    cur = conn.cursor()
    for t in open_trades():
        x = snapshot.get(t["symbol"])
        if not x or x.get("error"): continue
        price = float(x["price"])
        side = t["side"]
        pnl = (price - t["entry"]) * t["qty"] if side == "BUY" else (t["entry"] - price) * t["qty"]
        status = "OPEN"
        if side == "BUY" and price <= t["stop"]: status = "STOP_LOSS"
        if side == "BUY" and price >= t["target"]: status = "TAKE_PROFIT"
        if side == "SELL" and price >= t["stop"]: status = "STOP_LOSS"
        if side == "SELL" and price <= t["target"]: status = "TAKE_PROFIT"
        closed_at = datetime.now(timezone.utc).isoformat() if status != "OPEN" else None
        cur.execute("UPDATE paper_trades SET current_price=?, pnl=?, status=?, closed_at=? WHERE id=?",
                    (price, round(pnl,2), status, closed_at, t["id"]))
        if status != "OPEN":
            send_telegram(f"Paper close: {status} {t['name']} PnL {round(pnl,2)} EUR")
    conn.commit(); conn.close()

def best_candidate(snapshot, settings):
    candidates = []
    symbols_open = {t["symbol"] for t in open_trades()}
    for symbol, x in snapshot.items():
        if x.get("error") or symbol in symbols_open: continue
        if x["signal"] not in ("STRONG BUY", "STRONG SELL"): continue
        if x["confidence"] < settings["min_confidence"]: continue
        if x["risk_reward"] < settings["min_risk_reward"]: continue
        candidates.append(x)
    candidates.sort(key=lambda x: (x["confidence"], x["risk_reward"]), reverse=True)
    return candidates[0] if candidates else None

def run_paper_cycle():
    settings = get_settings()
    snapshot = market(force=True)
    update_open_trades(snapshot)

    current_pnl = pnl_today()
    todays = trades_today()
    if current_pnl >= settings["daily_target"]:
        return {"executed": False, "status": "STOP: daily target reached", "daily_pnl": current_pnl}
    if current_pnl <= -settings["daily_max_loss"]:
        return {"executed": False, "status": "STOP: daily max loss reached", "daily_pnl": current_pnl}
    if len(todays) >= int(settings["max_trades_per_day"]):
        return {"executed": False, "status": "STOP: max trades reached", "daily_pnl": current_pnl}

    c = best_candidate(snapshot, settings)
    if not c:
        return {"executed": False, "status": "No qualified opportunity", "daily_pnl": current_pnl}

    risk_money = settings["account_size"] * settings["risk_per_trade_pct"] / 100
    stop_dist = abs(c["entry"] - c["stop"])
    qty = risk_money / stop_dist if stop_dist > 0 else 0

    conn = db()
    conn.execute("""
    INSERT INTO paper_trades(day,opened_at,closed_at,symbol,name,group_name,side,entry,current_price,stop,target,qty,confidence,risk_reward,status,pnl,reason)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (today(), datetime.now(timezone.utc).isoformat(), None, c["symbol"], c["name"], c["group"], c["side"],
          c["entry"], c["price"], c["stop"], c["target"], qty, c["confidence"], c["risk_reward"], "OPEN", 0.0, c["reason"]))
    conn.commit(); conn.close()

    msg = f"Paper open: {c['side']} {c['name']} @ {c['entry']} | SL {c['stop']} | TP {c['target']} | conf {c['confidence']}%"
    send_telegram(msg)
    return {"executed": True, "status": msg, "candidate": c, "daily_pnl": pnl_today()}

class CapitalClient:
    """Prepared adapter. It reads env vars but will not trade unless CAPITAL_AUTO_TRADE=true."""
    def __init__(self):
        self.env = os.getenv("CAPITAL_ENV", "demo")
        self.api_key = os.getenv("CAPITAL_API_KEY", "")
        self.identifier = os.getenv("CAPITAL_IDENTIFIER", "")
        self.password = os.getenv("CAPITAL_PASSWORD", "")
        self.auto_trade = os.getenv("CAPITAL_AUTO_TRADE", "false").lower() == "true"
        self.base = "https://demo-api-capital.backend-capital.com/api/v1" if self.env == "demo" else "https://api-capital.backend-capital.com/api/v1"

    def configured(self):
        return bool(self.api_key and self.identifier and self.password)

    def status(self):
        return {"configured": self.configured(), "env": self.env, "auto_trade": self.auto_trade, "safe": not self.auto_trade}

@app.get("/api/market")
def api_market(): return market()

@app.get("/api/settings")
def api_settings(): return get_settings()

@app.post("/api/settings")
def api_save_settings(payload: dict = Body(...)): return save_settings(payload)

@app.get("/api/paper/status")
def api_paper_status():
    snap = market()
    update_open_trades(snap)
    return {"day": today(), "daily_pnl": pnl_today(), "open": open_trades(), "trades": trades_today()}

@app.post("/api/paper/run-cycle")
def api_paper_run(): return run_paper_cycle()

@app.post("/api/paper/reset-day")
def api_reset_day():
    conn = db()
    conn.execute("DELETE FROM paper_trades WHERE day=?", (today(),))
    conn.commit(); conn.close()
    return {"ok": True, "daily_pnl": 0, "trades": []}

@app.get("/api/capital/status")
def api_capital_status(): return CapitalClient().status()

@app.post("/api/test-alert")
def api_test_alert(): return send_telegram("Trading AI Pro alert test")

app.mount("/", StaticFiles(directory="static", html=True), name="static")
