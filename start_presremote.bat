@echo off
title BBGN Standalone PresRemote Server (Port 8011)
echo Starting Standalone PresRemote Mobile PWA Server on port 8011...
python -m uvicorn games.presremote_server:app --host 0.0.0.0 --port 8011
pause
