@echo off
echo Starting GrabbyVault...
call .venv\Scripts\activate.bat
python -m playwright install chromium
python src\main.py
pause
