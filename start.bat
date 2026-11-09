@echo off
REM ==========================================================================
REM  CM SURGICAL - Windows launcher
REM  Double-click this file to start the website.
REM  The site will open automatically in your browser at http://localhost:8000
REM ==========================================================================

title CM SURGICAL Website
cd /d "%~dp0"

echo.
echo   CM SURGICAL - starting the website...
echo   ----------------------------------------
echo.

REM --- 1. Find Python ---
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
  where py >nul 2>nul && set "PY=py"
)
if not defined PY (
  echo   ERROR: Python is not installed on this computer.
  echo.
  echo   Please install Python 3.9 or newer:
  echo     1. Go to https://www.python.org/downloads/
  echo     2. Download the latest version for Windows
  echo     3. IMPORTANT: tick "Add Python to PATH" during installation
  echo     4. Install it, then run this file again
  echo.
  pause
  exit /b 1
)

REM --- 2. Install anything missing ---
echo   Checking required packages (first run takes a minute)...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo   WARNING: could not install all packages automatically.
  echo   Try running:  pip install -r requirements.txt
  echo.
)

REM --- 3. Make sure the database is up to date ---
%PY% -c "import app; app.init_db()" >nul 2>&1

REM --- 4. Open the browser once the site is listening ---
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 4; Start-Process 'http://localhost:8000'"

echo.
echo   The website is starting.
echo   It will open in your browser automatically.
echo.
echo   LEAVE THIS WINDOW OPEN while you use the site.
echo   To close the site, click this window and press Ctrl + C.
echo.
echo   Admin panel: http://localhost:8000/admin
echo.
echo   ----------------------------------------
echo.

%PY% app.py

echo.
echo   The website has stopped.
pause