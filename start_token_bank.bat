@echo off
echo Starting Token Bank & Cashier Desk (Port 8005)...
python -m uvicorn games.token_bank_server:app --host 0.0.0.0 --port 8005
pause
