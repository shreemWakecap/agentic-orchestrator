# SDLC Orchestrator Setup
# One-time setup that installs 'orch' as a global command
#
# Usage:
#   .\setup.ps1                              # Just asks for DB password, uses all defaults
#   .\setup.ps1 -DbPassword "mypass"         # Fully automated, no prompts
#
# Custom settings (optional):
#   .\setup.ps1 -DbHost "myserver" -DbPort "5433" -DbName "mydb" -DbUser "myuser"

param(
    [string]$DbHost,
    [string]$DbPort,
    [string]$DbName,
    [string]$DbUser,
    [string]$DbPassword
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$parentDir = Split-Path $scriptDir -Parent

# Default values
$defaultDbHost = "localhost"
$defaultDbPort = "5432"
$defaultDbName = "orchestrator"
$defaultDbUser = "postgres"

# ============================================
# Helper Functions
# ============================================

function Write-Step {
    param([string]$Step, [string]$Message)
    Write-Host ""
    Write-Host "[$Step] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [!] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [X] $Message" -ForegroundColor Red
}

# ============================================
# Banner
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SDLC Orchestrator Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  This setup will:" -ForegroundColor White
Write-Host "    - Install required tools (UV, Node.js, Claude CLI)" -ForegroundColor Gray
Write-Host "    - Configure database connection" -ForegroundColor Gray
Write-Host "    - Install 'orch' command globally" -ForegroundColor Gray
Write-Host "    - Initialize the orchestrator database" -ForegroundColor Gray
Write-Host "    - Register this project as 'self'" -ForegroundColor Gray
Write-Host ""

# ============================================
# Step 1: Check Prerequisites
# ============================================

Write-Step "1/6" "Checking prerequisites..."

# Check UV
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Info "Installing UV package manager..."
    irm https://astral.sh/uv/install.ps1 | iex
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Success "UV installed"
} else {
    Write-Success "UV is installed"
}

# Check Python
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Fail "Python not found!"
    Write-Info "Please install Python 3.11+ from: https://python.org/"
    exit 1
} else {
    $pythonVersion = python --version 2>&1
    Write-Success "Python: $pythonVersion"
}

# Check pip
if (-not (Get-Command "pip" -ErrorAction SilentlyContinue)) {
    Write-Warn "pip not found, will use uv for installation"
    $usePip = $false
} else {
    Write-Success "pip is available"
    $usePip = $true
}

# Check Node.js/npm
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Fail "Node.js/npm not found!"
    Write-Info "Claude Code CLI requires Node.js."
    Write-Info "Please install from: https://nodejs.org/"
    exit 1
} else {
    $npmVersion = npm --version 2>$null
    Write-Success "npm v$npmVersion"
}

# Check Claude Code CLI
$claudeInstalled = $false
try {
    $claudeVersion = & claude --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $claudeInstalled = $true
        Write-Success "Claude CLI: $claudeVersion"
    }
} catch {
    $claudeInstalled = $false
}

if (-not $claudeInstalled) {
    Write-Info "Installing Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to install Claude Code CLI"
        Write-Info "Try manually: npm install -g @anthropic-ai/claude-code"
        exit 1
    }
    Write-Success "Claude CLI installed"
}

# ============================================
# Step 2: Configuration
# ============================================

Write-Step "2/6" "Configuration"

# Use defaults for everything - only override if explicitly provided
$dbHost = if ($DbHost) { $DbHost } else { $defaultDbHost }
$dbPort = if ($DbPort) { $DbPort } else { $defaultDbPort }
$dbName = if ($DbName) { $DbName } else { $defaultDbName }
$dbUser = if ($DbUser) { $DbUser } else { $defaultDbUser }

Write-Info "Database: $dbUser@$dbHost`:$dbPort/$dbName"

# Only ask for password if not provided
if ([string]::IsNullOrWhiteSpace($DbPassword)) {
    Write-Host ""
    $dbPassword = Read-Host "  Enter database password for '$dbUser'"
    if ([string]::IsNullOrWhiteSpace($dbPassword)) {
        Write-Warn "No password provided - using empty password"
        $dbPassword = ""
    }
} else {
    $dbPassword = $DbPassword
}

# ============================================
# Step 3: Create .env Configuration File
# ============================================

Write-Step "3/6" "Creating configuration..."

# Create .env file in .orchestrator directory (not external home)
$envFile = Join-Path $scriptDir ".env"
$envExampleFile = Join-Path $scriptDir ".env.example"

# Build DATABASE_URL
$databaseUrl = "postgresql+asyncpg://${dbUser}:${dbPassword}@${dbHost}:${dbPort}/${dbName}"

if (Test-Path $envExampleFile) {
    # Read the example file and replace values
    $envContent = Get-Content $envExampleFile -Raw

    # Replace database settings
    $envContent = $envContent -replace 'DATABASE_URL=.*', "DATABASE_URL=$databaseUrl"
    $envContent = $envContent -replace 'ORCH_DB_HOST=.*', "ORCH_DB_HOST=$dbHost"
    $envContent = $envContent -replace 'ORCH_DB_PORT=.*', "ORCH_DB_PORT=$dbPort"
    $envContent = $envContent -replace 'ORCH_DB_NAME=.*', "ORCH_DB_NAME=$dbName"
    $envContent = $envContent -replace 'ORCH_DB_USER=.*', "ORCH_DB_USER=$dbUser"
    $envContent = $envContent -replace 'ORCH_DB_PASSWORD=.*', "ORCH_DB_PASSWORD=$dbPassword"

    # Write the .env file
    $envContent | Set-Content $envFile -NoNewline
    Write-Success "Created .env file with database settings"
} else {
    # Create minimal .env file
    $envContent = @"
# SDLC Orchestrator Configuration
# Generated by setup.ps1

# Database Configuration
DATABASE_URL=$databaseUrl
ORCH_DB_HOST=$dbHost
ORCH_DB_PORT=$dbPort
ORCH_DB_NAME=$dbName
ORCH_DB_USER=$dbUser
ORCH_DB_PASSWORD=$dbPassword

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
"@
    $envContent | Set-Content $envFile
    Write-Success "Created .env file"
}

Write-Info "Config file: $envFile"

# Also set env vars for current session (so orch init works)
$env:ORCH_DB_HOST = $dbHost
$env:ORCH_DB_PORT = $dbPort
$env:ORCH_DB_NAME = $dbName
$env:ORCH_DB_USER = $dbUser
$env:ORCH_DB_PASSWORD = $dbPassword

# ============================================
# Step 4: Install Orchestrator Package
# ============================================

Write-Step "4/6" "Installing orchestrator package..."

Push-Location $scriptDir

# First, sync dependencies with uv
Write-Info "Syncing Python dependencies..."
$ErrorActionPreference = "Continue"
$env:UV_NO_PROGRESS = "1"
uv sync --all-extras 2>$null
$ErrorActionPreference = "Stop"

# Install the package so 'orch' command is available
if ($usePip) {
    Write-Info "Installing with pip..."
    pip install -e . --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "'orch' command installed via pip"
    } else {
        Write-Warn "pip install had issues, trying uv..."
        uv pip install -e . 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "'orch' command installed via uv"
        } else {
            Write-Fail "Package installation failed"
            Write-Info "You can still use: uv run python cli.py"
        }
    }
} else {
    Write-Info "Installing with uv pip..."
    uv pip install -e . 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "'orch' command installed via uv"
    } else {
        Write-Fail "Package installation failed"
        Write-Info "You can still use: uv run python cli.py"
    }
}

Pop-Location

# ============================================
# Step 5: Create Directory Structure & Init DB
# ============================================

Write-Step "5/6" "Creating directory structure..."

# Create directories inside .orchestrator
$projectsDir = Join-Path $scriptDir "projects"
$configDir = Join-Path $scriptDir "config"
$logsDir = Join-Path $scriptDir "logs"

if (-not (Test-Path $projectsDir)) {
    New-Item -ItemType Directory -Path $projectsDir -Force | Out-Null
    Write-Success "Created: $projectsDir"
} else {
    Write-Info "Exists: $projectsDir"
}

if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    Write-Success "Created: $configDir"
} else {
    Write-Info "Exists: $configDir"
}

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Success "Created: $logsDir"
} else {
    Write-Info "Exists: $logsDir"
}

# Initialize database
Write-Info "Initializing database..."

Push-Location $scriptDir

# Try to find the orch command
$orchExe = $null
$possiblePaths = @(
    (Join-Path $scriptDir ".venv\Scripts\orch.exe"),
    (Join-Path $env:USERPROFILE ".local\bin\orch.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\Scripts\orch.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\Scripts\orch.exe")
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $orchExe = $path
        break
    }
}

# Also check if orch is in PATH
if (-not $orchExe) {
    try {
        $orchCmd = Get-Command "orch" -ErrorAction SilentlyContinue
        if ($orchCmd) {
            $orchExe = $orchCmd.Source
        }
    } catch {}
}

if ($orchExe) {
    Write-Info "Found orch at: $orchExe"
    try {
        & $orchExe init 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Orchestrator initialized"
        } else {
            Write-Warn "Initialization returned non-zero exit code"
        }
    } catch {
        Write-Warn "Could not run orch init: $_"
        Write-Info "Trying fallback method..."
        uv run python cli.py init 2>&1
    }
} else {
    Write-Info "Running initialization via uv..."
    uv run python cli.py init 2>&1
}

Pop-Location

# ============================================
# Step 6: Register "self" project
# ============================================

Write-Step "6/6" "Registering 'self' project..."

Push-Location $scriptDir

# Check if "self" project already exists
$selfExists = $false
try {
    if ($orchExe) {
        $projectList = & $orchExe project list 2>&1
    } else {
        $projectList = uv run python cli.py project list 2>&1
    }
    if ($projectList -match "self") {
        $selfExists = $true
    }
} catch {}

if ($selfExists) {
    Write-Info "'self' project already registered"
} else {
    # Register parent directory as "self" project
    Write-Info "Registering $parentDir as 'self' project..."
    try {
        if ($orchExe) {
            & $orchExe project add $parentDir --name "self" 2>&1
        } else {
            uv run python cli.py project add $parentDir --name "self" 2>&1
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Success "'self' project registered"

            # Set it as active
            if ($orchExe) {
                & $orchExe project switch self 2>&1 | Out-Null
            } else {
                uv run python cli.py project switch self 2>&1 | Out-Null
            }
            Write-Success "'self' project set as active"
        } else {
            Write-Warn "Could not register 'self' project"
        }
    } catch {
        Write-Warn "Could not register 'self' project: $_"
    }
}

Pop-Location

# ============================================
# Complete!
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Restart your terminal, then use:" -ForegroundColor White
Write-Host "    orch --help" -ForegroundColor Cyan
Write-Host "    orch project list" -ForegroundColor Cyan
Write-Host "    orch portal" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Configuration:" -ForegroundColor White
Write-Host "    Config file: $envFile" -ForegroundColor Gray
Write-Host "    Database: $dbUser@$dbHost`:$dbPort/$dbName" -ForegroundColor Gray
Write-Host ""
Write-Host "  The 'self' project (this directory) is registered and active." -ForegroundColor Gray
Write-Host "  Add more projects with: orch project add /path/to/project" -ForegroundColor Gray
Write-Host ""
Write-Host "  Note: Claude Code will prompt for" -ForegroundColor Gray
Write-Host "  authentication on first use." -ForegroundColor Gray
Write-Host ""
