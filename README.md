# SDLC Orchestrator

Orchestrates Claude Code agents to create implementation plans.

## Architecture

```
.claude/                         .orchestrator/
├── agents/                      ├── workflows/
│   ├── scout.md      <──────────┤   └── planning.py
│   ├── architect.md  <──────────┤       - step 1: load scout
│   ├── planner.md    <──────────┤       - step 2: load architect
│   └── validator.md  <──────────┤       - step 3: load planner
│                                │       - step 4: load validator
├── commands/                    │
│   └── (interactive commands)   ├── core/
│                                │   ├── agent.py    (loads from .claude/agents/)
└── settings.json                │   └── workflow.py (base class)
    (permissions)                │
                                 └── run.py (entry point)
```

**`.claude/`** = Knowledge Base (WHAT agents know)
- Agent definitions with system prompts
- Commands for interactive use
- Settings and permissions

**`.orchestrator/`** = Workflow Engine (HOW agents work together)
- Python code that orchestrates steps
- Loads agents from `.claude/agents/`
- Coordinates multi-agent workflows

## Quick Start

```powershell
# Setup
./.orchestrator/setup.ps1

# Run planning workflow
uv run python .orchestrator/run.py plan "Add user authentication with JWT"
```

## How It Works

```
uv run python .orchestrator/run.py plan "Add user auth"
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│  .orchestrator/run.py                                  │
│                                                        │
│  1. Load scout agent from .claude/agents/scout.md      │
│     → Run: claude --print -p "<scout system prompt>"   │
│     → Output: codebase context                         │
│                                                        │
│  2. Load architect from .claude/agents/architect.md    │
│     → Run: claude --print -p "<architect prompt>"      │
│     → Output: architecture design                      │
│                                                        │
│  3. Load planner from .claude/agents/planner.md        │
│     → Run: claude --print -p "<planner prompt>"        │
│     → Output: implementation steps                     │
│                                                        │
│  4. Load validator from .claude/agents/validator.md    │
│     → Run: claude --print -p "<validator prompt>"      │
│     → Output: plan approval                            │
│                                                        │
│  5. Compile and save to .specs/<plan>.md               │
└────────────────────────────────────────────────────────┘
```

## Structure

```
.
├── .claude/                  # Knowledge Base
│   ├── agents/
│   │   ├── scout.md         # Codebase exploration
│   │   ├── architect.md     # Architecture design
│   │   ├── planner.md       # Implementation steps
│   │   └── validator.md     # Plan validation
│   ├── commands/            # Interactive commands
│   └── settings.json        # Permissions
│
├── .orchestrator/            # Workflow Engine
│   ├── core/
│   │   ├── agent.py         # Loads agents from .claude/
│   │   └── workflow.py      # Workflow base class
│   ├── workflows/
│   │   └── planning.py      # Planning workflow
│   ├── run.py               # Entry point
│   └── setup.ps1            # Setup script
│
├── .specs/                   # Generated plans
└── README.md
```

## Adding New Agents

1. Create agent in `.claude/agents/<name>.md`:
```markdown
---
name: my-agent
description: What this agent does
---

# My Agent

You are a specialized agent that...

## Responsibilities
...

## Output Format
...
```

2. Load in workflow:
```python
self.register_agent(Agent.load("my-agent", project_root))
```

## Requirements

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **Python 3.11+** with UV
- **rich** package

## License

MIT
