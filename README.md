# SDLC Orchestrator

AI-powered software development lifecycle automation using Claude Code.

## Quick Start

```bash
# Setup (one time)
.\.orchestrator\setup.ps1

# Navigate to orchestrator directory
cd .orchestrator

# Run commands
uv run cli.py <command>
```

## Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `setup` | `cli.py setup` | Initialize environment and fetch documentation |
| `plan` | `cli.py plan "Add user auth"` | Create implementation plan from request |
| `build` | `cli.py build specs/pending/001_feature-name/plan.md` | Execute plan and write code |
| `status` | `cli.py status specs/pending/001_feature-name` | Show build progress for a plan |
| `review` | `cli.py review specs/completed/001_feature-name` | Review completed build for issues |
| `fix` | `cli.py fix specs/reviews/review-feature.md` | Auto-fix issues from review |
| `list` | `cli.py list` | List all plans by status |
| `docs` | `cli.py docs` | Check/refresh AI documentation cache |
| `experts` | `cli.py experts list` | Manage expert agents |
| `cost` | `cli.py cost report daily` | Cost estimation and budget tracking |
| `portal` | `cli.py portal` | Start web management portal |
| `sync-remote` | `cli.py sync-remote` | Commit changes and create PR (AI-generated messages) |

## Workflows

### Planning
Takes a feature request and creates a detailed implementation plan.

```bash
uv run cli.py plan "Add JWT authentication"
# Output: specs/pending/001_jwt-authentication/
#   ├── 00_overview.md       # Plan metadata
#   ├── 01_context.md        # Codebase analysis (JSON)
#   ├── 02_architecture.md   # Architecture design (JSON)
#   ├── 03_implementation.md # Step-by-step plan
#   └── 04_validation.md     # Validation criteria
```

**Process:** Analyze complexity → Scout codebase → Architect design → Create plan → Validate

### Building
Executes a plan folder step-by-step, writing actual code.

```bash
# Build a plan (pass the FOLDER path, not individual files)
uv run cli.py build specs/pending/001_jwt-authentication

# Check build status
uv run cli.py status specs/pending/001_jwt-authentication

# Output: Code changes written to project + plan moved to /completed/
```

**Process:** Parse all .md files in folder → Execute each step → Self-review

**Note:** The build command takes the plan **folder** path. All `.md` files inside are read in sorted order (00_overview.md, 01_context.md, etc.) and combined for execution.

### Reviewing
Reviews completed work against best practices and documentation.

```bash
uv run cli.py review specs/completed/001_jwt-authentication
# Output: specs/reviews/review-jwt-authentication.md
```

**Process:** Detect tech stack → Check compliance → Expert reviews → Generate report

### Fixing
Automatically fixes issues identified in review.

```bash
uv run cli.py fix specs/reviews/review-jwt-authentication.md
uv run cli.py fix specs/reviews/review.md --dry-run  # Preview only
```

**Process:** Parse issues → Prioritize by severity → Apply fixes → Verify

### Sync Remote
Commits local changes and creates a PR with AI-generated messages.

```bash
uv run cli.py sync-remote
# Creates branch, commits, pushes, opens PR - all automatic
```

**Process:** Stage changes → AI generates commit message → Push → AI generates PR description → Create PR

## Project Structure

```
project/
├── .orchestrator/
│   ├── cli.py                  # Entry point
│   ├── setup.ps1               # Setup script
│   ├── pyproject.toml          # Python dependencies
│   │
│   ├── agents/                 # AI agent definitions
│   │   ├── planner.md          # Planning agent
│   │   ├── builder.md          # Code generation agent
│   │   ├── scout.md            # Codebase analysis agent
│   │   ├── architect.md        # Architecture design agent
│   │   ├── parser.md           # Plan parsing agent
│   │   ├── tester.md           # Testing agent
│   │   ├── goal-verifier.md    # Goal verification agent
│   │   ├── coordinator.md      # Parallel execution coordinator
│   │   ├── syncer.md           # Git sync agent
│   │   └── experts/            # Domain-specific experts
│   │       └── python.md
│   │
│   ├── server/                 # Web portal backend
│   │   ├── app.py              # FastAPI application
│   │   ├── services/           # Dependency injection services
│   │   │   ├── __init__.py
│   │   │   ├── interfaces.py   # Service interfaces (ABC)
│   │   │   ├── file_service.py # File operations service
│   │   │   └── plan_registry.py # Plan management service
│   │   ├── static/             # Frontend assets
│   │   │   └── js/             # JavaScript modules
│   │   └── templates/          # Jinja2 HTML templates
│   │
│   ├── specs/                  # Plan lifecycle
│   │   ├── pending/            # Plans ready to build
│   │   │   └── 001_feature/    # Each plan is a folder
│   │   │       └── plan.md     # Implementation plan
│   │   ├── completed/          # Successfully built plans
│   │   ├── failed/             # Failed builds
│   │   └── state/              # Build state tracking (for resume)
│   │
│   ├── config/                 # Configuration files
│   │   ├── budget.json         # Cost budget limits
│   │   └── agent.json          # Agent behavior settings
│   │
│   ├── core/                   # Core orchestrator logic
│   │   ├── agent.py            # Agent execution engine
│   │   ├── cost.py             # Cost tracking & estimation
│   │   └── config.py           # Configuration management
│   │
│   ├── workflows/              # Workflow definitions
│   │   ├── planning.py         # Planning workflow
│   │   ├── building.py         # Building workflow
│   │   └── reviewing.py        # Review workflow
│   │
│   ├── docs/                   # Cached AI documentation
│   │
│   └── tests/                  # Comprehensive test suite
│       ├── unit/               # Python unit tests (pytest)
│       ├── integration/        # Integration tests
│       └── e2e/                # Playwright E2E tests
│           ├── fixtures/       # Shared test fixtures
│           ├── utils/          # Test utilities
│           ├── visual/         # Percy visual regression tests
│           ├── workflows/      # Workflow-specific tests
│           └── docs/           # E2E testing documentation
│
└── src/                        # Your project code
```

## Plan Lifecycle

```
plan "Add feature" → specs/pending/001_feature/
                           ↓
                    build (execute steps)
                           ↓
              ┌────────────┴────────────┐
              ↓                         ↓
    specs/completed/001_feature   specs/failed/001_feature
              ↓                         ↓
         review                    fix & rebuild
              ↓
    specs/reviews/review-feature.md
              ↓
         fix (auto-apply)
```

## Web Portal

Start the web management portal to monitor and manage plans:

```bash
cd .orchestrator

# Start portal (default: http://localhost:8000)
uv run cli.py portal

# Start on custom port
uv run cli.py portal --port 3000
```

**Portal Features:**
- Dashboard with plan overview
- Plan listing by status (pending, completed, failed)
- Plan detail view with content
- Build progress monitoring
- Cost tracking and budget status
- Run history and events

## Requirements

- **Claude Code CLI** - `npm i -g @anthropic-ai/claude-code`
- **Python 3.11+**
- **Node.js 18+** - For E2E tests
- **GitHub CLI** - `gh` (for sync-remote)
- **UV** - Auto-installed by setup.ps1

## License

MIT




  Files Summary

  .orchestrator/
  ├── agents/
  │   ├── scout.md              # Original (legacy)
  │   ├── scout-overview.md     # NEW: Layer 1
  │   ├── scout-techstack.md    # NEW: Layer 2
  │   ├── scout-domain.md       # NEW: Layer 3
  │   └── scout-deep.md         # NEW: Layer 4
  ├── core/
  │   ├── domain_scanner.py     # NEW: Tech-agnostic detection
  │   └── knowledge_store.py    # UPDATED: Layered models
  ├── workflows/
  │   ├── scouting.py           # Original (legacy)
  │   └── smart_scouting.py     # NEW: Multi-phase workflow
  ├── docs/
  │   └── smart-scout-design.md # NEW: Architecture doc
  └── cli.py                    # UPDATED: smart-scout command

  Usage

  # Interactive mode (recommended)
  orchestrator smart-scout

  # Non-interactive with deep scan
  orchestrator smart-scout -n --depth deep

  # Quick scan only
  orchestrator smart-scout -n --depth quick

  The system now:
  1. Detects domains without assuming technology
  2. Asks you what to scan and how deep
  3. Uses AI agents for intelligent analysis at each layer
  4. Falls back gracefully if agents fail
  5. Generates experts based on discovered technologies
  6. Extracts rules from patterns found
