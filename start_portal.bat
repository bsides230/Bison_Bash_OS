@echo off
echo Starting Mobile Player Portal (Port 8009)...
python -m uvicorn games.portal_server:app --host 0.0.0.0 --port 8009
pause
