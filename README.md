# Trading PWA Live Final

Mobilna PWA aplikacija za iPhone + backend koji povlači cene za:
- WTI Crude Oil
- Gold
- Nasdaq 100
- S&P 500
- Bitcoin

Radi na Windows-u lokalno, a za stalno korišćenje na telefonu najbolje je deploy na Render/Railway.

## Pokretanje na Windows-u

1. Raspakuj ZIP.
2. Otvori PowerShell u folderu.
3. Pokreni:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

4. Na telefonu otvori:
`http://IP_ADRESA_TVOG_KOMPJUTERA:8000`

Ako si na istoj Wi-Fi mreži.

## Za stalno korišćenje na iPhone-u

Deploy na Render.com:
- New Web Service
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Otvori dobijeni link u Safari
- Share → Add to Home Screen

## Telegram alerti

Kopiraj `.env.example` u `.env` i unesi:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

## Važno

Podaci preko Yahoo Finance nisu profesionalni tick-by-tick feed i mogu kasniti.
Za CFD pozicije i izvršenje naloga treba dodati Capital.com API ključeve.
Ova aplikacija je za praćenje, disciplinu i signale — ne automatsko trgovanje.
