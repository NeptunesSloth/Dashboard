@echo off
REM Stop MayBot (one click). Click the MayBot launcher to start it again.
setlocal
cd /d "%~dp0\.."
where docker >nul 2>&1
if errorlevel 1 ( echo Docker not installed. & pause & exit /b 1 )
echo Stopping MayBot...
docker compose stop
echo Stopped.
pause
endlocal
