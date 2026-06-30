# Trading AI Elite 7.0 AI Hedge Fund Edition

Built on 6.0 Infrastructure.

Purpose:
- Move from trading bot to AI portfolio desk
- Protect capital first
- Trade only high-consensus opportunities
- Stay paper-first and live-locked

Added:
- AI Chief Investment Officer memo
- Hedge Fund Engine
- Regime classifier
- Strategy auto-selector
- Signal voting desk
- Portfolio heat allocation
- Paper-to-live readiness gate
- Hedge fund decision log
- Strategy selector log
- CIO memo log

Main endpoints:
- /api/hedge-fund/status
- /api/hedge-fund/engine
- /api/hedge-fund/cio
- /api/hedge-fund/regime
- /api/hedge-fund/strategy
- /api/hedge-fund/live-readiness

Rules:
- Live remains locked.
- Paper-first remains active.
- Minimum paper-trade gate before live.
- Portfolio heat gate.
- Multi-desk consensus before any proposed trade.

Infrastructure:
- Keeps 6.0 IBKR/TWS/Gateway endpoints.
- Render-safe.
- No pandas.
- Excel through openpyxl.
