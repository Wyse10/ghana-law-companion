# Ghana Law Companion - Local Application Launcher
# Starts the FastAPI core engine and NestJS BFF with the modern web client.

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🏛️ GHANA LAW COMPANION - WEB APPLICATION LAUNCHER" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend on Port 8000
Write-Host "`n[1/2] Starting FastAPI Core Engine on http://127.0.0.1:8000..." -ForegroundColor Green
$env:VECTOR_STORE_BACKEND = "local"
$fastapiJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    uv run uvicorn src.api.main:app --host 127.0.0.1 --port 8000
} -ArgumentList $Root

# Wait for FastAPI
$fastApiReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health/live" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $fastApiReady = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 800
    }
}

if (-not $fastApiReady) {
    Receive-Job -Job $fastapiJob
    Stop-Job $fastapiJob
    Remove-Job $fastapiJob
    throw "FastAPI failed to start on port 8000."
}
Write-Host "  -> FastAPI is live and ready!" -ForegroundColor Green

# 2. Start NestJS BFF on Port 3000
Write-Host "`n[2/2] Starting NestJS BFF & Web Client on http://127.0.0.1:3000..." -ForegroundColor Green
$env:FASTAPI_URL = "http://127.0.0.1:8000"
$nestjsDir = Join-Path $Root "nestjs"

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  ✨ GHANA LAW COMPANION IS READY FOR INTERACTION!" -ForegroundColor Yellow
Write-Host "  Open your browser and navigate to:" -ForegroundColor White
Write-Host "  👉 http://localhost:3000" -ForegroundColor Green -NoNewline
Write-Host " (or http://127.0.0.1:3000)" -ForegroundColor Gray
Write-Host "  Press Ctrl+C in this terminal when finished to stop." -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

try {
    Set-Location $nestjsDir
    node dist/main.js
} finally {
    Write-Host "`nStopping FastAPI background process..." -ForegroundColor Yellow
    Stop-Job $fastapiJob -ErrorAction SilentlyContinue
    Remove-Job $fastapiJob -ErrorAction SilentlyContinue
    Set-Location $Root
    Write-Host "Services stopped cleanly." -ForegroundColor Green
}
