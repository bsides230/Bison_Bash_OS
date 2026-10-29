@echo off
echo Starting Betting Station Kiosk (Port 8008)...
python -m uvicorn games.kiosk_server:app --host 0.0.0.0 --port 8008
pause
