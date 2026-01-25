# SDLC Orchestrator Setup
# One-time setup that installs 'orch' as a global command
#
# Prerequisites:
#   - Create .env file with database credentials before running
#
# Usage:
#   .\setup.ps1

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
Write-Host "    - Load database config from .env (must exist)" -ForegroundColor Gray
Write-Host "    - Install 'orch' command globally" -ForegroundColor Gray
Write-Host "    - Initialize the orchestrator database" -ForegroundColor Gray
Write-Host "    - Migrate agents/experts/config to database" -ForegroundColor Gray
Write-Host "    - Register this project as 'self'" -ForegroundColor Gray
Write-Host ""

# ============================================
# Step 1: Check Prerequisites
# ============================================

Write-Step "1/5" "Checking prerequisites..."

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

# Check Python (try py launcher first on Windows, then python)
$pythonCmd = $null
$pythonVersion = $null

# Try py launcher first (more reliable on Windows)
try {
    $testVer = & py --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $testVer -match "Python") {
        $pythonCmd = "py"
        $pythonVersion = $testVer
    }
} catch {}

# Fallback to python command
if (-not $pythonCmd) {
    try {
        $testVer = & python --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $testVer -match "Python") {
            $pythonCmd = "python"
            $pythonVersion = $testVer
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Fail "Python not found!"
    Write-Info "Please install Python 3.11+ from: https://python.org/"
    exit 1
} else {
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
# Step 2: Load Configuration from .env
# ============================================

Write-Step "2/5" "Loading configuration..."

$envFile = Join-Path $scriptDir ".env"

if (-not (Test-Path $envFile)) {
    Write-Fail ".env file not found!"
    Write-Host ""
    Write-Host "  Please create a .env file at: $envFile" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Example .env content:" -ForegroundColor Gray
    Write-Host "    ORCH_DB_HOST=localhost" -ForegroundColor Gray
    Write-Host "    ORCH_DB_PORT=5432" -ForegroundColor Gray
    Write-Host "    ORCH_DB_NAME=orchestrator" -ForegroundColor Gray
    Write-Host "    ORCH_DB_USER=postgres" -ForegroundColor Gray
    Write-Host "    ORCH_DB_PASSWORD=your_password" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

# Parse .env file
$envVars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        $envVars[$key] = $value
    }
}

# Load values from .env (with defaults as fallback)
$dbHost = if ($envVars['ORCH_DB_HOST']) { $envVars['ORCH_DB_HOST'] } else { $defaultDbHost }
$dbPort = if ($envVars['ORCH_DB_PORT']) { $envVars['ORCH_DB_PORT'] } else { $defaultDbPort }
$dbName = if ($envVars['ORCH_DB_NAME']) { $envVars['ORCH_DB_NAME'] } else { $defaultDbName }
$dbUser = if ($envVars['ORCH_DB_USER']) { $envVars['ORCH_DB_USER'] } else { $defaultDbUser }
$dbPassword = if ($envVars['ORCH_DB_PASSWORD']) { $envVars['ORCH_DB_PASSWORD'] } else { "" }

Write-Success "Loaded .env from: $envFile"
Write-Info "Database: $dbUser@$dbHost`:$dbPort/$dbName"

# Set env vars for current session (so orch init works)
$env:ORCH_DB_HOST = $dbHost
$env:ORCH_DB_PORT = $dbPort
$env:ORCH_DB_NAME = $dbName
$env:ORCH_DB_USER = $dbUser
$env:ORCH_DB_PASSWORD = $dbPassword

# Set SDLC_ORCHESTRATOR_HOME permanently so orch works from any directory
$env:SDLC_ORCHESTRATOR_HOME = $scriptDir
[System.Environment]::SetEnvironmentVariable("SDLC_ORCHESTRATOR_HOME", $scriptDir, "User")
Write-Success "Set SDLC_ORCHESTRATOR_HOME=$scriptDir"

# ============================================
# Step 3: Install Orchestrator Package
# ============================================

Write-Step "3/5" "Installing orchestrator package..."

Push-Location $scriptDir

# Temporarily allow non-terminating errors for external commands
$ErrorActionPreference = "SilentlyContinue"

# Fix pyproject.toml if py-modules is missing (required for cli to be importable)
$pyprojectFile = Join-Path $scriptDir "pyproject.toml"
if (Test-Path $pyprojectFile) {
    $pyprojectContent = Get-Content $pyprojectFile -Raw
    if ($pyprojectContent -notmatch 'py-modules\s*=') {
        Write-Info "Fixing pyproject.toml configuration..."
        # Add py-modules before [tool.setuptools.packages.find]
        $pyprojectContent = $pyprojectContent -replace '(\[tool\.setuptools\.packages\.find\])', @"
[tool.setuptools]
py-modules = ["cli", "commands", "config"]

`$1
"@
        $pyprojectContent | Set-Content $pyprojectFile -NoNewline
        Write-Success "Fixed pyproject.toml"
    }
}

# Sync dependencies with uv
Write-Info "Syncing Python dependencies..."
$env:UV_NO_PROGRESS = "1"
$null = uv sync --all-extras 2>&1

# Uninstall existing installation first (clean slate)
Write-Info "Removing any existing installation..."
$null = pip uninstall sdlc-orchestrator -y 2>&1

# Clean install with force-reinstall to ensure everything is fresh
Write-Info "Installing package..."
$installOutput = pip install -e . --force-reinstall 2>&1
$installSuccess = $LASTEXITCODE -eq 0

if ($installSuccess) {
    Write-Success "'orch' command installed"
} else {
    Write-Warn "pip install had issues, trying uv..."
    $null = uv pip install -e . 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "'orch' command installed via uv"
        $installSuccess = $true
    } else {
        Write-Fail "Package installation failed"
        Write-Info "You can still use: uv run python cli.py"
    }
}

# Install portal dependencies globally (required when orch is installed via pip)
Write-Info "Installing portal dependencies..."
$portalDeps = @(
    "fastapi",
    "uvicorn",
    "jinja2",
    "asyncpg",
    "sqlalchemy",
    "aiofiles",
    "python-multipart",
    "blinker",
    "websockets"
)
$pipCmd = if ($pythonCmd -eq "py") { "py -m pip" } else { "python -m pip" }
$null = Invoke-Expression "$pipCmd install $($portalDeps -join ' ') --quiet" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "Portal dependencies installed"
} else {
    Write-Warn "Some portal dependencies may be missing"
}

# Verify installation works
if ($installSuccess) {
    Write-Info "Verifying installation..."
    $verifyOutput = orch --help 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Installation verified - 'orch' command works"
    } else {
        Write-Warn "Installation may have issues: $verifyOutput"
    }
}

# Restore error preference
$ErrorActionPreference = "Stop"

Pop-Location

# ============================================
# Step 5: Create Directory Structure & Init DB
# ============================================

Write-Step "4/5" "Creating directory structure..."

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

# Migrate agents, experts, and config from files to database
Write-Info "Migrating agents/experts/config to database..."
try {
    if ($orchExe) {
        & $orchExe migrate-to-db 2>&1
    } else {
        uv run python cli.py migrate-to-db 2>&1
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Migration completed"
    } else {
        Write-Warn "Migration returned non-zero exit code"
    }
} catch {
    Write-Warn "Could not run migration: $_"
    Write-Info "You can run manually later: orch migrate-to-db"
}

Pop-Location

# ============================================
# Step 6: Register "self" project
# ============================================

Write-Step "5/5" "Registering 'self' project..."

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
