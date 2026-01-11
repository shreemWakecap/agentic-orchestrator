# SDLC Orchestrator

Orchestrates Claude Code agents through the full SDLC: **Plan → Build → Review**.

## Architecture

```
.claude/                              .orchestrator/
├── agents/                           ├── cli.py            (unified CLI)
│   ├── scout.md                      ├── setup.ps1         (setup script)
│   ├── architect.md                  ├── pyproject.toml    (dependencies)
│   ├── planner.md                    │
│   ├── validator.md                  ├── workflows/
│   ├── analyzer.md                   │   ├── planning.py   (smart decomposition)
│   ├── decomposer.md                 │   ├── building.py   (parallel building)
│   ├── synthesizer.md                │   └── reviewing.py  (expert reviews)
│   ├── parser.md                     │
│   ├── builder.md                    ├── core/
│   ├── tester.md                     │   ├── agent.py      (print + agentic modes)
│   ├── reviewer.md                   │   ├── workflow.py   (base class)
│   ├── coordinator.md                │   ├── docs_loader.py (httpx fetcher)
│   ├── integrator.md                 │   └── expert_loader.py
│   ├── stack_detector.md             │
│   ├── compliance_checker.md         └── config/
│   ├── standards_checker.md              └── registry.json
│   ├── report_generator.md
│   └── experts/                      ai_docs/
│       ├── _meta.md                  ├── README.md (URLs to fetch)
│       └── python.md                 └── *.md (cached docs)
│
└── commands/                         .specs/
    ├── workflow.md                   ├── pending/
    ├── docs.md                       ├── in-progress/
    ├── experts.md                    ├── completed/
    ├── setup.md                      ├── failed/
    └── prime.md                      └── reviews/
```

## Quick Start

```powershell
# 1. Setup (installs UV, syncs deps, fetches docs)
.\.orchestrator\setup.ps1

# 2. Create a plan
uv run python .orchestrator/cli.py plan "Add user authentication with JWT"

# 3. Build the plan
uv run python .orchestrator/cli.py build .specs/pending/user-authentication.md

# 4. Review the build
uv run python .orchestrator/cli.py review .specs/completed/user-authentication.md
```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `setup` | Initialize environment | `.\.orchestrator\setup.ps1` |
| `plan` | Create implementation plan | `cli.py plan "Add feature X"` |
| `build` | Execute a plan | `cli.py build .specs/pending/plan.md` |
| `review` | Review completed build | `cli.py review .specs/completed/plan.md` |
| `list` | List all plans by status | `cli.py list` |
| `docs` | Check/refresh AI docs | `cli.py docs [--refresh]` |
| `experts` | List available experts | `cli.py experts` |

**Full command syntax:**
```powershell
# All commands run via UV
uv run python .orchestrator/cli.py <command> [args]

# Examples
uv run python .orchestrator/cli.py plan "Implement REST API for users"
uv run python .orchestrator/cli.py build .specs/pending/rest-api.md
uv run python .orchestrator/cli.py review .specs/completed/rest-api.md --refresh-docs
uv run python .orchestrator/cli.py list
uv run python .orchestrator/cli.py docs --refresh
uv run python .orchestrator/cli.py experts
```

## Workflows

### 1. Planning Workflow

Creates implementation plans with smart complexity analysis.

```
Simple/Medium Features:
  Scout → Architect → Planner → Validator

Complex/Massive Features:
  Analyzer → Decomposer → [Parallel Sub-Plans] → Synthesizer → Validator
```

### 2. Building Workflow

Executes plans with parallel subagents that write code.

```
Simple Plans:
  Parser → Builder (per step) → Tester → Reviewer

Complex/Master Plans:
  Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Reviewer
```

### 3. Review Workflow

Reviews completed builds for quality and compliance.

```
Review Flow:
  1. Stack Detector → Identify technologies
  2. Compliance Checker → Did we build what was planned?
  3. [Parallel Expert Reviews] → Tech-specific code review
  4. Standards Checker → Universal best practices
  5. Report Generator → Actionable report
```

## Tech Experts System

Dynamic tech-specific experts for Plan/Build/Review phases:

```
.claude/agents/experts/
├── _meta.md     # Meta-expert (creates new experts dynamically)
└── python.md    # Python best practices
```

**Features:**
- Auto-detection of project tech stack
- Meta-expert creates new experts on-the-fly
- Experts provide tech-specific code reviews
- Reusable across all SDLC phases

**Add new experts** by creating `.claude/agents/experts/<name>.md`:
```markdown
---
name: fastapi
description: Expert in FastAPI best practices
---

# FastAPI Expert

You are an expert in FastAPI...

## Review Checklist
- Dependency injection patterns
- Response models
- Error handling
```

The expert will be auto-discovered when FastAPI is detected.

## AI Documentation System

Manages documentation for agents with freshness tracking:

```
ai_docs/
├── README.md    # URLs to fetch (source of truth)
└── *.md         # Cached documentation files
```

**Freshness Policy:**
- Docs older than **2 days** are marked stale
- Warnings shown during workflow execution
- Setup auto-fetches missing docs

```powershell
# Check docs status
uv run python .orchestrator/cli.py docs

# Refresh stale/missing docs
uv run python .orchestrator/cli.py docs --refresh
```

## Agent Execution Modes

```
+-----------------------------------+---------------------------------+
|  Print Mode (read-only)           |  Agentic Mode (can write)       |
|  claude --print -p "..."          |  claude -p "..." --allowedTools |
+-----------------------------------+---------------------------------+
|  scout, architect, planner        |  builder                        |
|  analyzer, decomposer             |  tester                         |
|  parser, coordinator              |  integrator                     |
|  compliance_checker               |                                 |
|  standards_checker                |                                 |
|  report_generator                 |                                 |
|  all experts                      |                                 |
+-----------------------------------+---------------------------------+
```

## Plan Lifecycle

```
                    Plan → Build → Review

+----------+   +-------------+   +-----------+   +---------+
| pending/ | → | in-progress/| → | completed/| → | reviews/|
+----------+   +-------------+   +-----------+   +---------+
                                       |
                                  or   v
                                 +---------+
                                 | failed/ |
                                 +---------+
```

## Requirements

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **Python 3.11+**
- **UV**: Auto-installed by setup.ps1

## License

MIT
