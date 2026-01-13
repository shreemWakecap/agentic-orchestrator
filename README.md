# SDLC Orchestrator

AI-powered software development lifecycle automation using Claude Code.

## Quick Start

```bash
.\.orchestrator\setup.ps1                    # Setup (one time)
uv run python .orchestrator/cli.py <command> # Run commands
```

## Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `setup` | `cli.py setup` | Initialize environment and fetch documentation |
| `plan` | `cli.py plan "Add user auth"` | Create implementation plan from request |
| `build` | `cli.py build .orchestrator/specs/pending/plan.md` | Execute plan and write code |
| `review` | `cli.py review .orchestrator/specs/completed/plan.md` | Review completed build for issues |
| `fix` | `cli.py fix .orchestrator/specs/reviews/review.md` | Auto-fix issues from review |
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
cli.py plan "Add JWT authentication"
# Output: .orchestrator/specs/pending/jwt-authentication.md
```

**Process:** Scout codebase → Architect design → Consult experts → Generate plan

### Building
Executes a plan step-by-step, writing actual code.

```bash
cli.py build .orchestrator/specs/pending/jwt-authentication.md
# Output: Code changes + plan moved to /completed/
```

**Process:** Parse steps → Execute each step → Run tests → Self-review

### Reviewing
Reviews completed work against best practices and documentation.

```bash
cli.py review .orchestrator/specs/completed/jwt-authentication.md
# Output: .orchestrator/specs/reviews/review-jwt-authentication.md
```

**Process:** Detect tech stack → Check compliance → Expert reviews → Generate report

### Fixing
Automatically fixes issues identified in review.

```bash
cli.py fix .orchestrator/specs/reviews/review-jwt-authentication.md
cli.py fix .orchestrator/specs/reviews/review.md --dry-run  # Preview only
```

**Process:** Parse issues → Prioritize by severity → Apply fixes → Verify

### Sync Remote
Commits local changes and creates a PR with AI-generated messages.

```bash
cli.py sync-remote
# Creates branch, commits, pushes, opens PR - all automatic
```

**Process:** Stage changes → AI generates commit message → Push → AI generates PR description → Create PR

## Project Structure

```
project/
├── .orchestrator/
│   ├── cli.py              # Entry point
│   ├── setup.ps1           # Setup script
│   ├── agents/             # AI agent definitions
│   ├── specs/              # Plan lifecycle
│   │   ├── pending/        # New plans
│   │   ├── in-progress/    # Being built
│   │   ├── completed/      # Built successfully
│   │   ├── failed/         # Build failed
│   │   └── reviews/        # Review reports
│   ├── docs/               # Cached documentation
│   └── tests/              # Test suite
└── src/                    # Your project code
```

## Requirements

- **Claude Code CLI** - `npm i -g @anthropic-ai/claude-code`
- **Python 3.11+**
- **GitHub CLI** - `gh` (for sync-remote)
- **UV** - Auto-installed by setup.ps1

## License

MIT
