@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
)

echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller
python -m playwright install chromium

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
echo Copying config template and bin if present...
if not exist "dist\GrabbyVault" mkdir "dist\GrabbyVault"
copy /Y config.json "dist\GrabbyVault\config.json" >nul 2>&1
if exist bin (
  xcopy /E /I /Y bin "dist\GrabbyVault\bin" >nul
)
if exist assets (
  xcopy /E /I /Y assets "dist\GrabbyVault\assets" >nul
)

echo.
echo Done. Run: dist\GrabbyVault\GrabbyVault.exe
echo Remember: place ffmpeg.exe + ffprobe.exe in dist\GrabbyVault\bin\
pause
