@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo === GrabbyVault smoke release check ===
echo.

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" if not exist "venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo [1] Python: %PY%
"%PY%" --version
if errorlevel 1 goto FAIL

echo [2] Compile src...
"%PY%" -m compileall -q src
if errorlevel 1 goto FAIL

echo [3] Unit tests...
"%PY%" -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 goto FAIL

echo [4] Import smoke...
"%PY%" -c "import sys; sys.path.insert(0,'src'); from core.paths import app_root, ffmpeg_path; from core.formats import resolve_preset; from core.license_manager import LS_ACTIVATE; from core.branding import brand_image_path, ensure_app_ico; print('root', app_root()); print('ffmpeg', ffmpeg_path() or 'MISSING'); print('brand', brand_image_path()); print('ico', ensure_app_ico()); print('preset', resolve_preset('1080')['id']); print('LS', LS_ACTIVATE)"
if errorlevel 1 goto FAIL

echo [5] Config template...
if not exist "config.example.json" (
  echo FAIL: config.example.json missing
  goto FAIL
)
echo OK config.example.json

echo [6] ffmpeg...
if exist "bin\ffmpeg.exe" (
  echo OK bin\ffmpeg.exe
) else (
  echo WARN: bin\ffmpeg.exe missing - add before shipping
)

echo [7] Assets...
if exist "assets\SILENVAULT CREST.png" (
  echo OK crest asset
) else if exist "assets\SILENVAULT_LOGO.png" (
  echo OK logo asset
) else (
  echo WARN: no brand PNG in assets
)

echo.
echo === SMOKE PASSED ===
goto END

:FAIL
echo.
echo === SMOKE FAILED ===
set ERR=1

:END
echo.
pause
if defined ERR exit /b 1
exit /b 0