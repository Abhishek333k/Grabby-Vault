@echo off
setlocal
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building GrabbyVault.exe (one-folder)...
pyinstaller --noconfirm --clean ^
  --name GrabbyVault ^
  --windowed ^
  --paths src ^
  --add-data "assets;assets" ^
  --hidden-import=yt_dlp ^
  --hidden-import=customtkinter ^
  --hidden-import=PIL ^
  --hidden-import=pystray ^
  --collect-all customtkinter ^
  --collect-all yt_dlp ^
  src\main.py

echo.
echo Staging release folder (sanitized config)...
if not exist "dist\GrabbyVault" mkdir "dist\GrabbyVault"
if exist "config.example.json" (
  copy /Y config.example.json "dist\GrabbyVault\config.json" >nul
) else (
  echo WARNING: config.example.json missing
)
if exist bin (
  xcopy /E /I /Y bin "dist\GrabbyVault\bin" >nul
)
if exist assets (
  xcopy /E /I /Y assets "dist\GrabbyVault\assets" >nul
)

echo.
echo Done: dist\GrabbyVault\GrabbyVault.exe
echo Ensure bin\ffmpeg.exe and ffprobe.exe are present for merges.
echo Release config has allow_dev_keys=false — use a real Lemon Squeezy key.
pause
