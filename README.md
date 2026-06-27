# Trading AI Elite 2.0 Auto AI

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
