param([switch]$App, [switch]$Demo, [switch]$Monitoring)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & "$PSScriptRoot/setup.ps1"
    docker compose up -d --wait postgres redis redpanda minio
    if ($LASTEXITCODE -ne 0) { throw 'Infrastructure did not become healthy.' }
    if ($App -or $Demo) {
        docker compose build migrate
        if ($LASTEXITCODE -ne 0) { throw 'Backend build failed.' }
        docker compose run --rm migrate
        if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
        docker compose run --rm migrate bootstrap
        if ($LASTEXITCODE -ne 0) { throw 'Initial API key registration failed.' }
        $arguments = @('compose', '--profile', 'app')
        if ($Demo) { $arguments += @('--profile', 'demo') }
        if ($Monitoring) { $arguments += @('--profile', 'monitoring') }
        $arguments += @('up', '-d', '--build', '--wait', '--wait-timeout', '600')
        & docker @arguments
        if ($LASTEXITCODE -ne 0) { throw 'One or more services failed. Run docker compose logs.' }
        Write-Host 'Dashboard: http://localhost:3000  API: http://localhost:8000/docs'
    }
} finally { Pop-Location }
