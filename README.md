# SDLC Orchestrator

AI-powered software development lifecycle automation using Claude Code.

## Overview

Manage multiple projects from one place. Add projects, switch between them, and run AI-powered workflows.

```
User Request (plain text)
    ↓
orch plan "Add feature X"
    ↓
specs/pending/001_feature-x/plan.md
    ↓
orch build specs/pending/001_feature-x
    ↓
specs/completed/001_feature-x/plan.md
```

## Requirements

- **Claude Code CLI** - `npm i -g @anthropic-ai/claude-code`
- **Python 3.11+**
- **PostgreSQL** - For data persistence
- **GitHub CLI** - `gh` (for sync-remote)

## Quick Start

### Windows (PowerShell)

```powershell
# 1. Run setup (creates .env, installs orch, registers this project as "self")
cd .orchestrator
.\setup.ps1 -DbPassword "your_password"

# 2. Restart terminal, then run workflows
orch plan "Add user authentication"
orch build
orch scout

# 3. Start the portal
orch portal
```

### Manual Setup

```bash
# 1. Create .env file in .orchestrator/
cd .orchestrator
cp .env.example .env
# Edit .env with your database credentials

# 2. Install and initialize
pip install -e .
orch init

# 3. Add a project
orch project add /path/to/my-project

# 4. Switch to project
orch project switch my-project

# 5. Run workflows
orch plan "Add user authentication"
orch build
orch scout

# 6. Start the portal
orch portal
```

## Adding Projects

### From Local Directory

```bash
orch project add /path/to/existing-project
```

### From Git Repository

```bash
orch project add --git https://github.com/user/repo.git --dest /path/to/clone
orch project add --git https://github.com/user/repo.git --dest /path/to/clone --branch develop
```

## Switching Projects

### Via CLI

```bash
orch project switch my-project
```

### Via Portal

Use the project switcher dropdown in the navigation bar to switch between projects.

## CLI Commands

### Workflow Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `plan` | `orch plan "Add user auth"` | Create implementation plan from request |
| `build` | `orch build [plan_id]` | Execute plan and write code |
| `scout` | `orch scout [--quick\|--deep]` | Analyze codebase and build knowledge |
| `sync` | `orch sync` | Commit changes and create PR |
| `portal` | `orch portal` | Start web management portal |

### Project Commands

```bash
# List all projects
orch project list [--all]          # --all includes archived

# Add projects
orch project add /path/to/project
orch project add --git <url> --dest <path> [--branch <branch>]

# Switch project
orch project switch <name>

# View project info
orch project info [name]

# Archive/restore
orch project archive <name>
orch project restore <name>

# Remove project
orch project remove <name> [--force] [--delete-files]

# Git operations
orch project fetch [name]
orch project pull [name]
orch project status [name]
```

### Other Commands

```bash
orch init              # Initialize orchestrator
orch list              # List all plans
orch cost report daily # Check cost/budget
```

## Architecture

### Workflow

| Step | What Happens |
|------|--------------|
| 1. Plan | User request → Planner agent explores codebase → Creates `plan.md` |
| 2. Parse | Deterministic parser extracts GOAL, STEPS, VERIFY (no LLM needed) |
| 3. Build | Builder agent executes each step → Verifies DONE criteria |
| 4. Complete | Plan moves from `pending/` to `completed/` |

### Agents

| Agent | Purpose | Tools |
|-------|---------|-------|
| **planner** | Explores codebase, designs approach, creates plan | Read, Glob, Grep, Bash |
| **builder** | Implements code, verifies each step | Write, Edit, Read, Bash, Glob, Grep |
| **scout** | Analyzes codebase, extracts knowledge | Read, Glob, Grep |
| **goal-verifier** | Verifies the overall goal is achieved | Read, Glob, Grep |

### Plan Format

```
GOAL: [One sentence - what success looks like]

CONTEXT:
- [Key codebase fact]
- [Pattern to follow]

STEPS:
1. [Title with action verb]
   ACTION: create|modify|delete|run
   DO: [What to implement - plain English]
   IN: [Files to read for patterns]
   OUT: [Output file path]
   DONE: [How to verify this step]
   NEEDS: [Dependencies, or "none"]

VERIFY:
- [How to verify the whole feature works]
```

### Plan Lifecycle

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

```bash
orch portal
```

### Portal Features

- **Dashboard**: Plan status counts, active tasks, sync status
- **Plans**: Create, view, and manage implementation plans
- **Knowledge**: View codebase intelligence and run scout scans
- **Chat**: Interactive knowledge assistant
- **Runs**: Workflow execution history
- **Projects**: Add, switch, and manage projects

### Project Switcher

The portal includes a project switcher in the navigation bar:
- Click the current project name to open the dropdown
- Select a different project to switch context
- All data is isolated per project

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SDLC_ORCHESTRATOR_HOME` | Override home directory (optional) | `.orchestrator/` |
| `ORCH_DB_HOST` | PostgreSQL host | `localhost` |
| `ORCH_DB_PORT` | PostgreSQL port | `5432` |
| `ORCH_DB_NAME` | Database name | `orchestrator` |
| `ORCH_DB_USER` | Database user | `postgres` |
| `ORCH_DB_PASSWORD` | Database password | `postgres` |

**Note:** Multi-project mode is always enabled. The `.orchestrator/` directory is used as the default home. Set `SDLC_ORCHESTRATOR_HOME` only if you need a custom location.

## Database Setup

The orchestrator uses PostgreSQL for data persistence.

### Quick Setup (Windows)

```powershell
# Run setup script - creates .env and initializes database
cd .orchestrator
.\setup.ps1 -DbPassword "your_password"
```

### Manual Setup

1. Create the database:
```bash
createdb orchestrator
```

2. Create `.env` file in `.orchestrator/`:
```env
ORCH_DB_HOST=localhost
ORCH_DB_PORT=5432
ORCH_DB_NAME=orchestrator
ORCH_DB_USER=postgres
ORCH_DB_PASSWORD=your_password
```

3. Initialize:
```bash
orch init
```

## Project Structure

```
.orchestrator/
├── cli.py                  # Entry point
├── config.py               # Unified configuration
├── agents/                 # AI agent definitions
│   ├── planner.md          # Planning agent
│   ├── builder.md          # Code generation agent
│   ├── scout.md            # Codebase analysis agent
│   └── experts/            # Domain-specific experts
├── core/                   # Core orchestrator logic
│   ├── agent.py            # Agent execution engine
│   ├── workflow.py         # Base workflow class
│   ├── plan_parser.py      # Deterministic plan parser
│   ├── knowledge_store.py  # Codebase knowledge management
│   ├── project_registry.py # Project management (multi-project)
│   └── git_manager.py      # Git operations
├── db/                     # Database layer
│   ├── models.py           # SQLAlchemy models
│   ├── repositories/       # Data access layer
│   └── migrations/         # Alembic migrations
├── workflows/              # Workflow implementations
│   ├── planning.py         # Plan creation workflow
│   ├── building.py         # Plan execution workflow
│   ├── scouting.py         # Codebase analysis workflow
│   └── syncing.py          # Git sync workflow
├── portal/                 # Web portal
│   ├── app.py              # FastAPI application
│   ├── routes/             # API endpoints
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # Frontend assets
├── specs/                  # Plans storage
│   ├── pending/            # Plans waiting to be built
│   ├── completed/          # Successfully built plans
│   └── failed/             # Failed builds
└── docs/                   # Documentation
```

## Project Isolation

Each project has complete data isolation:
- **Isolated database records**: All tables have `project_id` foreign key
- **Separate knowledge base**: Codebase analysis stored per project
- **Project-specific experts**: Custom AI experts for the project
- **Independent plans/runs**: No cross-project data leakage

```
.orchestrator/
├── .env               # Database credentials
├── cli.py             # Entry point
├── config.py          # Unified configuration
├── core/              # Shared orchestrator logic
├── workflows/         # Shared workflow definitions
├── portal/            # Web portal (multi-project aware)
├── agents/            # Shared agent definitions
│   └── experts/       # Shared tech experts
├── projects/          # Per-project data
│   ├── registry.json  # Project registry (cache, DB is source of truth)
│   └── {project-slug}/
│       ├── knowledge/ # Codebase analysis
│       ├── experts/   # Project-specific experts
│       └── config/    # Project overrides
├── config/            # Global configuration
└── logs/              # Log files
```

## License

MIT
