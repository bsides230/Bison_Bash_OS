@echo off
echo Starting The Gauntlet (Port 8007)...
python -m uvicorn games.gauntlet_server:app --host 0.0.0.0 --port 8007
pause
