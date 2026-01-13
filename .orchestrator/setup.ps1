# SDLC Orchestrator Setup
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check UV
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing UV..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
}

# Sync all dependencies (including web extras for portal)
Push-Location $scriptDir
Write-Host "Syncing dependencies..." -ForegroundColor Cyan
uv sync --all-extras
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: uv sync failed, trying explicit install..." -ForegroundColor Yellow
    uv pip install fastapi uvicorn jinja2
}
uv run python cli.py setup
Pop-Location
