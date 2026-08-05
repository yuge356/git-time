param(
    [switch]$Watch
)

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $workspace 'backend'
$frontend = Join-Path $workspace 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$backendLauncher = Join-Path $PSScriptRoot 'backend-local.cmd'
$vite = Join-Path $frontend 'node_modules\.bin\vite.cmd'
$logDirectory = Join-Path $workspace '.local-logs'
$stateFile = Join-Path $logDirectory 'processes.json'

function Get-ListenerPid([int]$Port) {
    $pattern = "(?:127\.0\.0\.1|0\.0\.0\.0|\[::\]):$Port\s+.*LISTENING\s+(\d+)$"
    $line = netstat -ano | Select-String $pattern | Select-Object -First 1
    if (-not $line) { return $null }
    return [int](($line.Line.Trim() -split '\s+')[-1])
}

function Test-BackendReady {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
        return $health.status -eq 'ok' -and $health.database -eq 'ok'
    } catch {
        return $false
    }
}

function Test-FrontendProxyReady {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:5174/health' -TimeoutSec 2
        return $health.status -eq 'ok' -and $health.database -eq 'ok'
    } catch {
        return $false
    }
}

function Wait-UntilReady([scriptblock]$Probe, [int]$Attempts = 40) {
    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        if (& $Probe) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

$previousState = $null
if (Test-Path -LiteralPath $stateFile) {
    try {
        $previousState = Get-Content -Raw -Encoding UTF8 -LiteralPath $stateFile | ConvertFrom-Json
    } catch {
        $previousState = $null
    }
}

function Test-PreviouslyManaged([string]$ServiceName, [int]$ProcessId) {
    if ($null -eq $previousState) { return $false }
    $service = $previousState.$ServiceName
    if ($null -eq $service -or [int]$service.pid -ne $ProcessId) { return $false }
    return $null -eq $service.managed -or [bool]$service.managed
}

foreach ($required in @($python, $backendLauncher, $vite)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing local runtime dependency: $required"
    }
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

Push-Location $backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed; startup cancelled.' }
} finally {
    Pop-Location
}

# Some desktop shells expose both `Path` and `PATH`. Start-Process builds a
# case-insensitive environment map and fails on that duplicate, so normalize it
# before launching either child process.
$savedPath = $env:Path
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $savedPath, 'Process')

$startedProcesses = @()
$backendManaged = $false
$frontendManaged = $false
$backendPid = Get-ListenerPid 8000
$frontendPid = Get-ListenerPid 5174

if ($backendPid) {
    if (-not (Test-BackendReady)) {
        throw "Port 8000 is used by process $backendPid, but it is not a healthy tracker backend."
    }
    $backendManaged = Test-PreviouslyManaged 'backend' $backendPid
    Write-Output "Reusing healthy backend process $backendPid on port 8000."
} else {
    $backendProcess = Start-Process -FilePath $backendLauncher `
        -WorkingDirectory $backend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDirectory 'backend.stdout.log') `
        -RedirectStandardError (Join-Path $logDirectory 'backend.stderr.log') `
        -PassThru
    $startedProcesses += $backendProcess
    $backendManaged = $true
}

if ($frontendPid) {
    $frontendManaged = Test-PreviouslyManaged 'frontend' $frontendPid
    Write-Output "Reusing process $frontendPid on port 5174 while its proxy is checked."
} else {
    $frontendProcess = Start-Process -FilePath $vite `
        -WorkingDirectory $frontend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDirectory 'frontend.stdout.log') `
        -RedirectStandardError (Join-Path $logDirectory 'frontend.stderr.log') `
        -PassThru
    $startedProcesses += $frontendProcess
    $frontendManaged = $true
}

$ready = $false
$ready = Wait-UntilReady { (Test-BackendReady) -and (Test-FrontendProxyReady) }

if (-not $ready) {
    foreach ($process in $startedProcesses) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    if ($backendManaged) {
        $listenerPid = Get-ListenerPid 8000
        if ($listenerPid) { Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue }
    }
    if ($frontendManaged) {
        $listenerPid = Get-ListenerPid 5174
        if ($listenerPid) { Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue }
    }
    throw "Local services failed readiness checks. Check logs in $logDirectory."
}

function Write-ProcessState {
    $script:backendPid = Get-ListenerPid 8000
    $script:frontendPid = Get-ListenerPid 5174
    @{
        backend = @{ port = 8000; pid = $script:backendPid; managed = $script:backendManaged }
        frontend = @{ port = 5174; pid = $script:frontendPid; managed = $script:frontendManaged }
    } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $stateFile
}

Write-ProcessState

Write-Output 'Local services are ready: http://localhost:5174'
Write-Output 'Database readiness: http://localhost:5174/health'
Write-Output "Logs: $logDirectory"

if (-not $Watch) {
    exit 0
}

Write-Output 'Local service monitor is running. Press Ctrl+C to stop managed services.'

$backendFailureCount = 0
$frontendFailureCount = 0

try {
    while ($true) {
        Start-Sleep -Seconds 2

        if (Test-BackendReady) {
            $backendFailureCount = 0
        } else {
            $backendFailureCount++
        }

        if ($backendFailureCount -ge 2) {
            $listenerPid = Get-ListenerPid 8000
            if ($listenerPid) {
                if (-not $backendManaged) {
                    throw "The reused process $listenerPid on port 8000 became unhealthy; stop it before restarting local development."
                }
                Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
            }

            Write-Warning 'Backend health check failed; restarting the local backend.'
            $backendProcess = Start-Process -FilePath $backendLauncher `
                -WorkingDirectory $backend `
                -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $logDirectory 'backend.stdout.log') `
                -RedirectStandardError (Join-Path $logDirectory 'backend.stderr.log') `
                -PassThru
            $backendManaged = $true

            if (-not (Wait-UntilReady { Test-BackendReady })) {
                Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
                throw "Backend restart failed. Check logs in $logDirectory."
            }

            $backendFailureCount = 0
            Write-ProcessState
            Write-Output "Backend recovered on port 8000 (process $backendPid)."
        }

        if (Test-FrontendProxyReady) {
            $frontendFailureCount = 0
        } elseif (Test-BackendReady) {
            $frontendFailureCount++
        }

        if ($frontendFailureCount -ge 3) {
            $listenerPid = Get-ListenerPid 5174
            if ($listenerPid) {
                if (-not $frontendManaged) {
                    throw "The reused process $listenerPid on port 5174 stopped proxying the backend; restart it with pnpm dev."
                }
                Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
            }

            Write-Warning 'Frontend health check failed; restarting the local frontend.'
            $frontendProcess = Start-Process -FilePath $vite `
                -WorkingDirectory $frontend `
                -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $logDirectory 'frontend.stdout.log') `
                -RedirectStandardError (Join-Path $logDirectory 'frontend.stderr.log') `
                -PassThru
            $frontendManaged = $true

            if (-not (Wait-UntilReady { Test-FrontendProxyReady })) {
                Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
                throw "Frontend restart failed. Check logs in $logDirectory."
            }

            $frontendFailureCount = 0
            Write-ProcessState
            Write-Output "Frontend recovered on port 5174 (process $frontendPid)."
        }
    }
} finally {
    foreach ($service in @(
        @{ port = 5174; pid = $frontendPid; managed = $frontendManaged },
        @{ port = 8000; pid = $backendPid; managed = $backendManaged }
    )) {
        $listenerPid = Get-ListenerPid ([int]$service.port)
        if ([bool]$service.managed -and $listenerPid -and $listenerPid -eq [int]$service.pid) {
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $stateFile -Force -ErrorAction SilentlyContinue
}
