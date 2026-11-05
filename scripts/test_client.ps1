# Test the Modern Client and Backend End-to-End
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "Running Ghana Law Companion End-to-End Integration Tests..." -ForegroundColor Cyan
uv run python scripts/test_end_to_end.py
