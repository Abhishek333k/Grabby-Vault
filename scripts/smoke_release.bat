@echo off
setlocal
cd /d "%~dp0.."

echo === GrabbyVault smoke release check ===
echo.

if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else (
  set PY=python
)

echo [1] Python: %PY%
%PY% --version || exit /b 1

echo [2] Compile src...
%PY% -m compileall -q src || exit /b 1

echo [3] Unit tests...
%PY% -m unittest discover -s tests -p "test_*.py" -v || exit /b 1

echo [4] Import smoke...
%PY% -c "import sys; sys.path.insert(0,'src'); from core.paths import app_root, ffmpeg_path, bin_dir; from core.config_manager import ConfigManager; from core.formats import resolve_preset; from core.license_manager import LemonSqueezyClient, LS_ACTIVATE; from core.branding import brand_image_path, ensure_app_ico; print('root', app_root()); print('ffmpeg', ffmpeg_path() or 'MISSING'); print('brand', brand_image_path()); print('ico', ensure_app_ico()); print('preset', resolve_preset('1080')['id']); print('LS activate endpoint', LS_ACTIVATE)" || exit /b 1

echo [5] Config template...
if not exist "config.example.json" (
  echo FAIL: config.example.json missing
  exit /b 1
)

echo [6] ffmpeg...
if exist "bin\ffmpeg.exe" (
  echo OK bin\ffmpeg.exe
) else (
  echo WARN: bin\ffmpeg.exe missing — release will need it
)

echo [7] Assets...
if exist "assets\SILENVAULT CREST.png" (
  echo OK crest asset
) else if exist "assets\SILENVAULT_LOGO.png" (
  echo OK logo asset
) else (
  echo WARN: no brand PNG in assets\
)

echo.
echo === SMOKE PASSED (fix WARN lines before shipping) ===
exit /b 0
