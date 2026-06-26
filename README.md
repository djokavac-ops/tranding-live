# Trading AI Ultimate

This is the no-more-manual-run architecture:
- background engine thread
- auto_engine_enabled setting
- paper trades opened automatically when the engine is ON
- professional scoring across 50+ instruments
- daily target / max loss / max trades / max open trades
- engine log
- Telegram-ready
- Capital.com-ready but safe/off by default

Render Start Command:
uvicorn server:app --host 0.0.0.0 --port $PORT

Important Render note:
On Render Free, services can sleep when inactive. For true 24/7 behavior, use a paid always-on instance or add an external uptime/cron ping.
