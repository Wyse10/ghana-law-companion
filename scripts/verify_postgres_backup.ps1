param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"

$BackupPath = [System.IO.Path]::GetFullPath($BackupPath)
if (-not (Test-Path $BackupPath -PathType Leaf)) {
    throw "Backup file does not exist: $BackupPath"
}

$checksumPath = "$BackupPath.sha256"
if (Test-Path $checksumPath -PathType Leaf) {
    $expected = ((Get-Content $checksumPath -Raw).Trim() -split "\s+")[0].ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 -Path $BackupPath).Hash.ToLowerInvariant()
    if ($expected -ne $actual) {
        throw "Backup checksum does not match."
    }
}

$restoreDatabase = "ghana_law_restore_verify"
try {
    & docker compose exec -T postgres psql -U ghana_law -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $restoreDatabase;"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not remove the previous verification database."
    }

    & docker compose exec -T postgres psql -U ghana_law -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $restoreDatabase;"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the verification database."
    }

    & $env:ComSpec /c "docker compose exec -T postgres pg_restore -U ghana_law -d $restoreDatabase --no-owner --no-acl < `"$BackupPath`""
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL restore failed."
    }

    $counts = & docker compose exec -T postgres psql -U ghana_law -d $restoreDatabase -tA -v ON_ERROR_STOP=1 -c "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM document_chunks);"
    $countText = ($counts -join "").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($countText)) {
        throw "Could not verify restored row counts."
    }

    Write-Output "Restore verification succeeded: $countText"
}
finally {
    & docker compose exec -T postgres psql -U ghana_law -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $restoreDatabase;" | Out-Null
}
