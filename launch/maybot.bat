@echo off
REM MayBot one-click launcher (Docker) for Windows.
REM Starts the dashboard detached and opens it in your browser. Containers use
REM restart:unless-stopped, so once started they stay up across crashes and
REM reboots (while Docker Desktop runs) — normally you click this only once.
setlocal
cd /d "%~dp0\.."

set "URL=http://localhost:8200"

REM 1. Docker present and running?
where docker >nul 2>&1
if errorlevel 1 (
  echo MayBot: Docker is not installed. Install Docker Desktop, then click again.
  pause
  exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo MayBot: Docker isn't running. Start Docker Desktop and click again.
  pause
  exit /b 1
)

REM 2. First-run config: create .env from the template if missing.
if not exist ".env" if exist ".env.example" (
  copy /y ".env.example" ".env" >nul
  echo Created .env from .env.example — edit it later to add secrets.
)

REM 3. Bring the stack up (build first time / after updates).
echo Starting MayBot...
docker compose up -d --build
if errorlevel 1 (
  echo MayBot: failed to start. Try: docker compose logs control-center
  pause
  exit /b 1
)

REM 4. Wait for the dashboard to answer (up to ~60s), then open the browser.
echo Waiting for the dashboard to come online...
powershell -NoProfile -Command ^
  "for ($i=0; $i -lt 60; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%URL%/healthz').StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep 1 }; exit 1"
if errorlevel 1 (
  echo MayBot: started, but the dashboard didn't answer within 60s. Check: docker compose logs control-center
  pause
  exit /b 1
)

echo MayBot is up -^> %URL%
start "" "%URL%"
endlocal
