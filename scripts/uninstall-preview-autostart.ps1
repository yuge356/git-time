param()

$ErrorActionPreference = 'Stop'
$taskNames = @('DayFlow Preview', 'Time Budget Tracker Preview')
$stopScript = Join-Path $PSScriptRoot 'stop-local.ps1'
$removed = $false

foreach ($taskName in $taskNames) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Output "Removed auto-start task: $taskName"
        $removed = $true
    }
}

if (-not $removed) {
    Write-Output 'Local preview auto-start is not installed.'
}

if (Test-Path -LiteralPath $stopScript) {
    & $stopScript
}
