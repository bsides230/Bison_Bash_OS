@echo off
echo Starting Port Hop Plinko (Port 8006)...
python -m uvicorn games.plinko_server:app --host 0.0.0.0 --port 8006
pause
