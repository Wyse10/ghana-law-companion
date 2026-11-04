param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\backups")
)

$ErrorActionPreference = "Stop"

$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $OutputDirectory "ghana-law-$timestamp.dump"
$checksumPath = "$backupPath.sha256"

& $env:ComSpec /c "docker compose exec -T postgres pg_dump -U ghana_law -d ghana_law --format=custom --no-owner --no-acl > `"$backupPath`""
if ($LASTEXITCODE -ne 0) {
    Remove-Item -Force -ErrorAction SilentlyContinue $backupPath
    throw "PostgreSQL backup failed."
}

if (-not (Test-Path $backupPath) -or (Get-Item $backupPath).Length -eq 0) {
    throw "PostgreSQL backup was empty."
}

$checksum = (Get-FileHash -Algorithm SHA256 -Path $backupPath).Hash.ToLowerInvariant()
"$checksum  $([System.IO.Path]::GetFileName($backupPath))" |
    Set-Content -Encoding ascii -Path $checksumPath

Write-Output "Backup: $backupPath"
Write-Output "SHA-256: $checksumPath"
