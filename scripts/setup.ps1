# SDLC Orchestrator Setup Script
# Prepares the environment for Claude Code SDLC workflow

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== SDLC Orchestrator Setup ===" -ForegroundColor Cyan

# Check if Claude Code CLI is installed
Write-Host "`nChecking Claude Code CLI..." -ForegroundColor Yellow
$claudeCmd = Get-Command "claude" -ErrorAction SilentlyContinue
if (-not $claudeCmd) {
    Write-Host "Claude Code CLI not found!" -ForegroundColor Red
    Write-Host "Install it with: npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
    exit 1
}
Write-Host "Found: $($claudeCmd.Source)" -ForegroundColor Green

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
        description = "Registry of domain experts created by meta-expert"
        experts = @()
    } | ConvertTo-Json -Depth 3

    Set-Content -Path $registry -Value $registryContent -Encoding UTF8
    Write-Host "  Initialized: $registry" -ForegroundColor Green
}

# Verify .claude structure
Write-Host "`nVerifying .claude structure..." -ForegroundColor Yellow
$requiredFiles = @(
    ".claude/settings.json",
    ".claude/agents/meta-expert.md",
    ".claude/agents/build-agent.md",
    ".claude/agents/tester.md",
    ".claude/agents/reviewer.md",
    ".claude/commands/plan.md",
    ".claude/commands/build.md",
    ".claude/commands/test.md",
    ".claude/commands/review.md",
    ".claude/commands/meta.md"
)

$missing = @()
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  Found: $file" -ForegroundColor Green
    } else {
        Write-Host "  Missing: $file" -ForegroundColor Red
        $missing += $file
    }
}

if ($missing.Count -gt 0) {
    Write-Host "`nWarning: Some files are missing. The SDLC system may not work correctly." -ForegroundColor Yellow
}

# Summary
Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host @"

SDLC Commands Available:
  /plan   "description"  - Create implementation plan
  /build  path/to/spec   - Build from spec
  /test   [spec-path]    - Run tests
  /review [target]       - Code review
  /meta   "domain"       - Create new expert

Usage:
  claude               # Start interactive session
  claude "/plan Add user authentication"

The system will automatically create domain experts as it
encounters new technology stacks in your codebase.

"@ -ForegroundColor White
