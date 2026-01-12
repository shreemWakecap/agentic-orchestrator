# SDLC Orchestrator

AI-powered software development lifecycle automation: **Plan → Build → Review → Fix**

## Quick Start

```bash
# Setup
.\.orchestrator\setup.ps1

# Run CLI
uv run python .orchestrator/cli.py <command>
```

## CLI Commands

```
cli.py <command> [args]
```

| Command | Description |
|---------|-------------|
| `setup` | Initialize environment, fetch docs |
| `plan <request>` | Create implementation plan |
| `build <plan.md>` | Execute plan, write code |
| `review <plan.md>` | Review completed build |
| `fix <review.md>` | Auto-fix issues from review |
| `list` | List all plans by status |
| `docs` | Check/refresh AI documentation |
| `experts` | Manage expert agents |
| `cost` | Cost estimation & budgets |
| `test` | Run test suite |
| `portal` | Start management portal |

### Workflow Commands

```bash
# Full cycle
cli.py plan "Add JWT authentication"
cli.py build .specs/pending/jwt-authentication.md
cli.py review .specs/completed/jwt-authentication.md
cli.py fix .specs/reviews/review-jwt-authentication.md
```

### Expert Management

```bash
cli.py experts list
cli.py experts create auth --type domain --keywords auth,login,jwt
cli.py experts create core-api --type module --module src/api
cli.py experts create fastapi --type tech --based-on python
```

**Expert Types:**
- `tech` - Languages, frameworks, tools (auto-detected)
- `domain` - Business domains (consulted during planning)
- `module` - Project-specific modules

### Cost & Budget

```bash
cli.py cost estimate plan --request "Add auth"
cli.py cost report daily|weekly|monthly
cli.py cost budget show
cli.py cost budget set --daily 10.00 --monthly 100.00
```

### Other Commands

```bash
cli.py docs --refresh              # Refresh stale documentation
cli.py test --unit                 # Run unit tests
cli.py test --integration          # Run integration tests
cli.py fix <review.md> --dry-run   # Preview fixes without applying
cli.py portal --port 8080          # Custom portal port
```

## Workflows

```
Planning:    Scout → Architect → [Expert Consultation] → Planner → Validator
Building:    Parser → [Parallel Builders] → Tester → Reviewer
Reviewing:   Stack Detect → Compliance → [Expert Reviews] → Standards → Report
```

## Project Structure

```
.specs/                    # Plan lifecycle
├── pending/               # New plans
├── in-progress/           # Being built
├── completed/             # Built successfully
├── failed/                # Build failed
└── reviews/               # Review reports

.claude/agents/            # AI agent definitions
├── *.md                   # Workflow agents
└── experts/               # Tech/domain/module experts

ai_docs/                   # Cached documentation
└── README.md              # URLs to fetch
```

## Requirements

- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Python 3.11+
- UV (auto-installed)

## License

MIT
