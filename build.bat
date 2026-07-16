@echo off
echo Installing dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m playwright install chromium
echo Done.
pause
