@echo off
echo Starting Master Admin...
python -m uvicorn master_admin.main:app --host 0.0.0.0 --port 8000
pause
