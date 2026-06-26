# Trading AI Elite Persistent

This version is made to stop losing history.

Key point:
- If DB_PATH is not set, SQLite is stored inside the app container and Render Free can reset it.
- To persist history, add a Render Persistent Disk mounted at /var/data and set:
  DB_PATH=/var/data/trading_ai_elite.db

Features:
- 50+ instruments
- automatic paper engine
- open/closed trades with AI explanation
- Daily, Weekly, All-time report
- CSV export
- Telegram-ready
- Capital.com-ready but safe/off by default

Render start command:
uvicorn server:app --host 0.0.0.0 --port $PORT
