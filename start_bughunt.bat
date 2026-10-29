@echo off
echo Starting Bug Bounty: Alpha Critical (Port 8003)...
python -m uvicorn games.bughunt_server:app --host 0.0.0.0 --port 8003
pause
