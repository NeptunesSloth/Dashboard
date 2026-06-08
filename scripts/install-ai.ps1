# MayBot AI-agent installer for Windows — install Ollama + a model and register it
# as a sect member on the dashboard.
#
#   $env:CONTROL_URL='http://DASH:8200'; $env:CONTROL_TOKEN='<operator-token>'; `
#   irm http://DASH:8200/install-ai.ps1 | iex
#
# Env: MODEL (default nous-hermes), MEMBER_NAME, MEMBER_ROLE, CONTROL_URL, CONTROL_TOKEN.
$ErrorActionPreference = 'Stop'
$Model = if ($env:MODEL) { $env:MODEL } else { 'nous-hermes' }
$Name  = if ($env:MEMBER_NAME) { $env:MEMBER_NAME } else { $Model }
$Role  = if ($env:MEMBER_ROLE) { $env:MEMBER_ROLE } else { 'Disciple' }
$Port  = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { '11434' }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Installing Ollama..."
  $exe = "$env:TEMP\OllamaSetup.exe"
  Invoke-WebRequest -UseBasicParsing 'https://ollama.com/download/OllamaSetup.exe' -OutFile $exe
  Start-Process -FilePath $exe -ArgumentList '/silent' -Wait
  $env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
}
Write-Host "Pulling model '$Model' (this can take a while)..."
& ollama pull $Model

$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' } | Select-Object -First 1).IPAddress
if (-not $ip) { $ip = '127.0.0.1' }
$BaseUrl = "http://${ip}:$Port"

if ($env:CONTROL_URL -and $env:CONTROL_TOKEN) {
  Write-Host "Registering member '$Name' on $($env:CONTROL_URL)..."
  $body = @{ name=$Name; role=$Role; provider='ollama'; model=$Model; base_url=$BaseUrl } | ConvertTo-Json
  try {
    Invoke-RestMethod -Method Post -Uri "$($env:CONTROL_URL.TrimEnd('/'))/api/members" `
      -Headers @{ 'x-control-token' = $env:CONTROL_TOKEN } -ContentType 'application/json' -Body $body | Out-Null
    Write-Host "OK Member '$Name' is on the dashboard."
  } catch { Write-Host "Could not auto-register: $_. Add it in the UI with the base_url below." }
} else {
  Write-Host "OK Local AI ready. Add a member in the dashboard (Sect Members -> Add member):"
}
Write-Host "    provider: ollama   model: $Model   base_url: $BaseUrl"
