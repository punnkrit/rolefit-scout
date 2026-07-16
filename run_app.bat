@echo off
title Career Search Coach Launcher
cd /d "%~dp0"

set "API_HOST=127.0.0.1"
set "API_PORT=8010"
set "UI_HOST=127.0.0.1"
set "UI_PORT=5173"
set "API_URL=http://%API_HOST%:%API_PORT%"
set "APP_URL=http://%UI_HOST%:%UI_PORT%"

set "API_RUNNER="
set "PYTHON="

where uv >nul 2>&1
if not errorlevel 1 (
  set "API_RUNNER=uv"
)

if "%API_RUNNER%"=="" if exist ".venv\Scripts\python.exe" (
  set "API_RUNNER=python"
  set "PYTHON=.venv\Scripts\python.exe"
)

if "%API_RUNNER%"=="" (
  where python >nul 2>&1
  if not errorlevel 1 (
    set "API_RUNNER=python"
    set "PYTHON=python"
  )
)

if "%API_RUNNER%"=="" (
  where py >nul 2>&1
  if not errorlevel 1 (
    set "API_RUNNER=python"
    set "PYTHON=py"
  )
)

where npm >nul 2>&1
if errorlevel 1 (
  echo Could not find npm.
  echo Install Node.js/npm, then run npm install in this project.
  echo.
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo Could not find node_modules.
  echo Run npm install in this project before starting the app.
  echo.
  pause
  exit /b 1
)

if "%API_RUNNER%"=="uv" (
  uv run --with-requirements requirements.txt python -m uvicorn --version >nul 2>&1
  if errorlevel 1 (
    echo Could not start uvicorn through uv.
    echo.
    echo Try running this once:
    echo uv run --with-requirements requirements.txt python -m uvicorn api:app --host 127.0.0.1 --port 8010
    echo.
    pause
    exit /b 1
  )
) else (
  if "%PYTHON%"=="" (
    echo Could not find Python.
    echo Install Python or uv, then try again.
    echo.
    pause
    exit /b 1
  )
  "%PYTHON%" -m uvicorn --version >nul 2>&1
  if errorlevel 1 (
    echo Could not start uvicorn with %PYTHON%.
    echo.
    echo Make sure Python dependencies are installed:
    echo %PYTHON% -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
  )
)

echo Starting Career Search Coach...
echo.
echo API:      %API_URL%
echo Frontend: %APP_URL%
echo.
echo Two server windows will open:
echo - Career Search API
echo - Career Search UI
echo.

if "%API_RUNNER%"=="uv" (
  start "Career Search API" cmd /k "uv run --with-requirements requirements.txt python -m uvicorn api:app --reload --host %API_HOST% --port %API_PORT%"
) else (
  start "Career Search API" cmd /k "%PYTHON% -m uvicorn api:app --reload --host %API_HOST% --port %API_PORT%"
)
start "Career Search UI" cmd /k "set VITE_API_BASE=%API_URL%&& set VITE_API_TARGET=%API_URL%&& npm run dev -- --host %UI_HOST% --port %UI_PORT%"

echo.
echo Waiting a few seconds before opening the app...
timeout /t 4 /nobreak >nul
start "" "%APP_URL%"

echo.
echo Launcher finished. Close the API and UI windows to stop the app.
