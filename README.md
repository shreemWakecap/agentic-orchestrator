# SDLC Orchestrator

Orchestrates Claude Code agents through the full SDLC: **Plan → Build → Test → Review**.

## Architecture

```
.claude/                              .orchestrator/
├── agents/                           ├── workflows/
│   ├── scout.md                      │   ├── planning.py    (smart decomposition)
│   ├── architect.md                  │   ├── building.py    (parallel building)
│   ├── planner.md                    │   └── reviewing.py   (expert reviews)
│   ├── validator.md                  │
│   ├── analyzer.md                   ├── core/
│   ├── decomposer.md                 │   ├── agent.py       (print + agentic modes)
│   ├── synthesizer.md                │   ├── workflow.py    (base class)
│   ├── parser.md                     │   ├── docs_loader.py (freshness checking)
│   ├── builder.md                    │   └── expert_loader.py
│   ├── tester.md                     │
│   ├── reviewer.md                   └── run.py (CLI entry point)
│   ├── coordinator.md
│   ├── integrator.md
│   ├── stack_detector.md             ai_docs/
│   ├── compliance_checker.md         ├── README.md (URLs to fetch)
│   ├── standards_checker.md          └── *.md (cached docs)
│   ├── report_generator.md
│   └── experts/                      .specs/
│       ├── _meta.md                  ├── pending/
│       ├── python.md                 ├── in-progress/
│       ├── typescript.md             ├── completed/
│       └── react.md                  ├── failed/
│                                     └── reviews/
└── settings.json
```

## Quick Start

```powershell
# Setup
./.orchestrator/setup.ps1

# Create a plan
uv run python .orchestrator/run.py plan "Add user authentication with JWT"

# Build the plan
uv run python .orchestrator/run.py build .specs/pending/user-authentication.md

# Review the build
uv run python .orchestrator/run.py review .specs/completed/user-authentication.md

# List all plans
uv run python .orchestrator/run.py list

# Check AI docs freshness
uv run python .orchestrator/run.py docs

# List available experts
uv run python .orchestrator/run.py experts
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

Executes plans with parallel subagents that actually write code.

```
Simple Plans:
  Parser → Builder (per step) → Tester → Reviewer

Complex/Master Plans:
  Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Reviewer
```

### 3. Review Workflow (NEW)

Reviews completed builds for quality and compliance.

```
Review Flow:
  1. Load AI Docs (freshness check)
  2. Stack Detector → Identify technologies
  3. Compliance Checker → Did we build what was planned?
  4. [Parallel Expert Reviews] → Tech-specific code review
  5. Standards Checker → Universal best practices
  6. Report Generator → Actionable report
```

## Tech Experts System

Dynamic tech-specific experts that can be used across Plan/Build/Review:

```
.claude/agents/experts/
├── _meta.md          # Creates new experts dynamically
├── python.md         # Python best practices
├── typescript.md     # TypeScript best practices
├── react.md          # React patterns & hooks
└── (more as needed)
```

**Features:**
- Auto-detection of project tech stack
- Meta-expert creates new experts on-the-fly
- Experts provide tech-specific code reviews
- Reusable across all SDLC phases

```bash
# List available experts
uv run python .orchestrator/run.py experts
```

## AI Documentation System

Loads and manages documentation for agents:

```
ai_docs/
├── README.md           # URLs to fetch
├── .cache/
│   └── freshness.json  # Tracks file ages
└── *.md                # Cached documentation
```

**Freshness Policy:**
- Docs older than **2 days** are marked stale
- Warnings shown during workflow execution
- Auto-refresh available with `--refresh` flag

```bash
# Check docs status
uv run python .orchestrator/run.py docs

# Refresh stale docs
uv run python .orchestrator/run.py docs --refresh

# Refresh during review
uv run python .orchestrator/run.py review plan.md --refresh-docs
```

## Agent Execution Modes

```
┌─────────────────────────────────────────────────────────────────────┐
│  Print Mode (read-only)           │  Agentic Mode (can write)      │
│  claude --print -p "..."          │  claude -p "..." --yes         │
│                                   │  --allowedTools "Write,..."    │
├───────────────────────────────────┼─────────────────────────────────┤
│  • scout, architect, planner      │  • builder                      │
│  • analyzer, decomposer           │  • tester                       │
│  • parser, coordinator            │  • integrator                   │
│  • compliance_checker             │                                 │
│  • standards_checker              │                                 │
│  • report_generator               │                                 │
│  • all experts (python, etc.)     │                                 │
└───────────────────────────────────┴─────────────────────────────────┘
```

## Plan Lifecycle

```
                    Plan → Build → Review

┌──────────┐   ┌─────────────┐   ┌───────────┐   ┌─────────┐
│ pending/ │ → │ in-progress/│ → │ completed/│ → │ reviews/│
└──────────┘   └─────────────┘   └───────────┘   └─────────┘
                                       │
                                 or    ▼
                                 ┌─────────┐
                                 │ failed/ │
                                 └─────────┘
```

## Commands Reference

```bash
# Workflows
uv run python .orchestrator/run.py plan "Your feature request"
uv run python .orchestrator/run.py build <plan-file>
uv run python .orchestrator/run.py review <plan-file> [--refresh-docs]

# Utilities
uv run python .orchestrator/run.py list              # List all plans
uv run python .orchestrator/run.py docs [--refresh]  # Check/refresh docs
uv run python .orchestrator/run.py experts           # List tech experts
```

## Adding New Experts

1. Create expert in `.claude/agents/experts/<name>.md`:
```markdown
---
name: fastapi
description: Expert in FastAPI best practices
---

# FastAPI Expert

You are an expert in FastAPI with deep knowledge of...

## Review Checklist
...

## Common Issues
...
```

2. The expert will be auto-discovered and used when FastAPI is detected.

## Project Structure

```
.
├── .claude/                  # Knowledge Base
│   ├── agents/              # Agent definitions (17+ agents)
│   │   └── experts/         # Tech-specific experts
│   ├── commands/            # Interactive commands
│   └── settings.json        # Permissions
│
├── .orchestrator/           # Workflow Engine
│   ├── core/
│   │   ├── agent.py        # Agent runner (print + agentic)
│   │   ├── workflow.py     # Workflow base class
│   │   ├── docs_loader.py  # AI docs with freshness
│   │   └── expert_loader.py # Tech expert discovery
│   ├── workflows/
│   │   ├── planning.py     # Smart planning
│   │   ├── building.py     # Smart building
│   │   └── reviewing.py    # Expert reviewing
│   ├── run.py              # CLI entry point
│   └── setup.ps1           # Setup script
│
├── .specs/                  # Plan Storage
│   ├── pending/            # Awaiting build
│   ├── in-progress/        # Currently building
│   ├── completed/          # Successfully built
│   ├── failed/             # Build failures
│   └── reviews/            # Review reports
│
├── ai_docs/                 # AI Documentation
│   ├── README.md           # URLs to fetch
│   ├── .cache/             # Freshness tracking
│   └── *.md                # Cached docs
│
└── README.md
```

## Requirements

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **Python 3.11+** with UV
- **rich** package

## License

MIT
