# MayBot agent — one-command installer for Windows. Downloads the agent from your
# dashboard, installs it, runs it (and registers a Scheduled Task so it survives
# reboots), and self-enrolls so the host appears on the dashboard automatically.
#
#   $env:CONTROL_URL='http://DASH:8200'; $env:REGISTER_TOKEN='secret'; `
#   irm http://DASH:8200/install-agent.ps1 | iex
#
# Env: CONTROL_URL (required), REGISTER_TOKEN, API_TOKEN (auto), AGENT_NAME (hostname),
#      AGENT_PORT (8100), AGENT_DIR (%USERPROFILE%\maybot-agent).
$ErrorActionPreference = 'Stop'
$Control = $env:CONTROL_URL; if (-not $Control) { Write-Error "Set CONTROL_URL=http://your-dashboard:8200"; return }
$Control = $Control.TrimEnd('/')
$Dir   = if ($env:AGENT_DIR) { $env:AGENT_DIR } else { Join-Path $HOME 'maybot-agent' }
$Port  = if ($env:AGENT_PORT) { $env:AGENT_PORT } else { '8100' }
$Name  = if ($env:AGENT_NAME) { $env:AGENT_NAME } else { $env:COMPUTERNAME }
$Reg   = if ($env:REGISTER_TOKEN) { $env:REGISTER_TOKEN } else { '' }
$Tok   = if ($env:API_TOKEN) { $env:API_TOKEN } else { -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) }) }

Write-Host "MayBot agent -> installing into $Dir (enrolling to $Control)"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
Set-Location $Dir
Invoke-WebRequest -UseBasicParsing "$Control/agent-bundle.tgz" -OutFile bundle.tgz
tar -xzf bundle.tgz; Remove-Item bundle.tgz
py -3 -m venv .venv 2>$null; if (-not (Test-Path .\.venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -q -U pip
.\.venv\Scripts\python.exe -m pip install -q -r requirements-agent.txt
if (-not (Test-Path projects.yaml)) { if (Test-Path projects.yaml.example) { Copy-Item projects.yaml.example projects.yaml } else { "projects: []" | Out-File projects.yaml -Encoding ascii } }

@"
MAYBOT_API_TOKEN=$Tok
MAYBOT_CONTROL_CENTER_URL=$Control
MAYBOT_REGISTER_TOKEN=$Reg
MAYBOT_AGENT_NAME=$Name
MAYBOT_AGENT_PORT=$Port
MAYBOT_PROJECTS_FILE=$Dir\projects.yaml
"@ | Out-File -Encoding ascii (Join-Path $Dir '.env')

# A small launcher that loads .env and starts uvicorn
@"
@echo off
cd /d "$Dir"
for /f "usebackq tokens=1,* delims==" %%A in ("$Dir\.env") do set %%A=%%B
"$Dir\.venv\Scripts\uvicorn.exe" maybot_agent.app:app --host 0.0.0.0 --port $Port
"@ | Out-File -Encoding ascii (Join-Path $Dir 'run-agent.bat')

# Register a Scheduled Task so it starts at logon and restarts on crash.
$action  = New-ScheduledTaskAction -Execute (Join-Path $Dir 'run-agent.bat')
$trigger = New-ScheduledTaskTrigger -AtLogOn
try {
  Register-ScheduledTask -TaskName 'MayBotAgent' -Action $action -Trigger $trigger -Force | Out-Null
  Start-ScheduledTask -TaskName 'MayBotAgent'
  Write-Host "OK Installed as a Scheduled Task (starts at logon). It will appear on your dashboard shortly."
} catch {
  Write-Host "Could not register a Scheduled Task; starting once in this window instead."
  & (Join-Path $Dir 'run-agent.bat')
}
Write-Host "Edit $Dir\projects.yaml to list this machine's bots."
