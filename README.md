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
| `build` | `cli.py build specs/pending/001_feature-name` | Execute plan folder and write code |
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
│   ├── cli.py              # Entry point
│   ├── setup.ps1           # Setup script
│   ├── pyproject.toml      # Python dependencies
│   ├── agents/             # AI agent definitions (scout, architect, planner, etc.)
│   ├── specs/              # Plan lifecycle
│   │   ├── pending/        # Plans ready to build
│   │   │   └── 001_feature/  # Each plan is a folder
│   │   │       ├── 00_overview.md
│   │   │       ├── 01_context.md
│   │   │       ├── 02_architecture.md
│   │   │       ├── 03_implementation.md
│   │   │       └── 04_validation.md
│   │   ├── completed/      # Successfully built plans
│   │   ├── failed/         # Failed builds
│   │   ├── reviews/        # Review reports
│   │   └── state/          # Build state tracking (for resume)
│   ├── docs/               # Cached documentation
│   └── tests/              # Test suite
└── src/                    # Your project code
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

## Requirements

- **Claude Code CLI** - `npm i -g @anthropic-ai/claude-code`
- **Python 3.11+**
- **GitHub CLI** - `gh` (for sync-remote)
- **UV** - Auto-installed by setup.ps1

## License

MIT




uv run cli.py plan "Extract inline JavaScript from server/templates/*.html into separate .js files in server/static/js/. Add Jest for testing. Create package.json with jest dependency, configure Jest, and add unit tests for extracted JS functions."


uv run cli.py plan "Add visual regression testing using Percy.io for the orchestrator web UI. Integrate Percy with the existing Playwright tests (or create new ones). Configure Percy in CI, add percy.yml config, and capture snapshots of key pages: plan list, plan detail, and build progress."


uv run cli.py plan "Refactor server/app.py to use dependency injection for better testability. Extract hard-coded dependencies (file paths, plan registry) into injectable services. Create a services/ module with interfaces. Update tests to use mock services."


uv run cli.py plan "Create a comprehensive E2E test suite for the orchestrator. Use Playwright to test: (1) full planning workflow - create plan from request, (2) build workflow - execute plan and verify files created, (3) review workflow - review built code. Structure tests in tests/e2e/ with fixtures for test data."
