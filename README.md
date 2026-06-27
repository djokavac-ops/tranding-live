# Trading AI Elite 2.1 Autonomous

New:
- AI analiza tržišta radi sama u pozadini.
- Auto engine je uključen podrazumevano.
- Market snapshots se čuvaju u PostgreSQL.
- Dashboard prikazuje AI market brief.
- Paper engine poštuje target, max loss, broj trejdova, confidence i risk/reward.

Deploy:
1. Upload all files to GitHub.
2. Keep DATABASE_URL on Render.
3. Start command:
   uvicorn server:app --host 0.0.0.0 --port $PORT

Note:
This is paper trading and analysis. It does not guarantee profit.


## New in 2.1

- Autonomous status panel.
- Automatic daily Telegram report after report_hour_utc.
- Automatic weekly Telegram report on Sunday after report_hour_utc.
- Manual Telegram report buttons.
- Background AI loop still scans market and runs paper trading automatically.

Important on Render Free:
Render Free web services can sleep when inactive. Auto AI continues when service is awake.
For true 24/7 operation, use paid always-on service or an external ping/cron.
