@echo off
echo Starting Dummy Game...
python -m uvicorn games.dummy_game:app --host 0.0.0.0 --port 8002
pause
