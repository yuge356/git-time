param(
    [string]$ProjectRef = 'cdaingelaivvffgpejjy',
    [string]$PoolerHost = 'aws-0-ap-southeast-1.pooler.supabase.com'
)

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backendDirectory = Join-Path $workspace 'backend'
$backendEnv = Join-Path $backendDirectory '.env'
$python = Join-Path $backendDirectory '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $backendEnv)) {
    throw 'backend/.env is missing. Copy backend/.env.example and configure the Supabase URL and publishable key first.'
}

if (-not (Test-Path -LiteralPath $python)) {
    throw 'backend/.venv is missing. Install the backend dependencies first.'
}

function Set-DotEnvValue {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Value
    )

    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        $lines.Add($line)
    }

    $prefix = "$Name="
    $replaced = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index].StartsWith($prefix, [System.StringComparison]::Ordinal)) {
            $lines[$index] = "$prefix$Value"
            $replaced = $true
            break
        }
    }

    if (-not $replaced) {
        $lines.Add("$prefix$Value")
    }

    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.UTF8Encoding]::new($false))
}

$securePassword = Read-Host 'Enter the Supabase database password (input is hidden)' -AsSecureString
$passwordPointer = [IntPtr]::Zero
$plainPassword = $null
$previousDatabaseUrl = $env:APP_DATABASE_URL
$previousDatabaseRole = $env:APP_DATABASE_ROLE

try {
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if ([string]::IsNullOrWhiteSpace($plainPassword)) {
        throw 'The database password cannot be empty.'
    }

    $encodedPassword = [uri]::EscapeDataString($plainPassword)
    $databaseUrl = "postgresql+asyncpg://postgres.${ProjectRef}:${encodedPassword}@${PoolerHost}:5432/postgres"

    # Validate with process-level variables before writing the local .env file.
    $env:APP_DATABASE_URL = $databaseUrl
    $env:APP_DATABASE_ROLE = 'dayflow_app'

    Push-Location $backendDirectory
    try {
        & $python -m alembic current
        if ($LASTEXITCODE -ne 0) {
            throw 'Supabase database validation failed. Check the password and try again.'
        }
    }
    finally {
        Pop-Location
    }

    Set-DotEnvValue -Path $backendEnv -Name 'APP_DATABASE_URL' -Value $databaseUrl
    Set-DotEnvValue -Path $backendEnv -Name 'APP_DATABASE_ROLE' -Value 'dayflow_app'
    Write-Output 'Supabase database validation succeeded and backend/.env was updated.'
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $plainPassword = $null
    $securePassword.Dispose()
    $env:APP_DATABASE_URL = $previousDatabaseUrl
    $env:APP_DATABASE_ROLE = $previousDatabaseRole
}
