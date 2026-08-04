param()

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$stateFile = Join-Path $workspace '.local-logs\processes.json'

function Get-ListenerPid([int]$Port) {
    $pattern = "(?:127\.0\.0\.1|0\.0\.0\.0|\[::\]):$Port\s+.*LISTENING\s+(\d+)$"
    $line = netstat -ano | Select-String $pattern | Select-Object -First 1
    if (-not $line) { return $null }
    return [int](($line.Line.Trim() -split '\s+')[-1])
}

if (-not (Test-Path -LiteralPath $stateFile)) {
    Write-Output 'No local services started by start-local.ps1 were found.'
    exit 0
}

$state = Get-Content -Raw -Encoding UTF8 -LiteralPath $stateFile | ConvertFrom-Json
foreach ($service in @($state.frontend, $state.backend)) {
    $listenerPid = Get-ListenerPid ([int]$service.port)
    if ($listenerPid -and $listenerPid -eq [int]$service.pid) {
        Stop-Process -Id $listenerPid -Force
        Write-Output "Stopped process $listenerPid on port $($service.port)."
    }
}

Remove-Item -LiteralPath $stateFile -Force
