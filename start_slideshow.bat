@echo off
title BBGN Stadium Slideshow & Presenter Server (Port 8010)
echo Starting Stadium Slideshow & Presenter Server (DJ Mac) on port 8010...
python -m uvicorn games.slideshow_server:app --host 0.0.0.0 --port 8010
pause
