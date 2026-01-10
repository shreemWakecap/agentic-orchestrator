# SDLC Orchestrator Setup Script
# Prepares the environment for SDLC workflows

$ErrorActionPreference = "Stop"

Write-Host "`n=== SDLC Orchestrator Setup ===" -ForegroundColor Cyan

# Check for Claude Code CLI
Write-Host "`nChecking Claude Code CLI..." -ForegroundColor Yellow
$claudeCmd = Get-Command "claude" -ErrorAction SilentlyContinue
if (-not $claudeCmd) {
    Write-Host "Claude Code CLI not found!" -ForegroundColor Red
    Write-Host "Install with: npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Found: claude" -ForegroundColor Green

# Check for UV (Python package manager)
Write-Host "`nChecking UV..." -ForegroundColor Yellow
$uvCmd = Get-Command "uv" -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Host "UV not found! Installing..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
}
Write-Host "  UV ready" -ForegroundColor Green

# Install orchestrator dependencies
Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
Push-Location ".orchestrator"
try {
    uv pip install rich --quiet 2>$null
    Write-Host "  Dependencies installed (rich)" -ForegroundColor Green
} catch {
    Write-Host "  Warning: Could not install dependencies" -ForegroundColor Yellow
}
finally {
    Pop-Location
}

# Create required directories
Write-Host "`nCreating directories..." -ForegroundColor Yellow
$dirs = @(".specs", ".orchestrator/experts")

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "  Exists:  $dir" -ForegroundColor Gray
    }
}

# Summary
Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host @"

Run the planning workflow:
  uv run python scripts/plan.py "Add user authentication"

Output saved to: .specs/

No API keys needed - uses Claude Code CLI directly.

"@ -ForegroundColor White
