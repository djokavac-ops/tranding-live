
import os, time, json, sqlite3, requests
from datetime import datetime, timezone, date
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles
load_dotenv()
APP=Path(__file__).parent; DATA=APP/'data'; DATA.mkdir(exist_ok=True); DB=DATA/'trading_ai.db'; WATCH=APP/'watchlist.json'
app=FastAPI(title='Trading AI Full App')
CACHE={'ts':0,'data':None}
DEFAULT={'account_size':5000.0,'daily_target':50.0,'daily_max_loss':50.0,'risk_per_trade_pct':0.5,'max_trades_per_day':2,'min_confidence':70,'trade_mode':'paper'}
def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
    c=conn(); cur=c.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    cur.execute('CREATE TABLE IF NOT EXISTS demo_trades(id INTEGER PRIMARY KEY AUTOINCREMENT,day TEXT,ts TEXT,symbol TEXT,name TEXT,side TEXT,entry REAL,stop REAL,target REAL,qty REAL,confidence INTEGER,pnl REAL,status TEXT,reason TEXT)')
    for k,v in DEFAULT.items(): cur.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,json.dumps(v)))
    c.commit(); c.close()
init()
def settings():
    c=conn(); rows=c.execute('SELECT key,value FROM settings').fetchall(); c.close(); out=DEFAULT.copy()
    for r in rows:
        try: out[r['key']]=json.loads(r['value'])
        except Exception: out[r['key']]=r['value']
    return out
def update_settings(p):
    c=conn(); cur=c.cursor()
    for k,v in p.items():
        if k in DEFAULT: cur.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(k,json.dumps(v)))
    c.commit(); c.close(); return settings()
def watchlist(): return json.loads(WATCH.read_text(encoding='utf-8'))['symbols']
def fetch(ticker):
    r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}',params={'range':'1y','interval':'1d'},headers={'User-Agent':'Mozilla/5.0'},timeout=12); r.raise_for_status()
    data=r.json()['chart']['result'][0]; q=data['indicators']['quote'][0]; rows=[]
    for i,ts in enumerate(data['timestamp']):
        o,h,l,c=q['open'][i],q['high'][i],q['low'][i],q['close'][i]; v=(q.get('volume') or [0]*len(data['timestamp']))[i]
        if None in (o,h,l,c): continue
        rows.append({'date':datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%d'),'open':float(o),'high':float(h),'low':float(l),'close':float(c),'volume':float(v or 0)})
    if len(rows)<80: raise ValueError('Not enough data')
    return rows
def ema(vals,span):
    a=2/(span+1); res=vals[0]
    for v in vals[1:]: res=a*v+(1-a)*res
    return res
def rsi(vals,p=14):
    gains=[]; losses=[]
    for i in range(-p,0):
        ch=vals[i]-vals[i-1]; gains.append(max(ch,0)); losses.append(abs(min(ch,0)))
    ag=sum(gains)/p; al=sum(losses)/p
    if al==0: return 100.0
    rs=ag/al; return 100-(100/(1+rs))
def atr(rows,p=14):
    trs=[]; prev=rows[-p-1]['close']
    for row in rows[-p:]:
        tr=max(row['high']-row['low'],abs(row['high']-prev),abs(row['low']-prev)); trs.append(tr); prev=row['close']
    return sum(trs)/len(trs)
def pc(vals,n): return (vals[-1]/vals[-n-1]-1)*100 if len(vals)>n else 0
def analyze(rows,meta):
    closes=[r['close'] for r in rows]; price=closes[-1]; e20=ema(closes[-80:],20); e50=ema(closes[-160:] if len(closes)>=160 else closes,50); e200=ema(closes,200); rrsi=rsi(closes); a=atr(rows); ch5=pc(closes,5); ch20=pc(closes,20); ch60=pc(closes,60); score=50; reasons=[]
    if price>e20: score+=7; reasons.append('price above EMA20')
    else: score-=7; reasons.append('price below EMA20')
    if e20>e50: score+=8; reasons.append('EMA20 above EMA50')
    else: score-=8; reasons.append('EMA20 below EMA50')
    if e50>e200: score+=12; reasons.append('medium trend bullish')
    else: score-=12; reasons.append('medium trend bearish')
    if 50<=rrsi<=65: score+=7; reasons.append('RSI healthy')
    elif rrsi>72: score-=8; reasons.append('RSI overbought')
    elif rrsi<40: score-=8; reasons.append('RSI weak')
    if ch5>0 and ch20>0: score+=8; reasons.append('5d and 20d momentum positive')
    elif ch5<0 and ch20<0: score-=8; reasons.append('5d and 20d momentum negative')
    score += 4 if ch60>0 else -4; reasons.append('3m trend positive' if ch60>0 else '3m trend negative')
    score=max(0,min(100,int(round(score))))
    if score>=78: signal='STRONG BUY'; side='BUY'
    elif score>=65: signal='BUY WATCH'; side='BUY'
    elif score<=22: signal='STRONG SELL'; side='SELL'
    elif score<=35: signal='SELL WATCH'; side='SELL'
    else: signal='WAIT'; side='WAIT'
    if side=='SELL': stop=price+max(1.5*a,price*.01); target=price-max(2.5*a,price*.015)
    else: stop=price-max(1.5*a,price*.01); target=price+max(2.5*a,price*.015)
    risk='LOW' if a/price<.025 else 'MEDIUM' if a/price<.055 else 'HIGH'
    return {'name':meta['name'],'ticker':meta['ticker'],'group':meta['group'],'price':round(price,4),'signal':signal,'side':side,'confidence':score,'risk':risk,'trend':'BULLISH' if e50>e200 else 'BEARISH','rsi':round(rrsi,2),'atr':round(a,4),'ema20':round(e20,4),'ema50':round(e50,4),'ema200':round(e200,4),'change_5d':round(ch5,2),'change_20d':round(ch20,2),'change_60d':round(ch60,2),'entry':round(price,4),'stop':round(stop,4),'target':round(target,4),'risk_reward':round(abs(target-price)/abs(price-stop),2),'reason':'; '.join(reasons[:7]),'updated_at':datetime.now(timezone.utc).isoformat()}
def snapshot(force=False):
    now=time.time()
    if not force and CACHE['data'] and now-CACHE['ts']<60: return CACHE['data']
    out={}
    for sym,meta in watchlist().items():
        if not meta.get('enabled',True): continue
        try:
            x=analyze(fetch(meta['ticker']),meta); x['symbol']=sym; out[sym]=x
        except Exception as e: out[sym]={'symbol':sym,'name':meta['name'],'ticker':meta['ticker'],'group':meta['group'],'error':str(e)}
    CACHE.update({'ts':now,'data':out}); return out
def day(): return date.today().isoformat()
def trades():
    c=conn(); rows=c.execute('SELECT * FROM demo_trades WHERE day=? ORDER BY id DESC',(day(),)).fetchall(); c.close(); return [dict(r) for r in rows]
def pnl(): return round(sum(float(t['pnl']) for t in trades()),2)
def telegram(txt):
    token=os.getenv('TELEGRAM_BOT_TOKEN',''); chat=os.getenv('TELEGRAM_CHAT_ID','')
    if not token or not chat: return {'sent':False,'reason':'not configured'}
    r=requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat,'text':txt},timeout=10); return {'sent':r.ok,'status':r.status_code}
def candidate(mkt,st):
    arr=[x for x in mkt.values() if not x.get('error') and x['signal'] in ('STRONG BUY','STRONG SELL') and x['confidence']>=st['min_confidence'] and x['risk_reward']>=1.4]
    arr.sort(key=lambda x:(x['confidence'],x['risk_reward']),reverse=True); return arr[0] if arr else None
def simulate(x,st):
    if pnl()>=st['daily_target']: return {'executed':False,'status':'STOP: daily target reached','daily_pnl':pnl()}
    if pnl()<=-st['daily_max_loss']: return {'executed':False,'status':'STOP: daily max loss reached','daily_pnl':pnl()}
    if len(trades())>=int(st['max_trades_per_day']): return {'executed':False,'status':'STOP: max trades reached','daily_pnl':pnl()}
    entry=x['entry']; stop=x['stop']; risk_money=st['account_size']*st['risk_per_trade_pct']/100; qty=risk_money/abs(entry-stop); direction=1 if x['side']=='BUY' else -1; edge=(x['confidence']-50)/100; trade_pnl=round(direction*x['atr']*max(.15,min(.85,edge))*qty,2)
    c=conn(); c.execute('INSERT INTO demo_trades(day,ts,symbol,name,side,entry,stop,target,qty,confidence,pnl,status,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(day(),datetime.now(timezone.utc).isoformat(),x['symbol'],x['name'],x['side'],entry,stop,x['target'],qty,x['confidence'],trade_pnl,'EXECUTED_PAPER',x['reason'])); c.commit(); c.close(); telegram(f"Paper trade {x['side']} {x['name']} PnL {trade_pnl} EUR Daily {pnl()} EUR"); return {'executed':True,'status':f"Paper trade: {x['side']} {x['name']} | PnL {trade_pnl} EUR",'daily_pnl':pnl(),'candidate':x}
@app.get('/api/market')
def api_market(): return snapshot()
@app.get('/api/settings')
def api_settings(): return settings()
@app.post('/api/settings')
def api_update(p:dict=Body(...)): return update_settings(p)
@app.get('/api/trades/today')
def api_trades(): return {'day':day(),'pnl':pnl(),'trades':trades()}
@app.post('/api/paper/run-cycle')
def api_cycle():
    st=settings(); x=candidate(snapshot(True),st); return simulate(x,st) if x else {'executed':False,'status':'No qualified STRONG signal','daily_pnl':pnl()}
@app.post('/api/paper/reset-day')
def api_reset():
    c=conn(); c.execute('DELETE FROM demo_trades WHERE day=?',(day(),)); c.commit(); c.close(); return {'ok':True,'pnl':0,'trades':[]}
@app.post('/api/test-alert')
def api_alert(): return telegram('Trading AI test alert: connected')
@app.get('/api/symbol/{symbol}')
def api_symbol(symbol:str):
    w=watchlist(); symbol=symbol.upper()
    if symbol not in w: return {'error':'Unknown symbol'}
    return {'symbol':symbol,'name':w[symbol]['name'],'rows':fetch(w[symbol]['ticker'])[-180:]}
app.mount('/', StaticFiles(directory='static', html=True), name='static')
