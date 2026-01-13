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
uv sync --all-extras --quiet 2>$null
uv run python cli.py setup
Pop-Location
