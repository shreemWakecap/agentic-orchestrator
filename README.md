# Self-Evolving SDLC Orchestrator

A minimal, self-improving development system with **actual workflow code** that orchestrates multiple Claude agents.

## Quick Start

```powershell
# Setup (installs dependencies)
./scripts/setup.ps1

# Run the planning workflow
uv run python scripts/plan.py "Add user authentication with JWT"

# Output saved to .specs/
```

## How It Works

The orchestrator runs **workflows** that coordinate multiple **agents**:

```
User: "Add user authentication"
              │
              ▼
┌─────────────────────────────────────────────────┐
│           PLANNING WORKFLOW                      │
│                                                 │
│  ┌──────────┐      ┌──────────┐                │
│  │  Scout   │─────▶│ Architect│                │
│  │ (explore │      │ (design  │                │
│  │ codebase)│      │ approach)│                │
│  └──────────┘      └────┬─────┘                │
│                         │                       │
│                         ▼                       │
│  ┌──────────┐      ┌──────────┐                │
│  │ Validator│◀─────│ Planner  │                │
│  │ (check   │      │ (create  │                │
│  │  plan)   │      │  steps)  │                │
│  └────┬─────┘      └──────────┘                │
│       │                                         │
│       ▼                                         │
│  .specs/user-authentication-jwt.md              │
└─────────────────────────────────────────────────┘
```

Each agent has a specific role and returns structured output to the next agent.

## Project Structure

```
.
├── .orchestrator/           # Workflow code
│   ├── core/
│   │   ├── agent.py        # Agent wrapper (calls Claude API)
│   │   └── workflow.py     # Workflow base class
│   ├── workflows/
│   │   └── planning.py     # Planning workflow (4 agents)
│   ├── experts/            # Generated domain expertise
│   └── pyproject.toml      # Dependencies
│
├── .claude/                 # Claude Code config (optional)
│   ├── agents/             # Agent definitions
│   └── commands/           # Slash commands
│
├── .specs/                  # Generated implementation plans
│
├── scripts/
│   ├── setup.ps1           # Setup script
│   └── plan.py             # Run planning workflow
│
└── README.md
```

## The Planning Workflow

The planning workflow uses 4 specialized agents:

| Agent | Role | Output |
|-------|------|--------|
| **Scout** | Explores codebase structure | Context about project |
| **Architect** | Designs high-level approach | Architecture design |
| **Planner** | Creates implementation steps | Detailed task list |
| **Validator** | Ensures plan is complete | Approval/feedback |

Each agent receives context from previous agents, creating a **chain of specialized reasoning**.

## Creating Custom Workflows

```python
from orchestrator.core import Agent, Workflow, WorkflowResult

class MyWorkflow(Workflow):
    def __init__(self, project_root):
        super().__init__(name="My Workflow", output_dir=project_root / ".output")

        # Register agents
        self.register_agent(Agent(
            name="analyzer",
            system_prompt="You analyze code...",
            model="claude-sonnet-4-20250514"
        ))

    def execute(self, request: str) -> WorkflowResult:
        result = self.run_agent("analyzer", message=request)
        # ... orchestration logic
        return WorkflowResult(success=True, ...)
```

## Environment Setup

Requires `ANTHROPIC_API_KEY` in `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

## Commands

| Command | Description |
|---------|-------------|
| `uv run python scripts/plan.py "..."` | Run planning workflow |
| `./scripts/setup.ps1` | Install dependencies |

## Philosophy

- **Real workflow code** - Not just configuration, actual Python orchestration
- **Multiple specialized agents** - Each agent does one thing well
- **Composable** - Build new workflows from existing agents
- **Self-improving** - Create domain experts as you encounter new stacks

## License

MIT
