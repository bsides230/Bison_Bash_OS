@echo off
echo Starting N64 Tournament Station (Port 8004)...
python -m uvicorn games.n64_server:app --host 0.0.0.0 --port 8004
pause
