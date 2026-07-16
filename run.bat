@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) else (
  echo No virtualenv found. Create one: python -m venv venv
  pause
  exit /b 1
)

python src\main.py
if errorlevel 1 pause
