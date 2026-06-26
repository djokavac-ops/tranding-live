# Trading AI Final

One-package final version.

Includes:
- 50+ instruments
- pro scoring engine: EMA 8/20/50/100/200, RSI, MACD, Bollinger position, ATR, momentum, volume, breakout/breakdown, candlestick patterns
- paper trading with open/closed trades
- entry/current/stop/TP1/TP2/qty/PnL
- daily target, max loss, max trades, max open trades
- Capital.com adapter prepared but safe/off by default
- Telegram-ready

Render Start Command:
uvicorn server:app --host 0.0.0.0 --port $PORT

Replace all GitHub files with this package contents.
