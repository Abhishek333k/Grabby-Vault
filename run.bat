@echo off
setlocal
cd /d "%~dp0"

REM Prefer a single venv name: venv\ (fallback .venv\)
if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo No virtualenv found. Create one:
  echo   python -m venv venv
  echo   venv\Scripts\activate
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist "config.json" (
  if exist "config.example.json" (
    echo Creating config.json from config.example.json...
    copy /Y config.example.json config.json >nul
  )
)

python src\main.py
if errorlevel 1 pause
