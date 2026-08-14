param()

$ErrorActionPreference = 'Stop'
$taskName = 'DayFlow Preview'
$legacyTaskName = 'Time Budget Tracker Preview'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$launcher = Join-Path $PSScriptRoot 'start-local.ps1'
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Missing local preview launcher: $launcher"
}

$arguments = @(
    '-NoProfile'
    '-ExecutionPolicy Bypass'
    '-WindowStyle Hidden'
    "-File `"$launcher`""
    '-Watch'
) -join ' '

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument $arguments `
    -WorkingDirectory $workspace
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

$legacyTask = Get-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue
if ($legacyTask) {
    Stop-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $legacyTaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description 'Keep the DayFlow local preview available after Windows sign-in.' `
    -Force | Out-Null

Start-ScheduledTask -TaskName $taskName

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:5174/health' -TimeoutSec 2
        if ($health.status -eq 'ok' -and $health.database -eq 'ok') {
            $ready = $true
            break
        }
    } catch {
        # The monitor can still be applying migrations or starting the services.
    }
}

if (-not $ready) {
    throw "The auto-start task was installed, but the preview did not become healthy. Check $workspace\.local-logs."
}

Write-Output 'Local preview auto-start is installed and healthy.'
Write-Output 'Preview URL: http://localhost:5174'
