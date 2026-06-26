# Trading AI Pro Paper + Capital Ready

Includes:
- professional paper trading workflow
- market confidence scoring
- open/closed trade tracking
- entry/current/stop/target/qty/PnL
- daily target / max loss / max trades
- Capital.com adapter prepared but disabled by default

Render start command:
uvicorn server:app --host 0.0.0.0 --port $PORT

For Capital.com later, add env vars:
CAPITAL_ENV=demo
CAPITAL_API_KEY=...
CAPITAL_IDENTIFIER=...
CAPITAL_PASSWORD=...
CAPITAL_AUTO_TRADE=false
