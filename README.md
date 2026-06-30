# Trading AI Elite 7.1 Unified Project

This is now the main project base going forward.

Purpose:
- Stop deleting/re-uploading GitHub for every version
- Keep one unified project
- Make Render usable as dashboard
- Make local/VPS backend usable for IBKR TWS/Gateway
- Add clearer IBKR status messages
- Add Developer Mode
- Add AI Execution Queue and Dry Run
- Keep Hedge Fund 7.0 logic
- Keep 6.0 Infrastructure endpoints

Important:
- Render cannot directly connect to TWS on your laptop.
- IBKR API requires backend on the same laptop/VPS as TWS or IB Gateway.
- Render can still serve dashboard and AI analysis.
- For real Paper execution, run this backend locally or on VPS.

New endpoints:
- /api/unified/status
- /api/unified/ibkr-panel
- /api/developer/status
- /api/execution/queue
- /api/execution/dry-run

IBKR local test:
1. Open TWS Paper.
2. Enable API socket on port 7497.
3. Run backend locally:
   pip install -r requirements.txt
   uvicorn server:app --host 127.0.0.1 --port 8000
4. Open:
   http://127.0.0.1:8000/api/infra/ibkr/status

Safety:
- Live remains locked.
- Paper-first remains active.
- Execution is locked by default.
- Dry-run queues ideas but does not send orders.
