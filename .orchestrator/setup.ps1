# SDLC Orchestrator Setup
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SDLC Orchestrator Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check UV
Write-Host "[1/4] Checking UV package manager..." -ForegroundColor Cyan
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing UV..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    Write-Host "  UV installed successfully" -ForegroundColor Green
} else {
    Write-Host "  UV is installed" -ForegroundColor Green
}

# Step 2: Check Node.js/npm (required for Claude Code CLI)
Write-Host ""
Write-Host "[2/4] Checking Node.js/npm..." -ForegroundColor Cyan
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  Node.js/npm not found!" -ForegroundColor Red
    Write-Host "  Claude Code CLI requires Node.js to be installed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Please install Node.js from: https://nodejs.org/" -ForegroundColor White
    Write-Host "  Then re-run this setup script." -ForegroundColor White
    Write-Host ""
    exit 1
} else {
    $npmVersion = npm --version 2>$null
    Write-Host "  npm v$npmVersion is installed" -ForegroundColor Green
}

# Step 3: Check Claude Code CLI
Write-Host ""
Write-Host "[3/4] Checking Claude Code CLI..." -ForegroundColor Cyan
$claudeInstalled = $false
try {
    $claudeVersion = & claude --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $claudeInstalled = $true
        Write-Host "  Claude Code CLI $claudeVersion is installed" -ForegroundColor Green
    }
} catch {
    $claudeInstalled = $false
}

if (-not $claudeInstalled) {
    Write-Host "  Installing Claude Code CLI..." -ForegroundColor Yellow
    npm install -g @anthropic-ai/claude-code 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to install Claude Code CLI" -ForegroundColor Red
        Write-Host "  Try running manually: npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  Claude Code CLI installed successfully" -ForegroundColor Green
}

# Step 4: Sync Python dependencies and run setup
Write-Host ""
Write-Host "[4/4] Setting up Python environment..." -ForegroundColor Cyan
Push-Location $scriptDir
Write-Host "  Syncing dependencies..." -ForegroundColor White

# Temporarily allow errors for uv commands (they output to stderr even on success)
$ErrorActionPreference = "Continue"
$env:UV_NO_PROGRESS = "1"
uv sync --all-extras 2>$null
$syncExitCode = $LASTEXITCODE
if ($syncExitCode -ne 0) {
    Write-Host "  Warning: uv sync had issues, trying explicit install..." -ForegroundColor Yellow
    uv pip install fastapi uvicorn jinja2 2>$null
}
$ErrorActionPreference = "Stop"

Write-Host "  Running orchestrator setup..." -ForegroundColor White
uv run python cli.py setup
Pop-Location

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  You can now use the orchestrator:" -ForegroundColor White
Write-Host "    uv run python cli.py --help" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Note: Claude Code will prompt for authentication on first use." -ForegroundColor Gray
Write-Host ""
