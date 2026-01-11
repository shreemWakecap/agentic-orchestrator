# SDLC Orchestrator Setup Script
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check for UV
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing UV..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
}

# Sync and run
Push-Location $scriptDir
uv sync --quiet 2>$null
uv run python init_setup.py
Pop-Location
