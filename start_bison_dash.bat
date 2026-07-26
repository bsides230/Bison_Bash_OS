@echo off
echo Starting Bison Dash...
python -m uvicorn game_hub.games.bison_dash.main:app --host 0.0.0.0 --port 8001
pause
