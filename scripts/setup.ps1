$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    python scripts/setup.py
    if ($LASTEXITCODE -ne 0) { throw 'Environment setup failed. Install Python 3.11 or later.' }
    Write-Host 'Configuration is ready. Credentials are in .env; keep it private.'
} finally { Pop-Location }
