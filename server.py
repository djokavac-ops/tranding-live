import os, time, json, sqlite3, math
from datetime import datetime, timezone, date
from pathlib import Path
from typing import List
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles

load_dotenv()
APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "trading_ai_final.db"
WATCHLIST_PATH = APP_DIR / "watchlist.json"

app = FastAPI(title="Trading AI Final")
CACHE = {"market_ts": 0, "market": None}

DEFAULT_SETTINGS = {
    "account_size": 5000.0,
    "daily_target": 50.0,
    "daily_max_loss": 50.0,
    "risk_per_trade_pct": 0.5,
    "max_trades_per_day": 3,
    "max_open_trades": 2,
    "min_confidence": 76,
    "min_risk_reward": 1.45,
    "auto_paper_enabled": False,
    "trading_mode": "paper"
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
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
        target1 REAL NOT NULL,
        target2 REAL NOT NULL,
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
        risk TEXT NOT NULL,
        reason TEXT NOT NULL
    )
    """)
    for k,v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, json.dumps(v)))
    conn.commit(); conn.close()

init_db()

def today(): return date.today().isoformat()

def get_settings():
    conn = db(); rows = conn.execute("SELECT key,value FROM settings").fetchall(); conn.close()
    s = DEFAULT_SETTINGS.copy()
    for r in rows:
        try: s[r["key"]] = json.loads(r["value"])
        except Exception: s[r["key"]] = r["value"]
    return s

def save_settings(payload):
    conn = db(); c = conn.cursor()
    for k,v in payload.items():
        if k in DEFAULT_SETTINGS:
            c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, json.dumps(v)))
    conn.commit(); conn.close()
    return get_settings()

def load_symbols():
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["symbols"]

def fetch_chart(ticker, range_="1y", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(url, params={"range": range_, "interval": interval}, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
    r.raise_for_status()
    payload = r.json()
    result = payload.get("chart", {}).get("result")
    if not result: raise ValueError("No data")
    data = result[0]; q = data["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(data["timestamp"]):
        o,h,l,c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        v = q.get("volume", [0]*len(data["timestamp"]))[i]
        if None in (o,h,l,c): continue
        rows.append({"date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"),
                     "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v or 0)})
    if len(rows) < 90: raise ValueError("Not enough data")
    return rows

def ema(vals, span):
    alpha = 2/(span+1); out = vals[0]
    for v in vals[1:]: out = alpha*v + (1-alpha)*out
    return out

def sma(vals, n):
    vals = vals[-n:] if len(vals) >= n else vals
    return sum(vals)/len(vals) if vals else 0

def rsi(vals, n=14):
    if len(vals) <= n: return 50
    gains=[]; losses=[]
    for i in range(-n,0):
        ch=vals[i]-vals[i-1]; gains.append(max(ch,0)); losses.append(abs(min(ch,0)))
    ag=sum(gains)/n; al=sum(losses)/n
    if al == 0: return 100
    return 100 - 100/(1+ag/al)

def atr(rows, n=14):
    if len(rows) <= n+1: return 0
    trs=[]; prev=rows[-n-1]["close"]
    for row in rows[-n:]:
        trs.append(max(row["high"]-row["low"], abs(row["high"]-prev), abs(row["low"]-prev)))
        prev=row["close"]
    return sum(trs)/len(trs)

def macd(vals):
    return ema(vals[-100:], 12) - ema(vals[-120:], 26)

def bollinger_pos(vals, n=20):
    recent=vals[-n:]; mean=sum(recent)/len(recent)
    sd=math.sqrt(sum((x-mean)**2 for x in recent)/len(recent))
    upper=mean+2*sd; lower=mean-2*sd
    return 0.5 if upper==lower else (vals[-1]-lower)/(upper-lower)

def pct(vals, n):
    return 0 if len(vals)<=n else (vals[-1]/vals[-n-1]-1)*100

def candle_pattern(rows):
    last=rows[-1]; prev=rows[-2]
    body=abs(last["close"]-last["open"]); rng=max(0.0001,last["high"]-last["low"])
    upper=last["high"]-max(last["close"],last["open"])
    lower=min(last["close"],last["open"])-last["low"]
    if body/rng < 0.12: return "DOJI", 0
    if lower > body*2 and upper < body: return "HAMMER", 4
    if upper > body*2 and lower < body: return "SHOOTING_STAR", -4
    if last["close"] > last["open"] and prev["close"] < prev["open"] and last["close"] > prev["open"] and last["open"] < prev["close"]:
        return "BULLISH_ENGULFING", 6
    if last["close"] < last["open"] and prev["close"] > prev["open"] and last["open"] > prev["close"] and last["close"] < prev["open"]:
        return "BEARISH_ENGULFING", -6
    return "NONE", 0

def analyze(rows, meta):
    closes=[x["close"] for x in rows]; vols=[x["volume"] for x in rows]
    price=closes[-1]
    e8=ema(closes[-60:],8); e20=ema(closes[-80:],20); e50=ema(closes[-160:],50); e100=ema(closes[-220:],100); e200=ema(closes,200)
    rv=rsi(closes); av=atr(rows); mv=macd(closes); bb=bollinger_pos(closes)
    ch5=pct(closes,5); ch20=pct(closes,20); ch60=pct(closes,60)
    vol_avg=sma(vols,20); vol_factor=vols[-1]/vol_avg if vol_avg>0 else 1
    high20=max(x["high"] for x in rows[-20:]); low20=min(x["low"] for x in rows[-20:])
    high60=max(x["high"] for x in rows[-60:]); low60=min(x["low"] for x in rows[-60:])
    pattern, pscore = candle_pattern(rows)

    score=50; reasons=[]; bearish_reasons=[]
    if price>e20: score+=6; reasons.append("price>EMA20")
    else: score-=6; bearish_reasons.append("price<EMA20")
    if e8>e20>e50: score+=10; reasons.append("EMA alignment bullish")
    elif e8<e20<e50: score-=10; bearish_reasons.append("EMA alignment bearish")
    if e50>e200: score+=12; reasons.append("main trend bullish")
    else: score-=12; bearish_reasons.append("main trend bearish")
    if e100>e200: score+=4
    else: score-=4
    if mv>0: score+=6; reasons.append("MACD positive")
    else: score-=6; bearish_reasons.append("MACD negative")
    if 50<=rv<=66: score+=8; reasons.append("RSI healthy")
    elif 66<rv<=72: score+=2; reasons.append("RSI strong")
    elif rv>75: score-=9; bearish_reasons.append("RSI overbought")
    elif rv<35: score-=9; bearish_reasons.append("RSI weak/oversold")
    elif rv<45: score-=4
    if ch5>0 and ch20>0: score+=8; reasons.append("5d+20d momentum positive")
    elif ch5<0 and ch20<0: score-=8; bearish_reasons.append("5d+20d momentum negative")
    if ch60>0: score+=5
    else: score-=5
    if price>high20*0.995: score+=4; reasons.append("near 20d breakout")
    if price<low20*1.005: score-=4; bearish_reasons.append("near 20d breakdown")
    if price>high60*0.995: score+=3
    if price<low60*1.005: score-=3
    if vol_factor>1.4: score+=3; reasons.append("volume expansion")
    if bb>0.95: score-=4; bearish_reasons.append("Bollinger high")
    if bb<0.05: score-=2; bearish_reasons.append("Bollinger low")
    score+=pscore
    if pattern!="NONE": (reasons if pscore>=0 else bearish_reasons).append(pattern)

    score=max(0,min(100,round(score)))
    if score>=82: signal,side="STRONG BUY","BUY"
    elif score>=68: signal,side="BUY WATCH","BUY"
    elif score<=18: signal,side="STRONG SELL","SELL"
    elif score<=32: signal,side="SELL WATCH","SELL"
    else: signal,side="WAIT","WAIT"

    stop_dist=max(av*1.5, price*0.01)
    t1_dist=max(av*2.2, price*0.014)
    t2_dist=max(av*3.4, price*0.022)
    if side=="SELL":
        stop=price+stop_dist; t1=price-t1_dist; t2=price-t2_dist
    else:
        stop=price-stop_dist; t1=price+t1_dist; t2=price+t2_dist
    rr=abs(t1-price)/abs(price-stop) if abs(price-stop)>0 else 0
    vol_risk=av/price if price else 0
    risk="LOW" if vol_risk<0.025 else "MEDIUM" if vol_risk<0.055 else "HIGH"
    reason_list=(reasons if side=="BUY" else bearish_reasons)[:8]
    if side=="WAIT": reason_list=(reasons+bearish_reasons)[:8]
    return {"symbol":None,"name":meta["name"],"ticker":meta["ticker"],"group":meta["group"],"price":round(price,4),
            "signal":signal,"side":side,"confidence":int(score),"risk":risk,"trend":"BULLISH" if e50>e200 else "BEARISH",
            "rsi":round(rv,2),"atr":round(av,4),"macd":round(mv,4),"bollinger_pos":round(bb,2),"candle":pattern,
            "ema8":round(e8,4),"ema20":round(e20,4),"ema50":round(e50,4),"ema100":round(e100,4),"ema200":round(e200,4),
            "change_5d":round(ch5,2),"change_20d":round(ch20,2),"change_60d":round(ch60,2),
            "entry":round(price,4),"stop":round(stop,4),"target1":round(t1,4),"target2":round(t2,4),"risk_reward":round(rr,2),
            "reason":"; ".join(reason_list),"updated_at":datetime.now(timezone.utc).isoformat()}

def log_decision(symbol,x):
    conn=db()
    conn.execute("INSERT INTO decisions(ts,symbol,decision,confidence,risk,reason) VALUES(?,?,?,?,?,?)",
                 (datetime.now(timezone.utc).isoformat(),symbol,x.get("signal","ERR"),x.get("confidence",0),x.get("risk",""),x.get("reason","")))
    conn.commit(); conn.close()

def market(force=False):
    now=time.time()
    if not force and CACHE["market"] and now-CACHE["market_ts"]<60: return CACHE["market"]
    out={}
    for symbol, meta in load_symbols().items():
        if not meta.get("enabled", True): continue
        try:
            rows=fetch_chart(meta["ticker"])
            x=analyze(rows,meta); x["symbol"]=symbol; out[symbol]=x; log_decision(symbol,x)
        except Exception as e:
            out[symbol]={"symbol":symbol,"name":meta["name"],"ticker":meta["ticker"],"group":meta["group"],"error":str(e)}
    CACHE["market"]=out; CACHE["market_ts"]=now
    return out

def trades_today():
    conn=db(); rows=conn.execute("SELECT * FROM paper_trades WHERE day=? ORDER BY id DESC",(today(),)).fetchall(); conn.close()
    return [dict(r) for r in rows]

def open_trades():
    conn=db(); rows=conn.execute("SELECT * FROM paper_trades WHERE status='OPEN' ORDER BY id DESC").fetchall(); conn.close()
    return [dict(r) for r in rows]

def pnl_today(): return round(sum(float(x["pnl"]) for x in trades_today()),2)

def send_telegram(text):
    token=os.getenv("TELEGRAM_BOT_TOKEN",""); chat_id=os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat_id: return {"sent":False,"reason":"not configured"}
    try:
        r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":chat_id,"text":text},timeout=10)
        return {"sent":r.ok}
    except Exception as e: return {"sent":False,"error":str(e)}

def update_open(snapshot):
    conn=db(); c=conn.cursor()
    for t in open_trades():
        x=snapshot.get(t["symbol"])
        if not x or x.get("error"): continue
        price=float(x["price"]); side=t["side"]
        pnl=(price-t["entry"])*t["qty"] if side=="BUY" else (t["entry"]-price)*t["qty"]
        status="OPEN"
        if side=="BUY" and price<=t["stop"]: status="STOP_LOSS"
        if side=="BUY" and price>=t["target1"]: status="TAKE_PROFIT"
        if side=="SELL" and price>=t["stop"]: status="STOP_LOSS"
        if side=="SELL" and price<=t["target1"]: status="TAKE_PROFIT"
        closed=datetime.now(timezone.utc).isoformat() if status!="OPEN" else None
        c.execute("UPDATE paper_trades SET current_price=?, pnl=?, status=?, closed_at=? WHERE id=?",
                  (price,round(pnl,2),status,closed,t["id"]))
        if status!="OPEN": send_telegram(f"Paper close {status}: {t['side']} {t['name']} PnL {round(pnl,2)} EUR")
    conn.commit(); conn.close()

def best_candidate(snapshot, settings):
    open_symbols={t["symbol"] for t in open_trades()}
    cands=[]
    for symbol,x in snapshot.items():
        if x.get("error") or symbol in open_symbols: continue
        if x["signal"] not in ("STRONG BUY","STRONG SELL"): continue
        if x["confidence"] < settings["min_confidence"]: continue
        if x["risk_reward"] < settings["min_risk_reward"]: continue
        if x["risk"]=="HIGH" and x["confidence"]<88: continue
        cands.append(x)
    cands.sort(key=lambda x:(x["confidence"],x["risk_reward"], -abs(x["change_5d"])), reverse=True)
    return cands[0] if cands else None

def run_cycle():
    settings=get_settings(); snap=market(force=True); update_open(snap)
    p=pnl_today(); all_trades=trades_today(); opened=open_trades()
    if p>=settings["daily_target"]: return {"executed":False,"status":"STOP: daily target reached","daily_pnl":p}
    if p<=-settings["daily_max_loss"]: return {"executed":False,"status":"STOP: daily max loss reached","daily_pnl":p}
    if len(all_trades)>=int(settings["max_trades_per_day"]): return {"executed":False,"status":"STOP: max trades reached","daily_pnl":p}
    if len(opened)>=int(settings["max_open_trades"]): return {"executed":False,"status":"STOP: max open trades reached","daily_pnl":p}
    cand=best_candidate(snap,settings)
    if not cand: return {"executed":False,"status":"No qualified professional setup","daily_pnl":p}
    risk_money=settings["account_size"]*settings["risk_per_trade_pct"]/100
    stop_dist=abs(cand["entry"]-cand["stop"])
    qty=risk_money/stop_dist if stop_dist>0 else 0
    conn=db()
    conn.execute("""
    INSERT INTO paper_trades(day,opened_at,closed_at,symbol,name,group_name,side,entry,current_price,stop,target1,target2,qty,confidence,risk_reward,status,pnl,reason)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(today(),datetime.now(timezone.utc).isoformat(),None,cand["symbol"],cand["name"],cand["group"],cand["side"],cand["entry"],cand["price"],cand["stop"],cand["target1"],cand["target2"],qty,cand["confidence"],cand["risk_reward"],"OPEN",0,cand["reason"]))
    conn.commit(); conn.close()
    msg=f"Paper open: {cand['side']} {cand['name']} @ {cand['entry']} | SL {cand['stop']} | TP1 {cand['target1']} | conf {cand['confidence']}%"
    send_telegram(msg)
    return {"executed":True,"status":msg,"candidate":cand,"daily_pnl":pnl_today()}

class CapitalClient:
    def __init__(self):
        self.env=os.getenv("CAPITAL_ENV","demo")
        self.api_key=os.getenv("CAPITAL_API_KEY","")
        self.identifier=os.getenv("CAPITAL_IDENTIFIER","")
        self.password=os.getenv("CAPITAL_PASSWORD","")
        self.auto_trade=os.getenv("CAPITAL_AUTO_TRADE","false").lower()=="true"
    def status(self):
        return {"configured":bool(self.api_key and self.identifier and self.password), "env":self.env, "auto_trade":self.auto_trade, "safe_mode":not self.auto_trade}

@app.get("/api/market")
def api_market(): return market()

@app.get("/api/settings")
def api_settings(): return get_settings()

@app.post("/api/settings")
def api_save(payload:dict=Body(...)): return save_settings(payload)

@app.get("/api/paper/status")
def api_paper_status():
    snap=market(); update_open(snap)
    return {"day":today(),"daily_pnl":pnl_today(),"open":open_trades(),"trades":trades_today()}

@app.post("/api/paper/run-cycle")
def api_run(): return run_cycle()

@app.post("/api/paper/auto-run")
def api_auto_run():
    settings=get_settings()
    if not settings.get("auto_paper_enabled"): return {"ok":False,"status":"Auto paper disabled"}
    return run_cycle()

@app.post("/api/paper/reset-day")
def api_reset():
    conn=db(); conn.execute("DELETE FROM paper_trades WHERE day=?",(today(),)); conn.commit(); conn.close()
    return {"ok":True,"daily_pnl":0,"trades":[]}

@app.get("/api/capital/status")
def api_capital(): return CapitalClient().status()

@app.post("/api/test-alert")
def api_alert(): return send_telegram("Trading AI Final: Telegram connected.")

app.mount("/", StaticFiles(directory="static", html=True), name="static")
