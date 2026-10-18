param([string]$Destination = 'backups')
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $dumpName = "tracelore-control-$stamp.dump"
    docker compose exec -T postgres pg_dump -U postgres -d tracelore -Fc --exclude-table=public.events* --file="/tmp/$dumpName"
    if ($LASTEXITCODE -ne 0) { throw 'Control-plane dump failed.' }
    $containerId = (docker compose ps -q postgres).Trim()
    docker cp "${containerId}:/tmp/$dumpName" (Join-Path $Destination $dumpName)
    if ($LASTEXITCODE -ne 0) { throw 'Dump transfer failed.' }
    docker compose exec -T postgres rm "/tmp/$dumpName"
    Get-FileHash -Algorithm SHA256 (Join-Path $Destination $dumpName)
    Write-Host 'Control-plane backup created. Hot events require a full/base backup plus WAL.'
} finally { Pop-Location }
