# SDLC Orchestrator Setup
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check UV
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing UV..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
}

# Sync and run setup
Push-Location $scriptDir
uv sync --quiet 2>$null
uv run python cli.py setup
Pop-Location
