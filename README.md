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
| `test` | `cli.py test` | Run test suite |
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

**Process:** Parse all .md files in folder → Execute each step → Run tests → Self-review

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

## Testing

The orchestrator includes a comprehensive test suite with unit tests, E2E tests, and visual regression tests.

### Quick Test Commands

```bash
cd .orchestrator

# Run all unit tests
uv run pytest tests/unit -v

# Run specific test file
uv run pytest tests/unit/test_agent.py -v

# Run tests with coverage
uv run pytest tests/unit --cov=core --cov=server --cov-report=html
```

### Unit Tests (Python/pytest)

Located in `tests/unit/`, these tests cover core functionality:

```bash
# Run all unit tests
uv run pytest tests/unit -v

# Run with verbose output
uv run pytest tests/unit -v --tb=short

# Run specific test module
uv run pytest tests/unit/test_cost.py -v

# Run tests matching a pattern
uv run pytest tests/unit -k "test_agent" -v
```

**Test modules:**
- `test_agent.py` - Agent execution, retries, error handling
- `test_config.py` - Configuration loading and validation
- `test_cost.py` - Cost estimation and budget management
- `test_portal.py` - FastAPI endpoints and workflows
- `test_system_explorer.py` - Technology detection
- `test_css_classes.py` - CSS class validation

### E2E Tests (Playwright)

Located in `tests/e2e/`, these tests verify the web portal functionality:

```bash
cd tests/e2e

# Install dependencies (first time)
npm install
npx playwright install

# Run all E2E tests
npm test

# Run in headed mode (see browser)
npm run test:headed

# Run with Playwright UI
npm run test:ui

# Run specific test file
npx playwright test plans.spec.ts

# Run tests matching pattern
npx playwright test --grep "navigation"

# Debug a specific test
npm run test:debug
```

**Test files:**
- `plans.spec.ts` - Plan listing and management
- `plan-details.spec.ts` - Plan detail page
- `build.spec.ts` - Build workflow execution
- `navigation.spec.ts` - Navigation and routing
- `accessibility.spec.ts` - WCAG accessibility checks
- `error-handling.spec.ts` - Error scenarios
- `cost-tracking.spec.ts` - Cost tracking workflow
- `plan-lifecycle.spec.ts` - Full plan lifecycle
- `expert-management.spec.ts` - Expert management

### Visual Regression Tests (Percy)

Located in `tests/e2e/visual/`, these tests detect unintended UI changes:

```bash
cd tests/e2e

# Set Percy token (required)
export PERCY_TOKEN="your_token_here"  # Linux/macOS
$env:PERCY_TOKEN="your_token_here"    # Windows PowerShell

# Run visual regression tests
npm run test:visual

# Run without uploading to Percy (local only)
npx playwright test visual/
```

**Configuration:**
- `percy.yml` - Percy configuration (viewports: 1280px, 768px, 375px)
- See `tests/e2e/docs/PERCY_SETUP.md` for detailed setup instructions

### Test Infrastructure

**Fixtures (`tests/e2e/fixtures/`):**
- `test-fixtures.ts` - Custom Playwright fixtures (APIClient, testPlan)
- `mock-errors.ts` - Route interception helpers for error testing
- `index.ts` - Shared selectors and utilities

**Utilities (`tests/e2e/utils/`):**
- `navigation.helpers.ts` - Navigation testing utilities
- `accessibility.helpers.ts` - Axe-core accessibility helpers
- `index.ts` - Utility exports

### CI/CD Integration

Tests run automatically on GitHub Actions:
- **Unit tests**: On every push and PR
- **E2E tests**: On PR to main branches
- **Visual tests**: On PR (requires `PERCY_TOKEN` secret)

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