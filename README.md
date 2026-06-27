# Trading AI Elite 1.0

Use PostgreSQL for history that does not disappear.

Render start command:
uvicorn server:app --host 0.0.0.0 --port $PORT

Add DATABASE_URL from your Render PostgreSQL database.
If DATABASE_URL is empty, app falls back to local SQLite, which can reset on Render Free.
