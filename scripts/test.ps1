param([switch]$Integration, [switch]$Load)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw 'Lint failed.' }
    python -m mypy backend sdk/python
    if ($LASTEXITCODE -ne 0) { throw 'Type check failed.' }
    python -m pytest -m unit -q
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
    if ($Integration) {
        python -m pytest -m integration -q
        if ($LASTEXITCODE -ne 0) { throw 'Integration tests failed.' }
    }
    if ($Load) {
        python -m pytest -m load -q
        if ($LASTEXITCODE -ne 0) { throw 'Load gates failed.' }
    }
    Push-Location dashboard
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed.' }
        npm run lint
        if ($LASTEXITCODE -ne 0) { throw 'Frontend types failed.' }
        npm test
        if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
} finally { Pop-Location }
