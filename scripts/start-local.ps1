param()

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $workspace 'backend'
$frontend = Join-Path $workspace 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$vite = Join-Path $frontend 'node_modules\.bin\vite.cmd'
$logDirectory = Join-Path $workspace '.local-logs'

function Get-ListenerPid([int]$Port) {
    $pattern = "(?:127\.0\.0\.1|0\.0\.0\.0|\[::\]):$Port\s+.*LISTENING\s+(\d+)$"
    $line = netstat -ano | Select-String $pattern | Select-Object -First 1
    if (-not $line) { return $null }
    return [int](($line.Line.Trim() -split '\s+')[-1])
}

foreach ($required in @($python, $vite)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing local runtime dependency: $required"
    }
}

foreach ($port in @(8000, 5174)) {
    $listenerPid = Get-ListenerPid $port
    if ($listenerPid) {
        throw "Port $port is already used by process $listenerPid. Stop the old local service first."
    }
}

Push-Location $backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed; startup cancelled.' }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

# Some desktop shells expose both `Path` and `PATH`. Start-Process builds a
# case-insensitive environment map and fails on that duplicate, so normalize it
# before launching either child process.
$savedPath = $env:Path
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $savedPath, 'Process')

$backendProcess = Start-Process -FilePath $python `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') `
    -WorkingDirectory $backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDirectory 'backend.stdout.log') `
    -RedirectStandardError (Join-Path $logDirectory 'backend.stderr.log') `
    -PassThru

$frontendProcess = Start-Process -FilePath $vite `
    -WorkingDirectory $frontend `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDirectory 'frontend.stdout.log') `
    -RedirectStandardError (Join-Path $logDirectory 'frontend.stderr.log') `
    -PassThru

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:5174/health' -TimeoutSec 2
        if ($health.status -eq 'ok' -and $health.database -eq 'ok') {
            $ready = $true
            break
        }
    } catch {}
    Start-Sleep -Milliseconds 250
}

if (-not $ready) {
    foreach ($process in @($backendProcess, $frontendProcess)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    foreach ($port in @(8000, 5174)) {
        $listenerPid = Get-ListenerPid $port
        if ($listenerPid) {
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
    }
    throw "Local services failed to start. Check logs in $logDirectory."
}

@{
    backend = @{ port = 8000; pid = Get-ListenerPid 8000 }
    frontend = @{ port = 5174; pid = Get-ListenerPid 5174 }
} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $logDirectory 'processes.json')

Write-Output 'Local services started: http://localhost:5174'
Write-Output 'Database readiness: http://localhost:5174/health'
Write-Output "Logs: $logDirectory"
