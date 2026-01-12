# SDLC Orchestrator

AI-powered software development lifecycle automation.

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  PLAN   │ ─► │  BUILD  │ ─► │ REVIEW  │ ─► │   FIX   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

## Quick Start

```bash
.\.orchestrator\setup.ps1                    # Setup
uv run python .orchestrator/cli.py <command> # Run
```

## CLI Commands

```
┌────────────────────────────────────────────────────────────┐
│  cli.py <command> [args]                                   │
├────────────┬───────────────────────────────────────────────┤
│  setup     │  Initialize environment, fetch docs           │
│  plan      │  Create implementation plan                   │
│  build     │  Execute plan, write code                     │
│  review    │  Review completed build                       │
│  fix       │  Auto-fix issues from review                  │
│  list      │  List all plans by status                     │
│  docs      │  Check/refresh AI documentation               │
│  experts   │  Manage expert agents                         │
│  cost      │  Cost estimation & budgets                    │
│  test      │  Run test suite                               │
│  portal    │  Start management portal                      │
└────────────┴───────────────────────────────────────────────┘
```

### Workflow Example

```bash
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
```

```
┌─────────────────────────────────────────────────────────┐
│  Expert Types                                           │
├─────────────┬───────────────────────────────────────────┤
│  tech       │  Languages, frameworks (auto-detected)    │
│  domain     │  Business domains (consulted in planning) │
│  module     │  Project-specific modules                 │
└─────────────┴───────────────────────────────────────────┘
```

### Cost & Budget

```bash
cli.py cost estimate plan --request "Add auth"
cli.py cost report daily|weekly|monthly
cli.py cost budget set --daily 10.00 --monthly 100.00
```

## Workflows

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PLANNING                                                                   │
│                                                                             │
│    ┌───────┐   ┌───────────┐   ┌─────────────────────┐   ┌─────────┐       │
│    │ Scout │ ─►│ Architect │ ─►│ Expert Consultation │ ─►│ Planner │ ─► Plan│
│    └───────┘   └───────────┘   └─────────────────────┘   └─────────┘       │
│                                         │                                   │
│                              ┌──────────┴──────────┐                       │
│                              │ Domain/Module Experts│                       │
│                              └─────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  BUILDING                                                                   │
│                                                                             │
│    ┌────────┐   ┌───────────────────────┐   ┌────────┐   ┌──────────┐      │
│    │ Parser │ ─►│   Parallel Builders   │ ─►│ Tester │ ─►│ Reviewer │      │
│    └────────┘   │  ┌─────┐ ┌─────┐     │   └────────┘   └──────────┘      │
│                 │  │ B1  │ │ B2  │ ... │                                   │
│                 │  └─────┘ └─────┘     │                                   │
│                 └───────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  REVIEWING                                                                  │
│                                                                             │
│    ┌───────────┐   ┌────────────┐   ┌────────────────┐   ┌────────┐        │
│    │ Stack     │ ─►│ Compliance │ ─►│ Expert Reviews │ ─►│ Report │        │
│    │ Detector  │   │ Checker    │   │ (parallel)     │   │        │        │
│    └───────────┘   └────────────┘   └────────────────┘   └────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Plan Lifecycle

```
                         .specs/
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   ┌─────────┐   ┌─────────────┐   ┌───────────┐    │
    │   │ pending │ ─►│ in-progress │ ─►│ completed │    │
    │   └─────────┘   └─────────────┘   └─────┬─────┘    │
    │        │                                │          │
    │        │ plan                    review │          │
    │        ▼                                ▼          │
    │   ┌─────────┐                    ┌──────────┐      │
    │   │ failed  │                    │ reviews/ │      │
    │   └─────────┘                    └──────────┘      │
    │                                                     │
    └─────────────────────────────────────────────────────┘
```

## Project Structure

```
project/
│
├── .orchestrator/              ◄── Core engine
│   ├── cli.py                      Entry point
│   ├── workflows/                  Planning, Building, Reviewing
│   ├── core/                       Agent, Workflow, Loaders
│   └── server/                     Portal backend
│
├── .claude/agents/             ◄── AI agents
│   ├── scout.md, architect.md      Workflow agents
│   └── experts/                    Tech/Domain/Module experts
│
├── .specs/                     ◄── Plan lifecycle
│   ├── pending/
│   ├── in-progress/
│   ├── completed/
│   └── reviews/
│
└── ai_docs/                    ◄── Cached documentation
    └── README.md                   URLs to fetch
```

## Requirements

```
┌────────────────────────────────────────┐
│  Claude Code CLI    npm i -g @anthropic-ai/claude-code  │
│  Python 3.11+                          │
│  UV                 (auto-installed)   │
└────────────────────────────────────────┘
```

## License

MIT
