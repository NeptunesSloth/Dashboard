@echo off
REM MayBot one-click updater for Windows — pull the latest code and restart.
REM Use this instead of deleting/replacing files by hand. Requires a git clone
REM (see the note below if this folder was downloaded as a ZIP).
setlocal
cd /d "%~dp0\.."

where docker >nul 2>&1
if errorlevel 1 ( echo Docker is not installed. Install Docker Desktop first. & pause & exit /b 1 )

if not exist ".git" (
  echo This folder is not a git clone, so it can't auto-update.
  echo One-time fix ^(do this once, then update.bat works forever^):
  echo   1^) Install "Git for Windows"
  echo   2^) In a folder you like:  git clone ^<your-repo-url^> maybot
  echo   3^) Run launch\maybot.bat from inside that "maybot" folder.
  pause
  exit /b 1
)

where git >nul 2>&1
if errorlevel 1 ( echo Git not found. Install "Git for Windows", then run this again. & pause & exit /b 1 )

echo Pulling the latest version...
git pull --ff-only
if errorlevel 1 (
  echo Update failed ^(local changes?^). Try:  git stash  then run update.bat again.
  pause
  exit /b 1
)

echo Rebuilding and restarting MayBot...
docker compose up -d --build
if errorlevel 1 ( echo Restart failed. Check: docker compose logs control-center & pause & exit /b 1 )

echo.
echo MayBot updated and restarted -^> http://localhost:8200
echo (No browser cache to clear — the service worker is network-first now.)
pause
endlocal
