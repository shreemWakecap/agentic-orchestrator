# SDLC Orchestrator Setup Script
# Prepares the environment for SDLC workflows

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== SDLC Orchestrator Setup ===" -ForegroundColor Cyan

# Check for UV (Python package manager)
Write-Host "`nChecking UV..." -ForegroundColor Yellow
$uvCmd = Get-Command "uv" -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Host "UV not found! Installing..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
}
Write-Host "UV ready" -ForegroundColor Green

# Install orchestrator dependencies
Write-Host "`nInstalling orchestrator dependencies..." -ForegroundColor Yellow
Push-Location ".orchestrator"
try {
    uv sync 2>$null
    if ($LASTEXITCODE -ne 0) {
        uv pip install anthropic python-dotenv rich
    }
    Write-Host "  Dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# Check for .env file
Write-Host "`nChecking environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.sample") {
        Copy-Item ".env.sample" ".env"
        Write-Host "  Created .env from .env.sample" -ForegroundColor Yellow
        Write-Host "  IMPORTANT: Add your ANTHROPIC_API_KEY to .env" -ForegroundColor Red
    } else {
        Write-Host "  Warning: No .env file found. Create one with ANTHROPIC_API_KEY" -ForegroundColor Yellow
    }
} else {
    Write-Host "  .env exists" -ForegroundColor Green
}

# Create required directories
Write-Host "`nCreating directories..." -ForegroundColor Yellow
$dirs = @(
    ".orchestrator/experts",
    ".specs"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "  Exists:  $dir" -ForegroundColor Gray
    }
}

# Initialize registry if not exists
$registry = ".orchestrator/registry.json"
if (-not (Test-Path $registry) -or $Force) {
    $registryContent = @{
        version = "1.0"
        description = "Registry of domain experts"
        experts = @()
    } | ConvertTo-Json -Depth 3

    Set-Content -Path $registry -Value $registryContent -Encoding UTF8
    Write-Host "  Initialized: $registry" -ForegroundColor Green
}

# Summary
Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host @"

SDLC Workflows:

  Standalone Scripts (run from project root):
    uv run python scripts/plan.py "Add user authentication"

  Or use Claude Code directly:
    claude "/plan Add user authentication"

Workflow Output:
  Plans are saved to .specs/

Next Steps:
  1. Ensure ANTHROPIC_API_KEY is set in .env
  2. Run: uv run python scripts/plan.py "Your feature request"

"@ -ForegroundColor White
