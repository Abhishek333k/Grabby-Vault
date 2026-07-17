@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo === GrabbyVault build ===
echo.

REM Prefer venv\ then .venv\
set "PY="
set "PIP="
if exist "%~dp0venv\Scripts\python.exe" (
  set "PY=%~dp0venv\Scripts\python.exe"
  set "PIP=%~dp0venv\Scripts\pip.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY=%~dp0.venv\Scripts\python.exe"
  set "PIP=%~dp0.venv\Scripts\pip.exe"
) else (
  echo ERROR: No venv found. Create one first:
  echo   python -m venv venv
  echo   venv\Scripts\activate
  echo   pip install -r requirements.txt
  goto FAIL
)

echo Using Python: %PY%
"%PY%" --version
if errorlevel 1 goto FAIL

echo.
echo [1/5] Installing dependencies...
"%PIP%" install -r requirements.txt
if errorlevel 1 goto FAIL
"%PIP%" install -U pyinstaller
if errorlevel 1 goto FAIL

echo.
echo [2/5] App icon...
"%PY%" -c "import sys; sys.path.insert(0,'src'); from core.branding import ensure_app_ico; p=ensure_app_ico(); print(p or 'no ico')"
if errorlevel 1 (
  echo WARN: icon generation failed, continuing without custom icon
)

echo.
echo [3/5] PyInstaller build...
if exist "assets\grabbyvault.ico" (
  "%PY%" -m PyInstaller --noconfirm --clean --name GrabbyVault --windowed --paths src --add-data "assets;assets" --icon "assets\grabbyvault.ico" --hidden-import=yt_dlp --hidden-import=customtkinter --hidden-import=PIL --hidden-import=pystray --collect-all customtkinter --collect-all yt_dlp src\main.py
) else (
  "%PY%" -m PyInstaller --noconfirm --clean --name GrabbyVault --windowed --paths src --add-data "assets;assets" --hidden-import=yt_dlp --hidden-import=customtkinter --hidden-import=PIL --hidden-import=pystray --collect-all customtkinter --collect-all yt_dlp src\main.py
)
if errorlevel 1 goto FAIL

echo.
echo [4/5] Staging release files into dist\GrabbyVault\...
if not exist "dist\GrabbyVault" (
  echo ERROR: PyInstaller did not create dist\GrabbyVault
  goto FAIL
)

if exist "config.example.json" (
  copy /Y "config.example.json" "dist\GrabbyVault\config.json" >nul
  echo OK config.json from example
) else (
  echo WARN: config.example.json missing
)

if exist "bin\ffmpeg.exe" (
  if not exist "dist\GrabbyVault\bin" mkdir "dist\GrabbyVault\bin"
  copy /Y "bin\ffmpeg.exe" "dist\GrabbyVault\bin\" >nul
  if exist "bin\ffprobe.exe" copy /Y "bin\ffprobe.exe" "dist\GrabbyVault\bin\" >nul
  echo OK ffmpeg copied
) else (
  echo WARN: bin\ffmpeg.exe missing - copy it before shipping
)

if exist "assets" (
  xcopy /E /I /Y "assets" "dist\GrabbyVault\assets" >nul
  echo OK assets copied
)

echo.
echo [5/5] Verify exe...
if exist "dist\GrabbyVault\GrabbyVault.exe" (
  echo OK: dist\GrabbyVault\GrabbyVault.exe
  dir "dist\GrabbyVault\GrabbyVault.exe"
) else (
  echo ERROR: GrabbyVault.exe not found after build
  goto FAIL
)

echo.
echo === BUILD OK ===
echo Folder: %~dp0dist\GrabbyVault\
goto END

:FAIL
echo.
echo === BUILD FAILED ===
set ERR=1

:END
echo.
pause
if defined ERR exit /b 1
exit /b 0
