# SDLC Orchestrator

Orchestrates multiple Claude Code CLI subprocesses to create implementation plans.

## Quick Start

```powershell
# Setup
./.orchestrator/setup.ps1

# Run planning workflow
uv run python .orchestrator/run.py plan "Add user authentication with JWT"
```

## How It Works

```
uv run python .orchestrator/run.py plan "Add user authentication"
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│  .orchestrator/run.py                                │
│                                                      │
│  Spawns 4 Claude Code CLI processes sequentially:    │
│                                                      │
│  1. Scout     → claude --print -p "explore codebase" │
│  2. Architect → claude --print -p "design approach"  │
│  3. Planner   → claude --print -p "create steps"     │
│  4. Validator → claude --print -p "check plan"       │
│                                                      │
│  Output: .specs/<plan>.md                            │
└──────────────────────────────────────────────────────┘
```

## Structure

```
.
├── .orchestrator/
│   ├── core/
│   │   ├── agent.py      # Spawns claude CLI subprocess
│   │   └── workflow.py   # Workflow base class
│   ├── workflows/
│   │   └── planning.py   # 4-agent planning workflow
│   ├── experts/          # Generated domain expertise
│   ├── run.py            # Entry point
│   ├── setup.ps1         # Setup script
│   └── pyproject.toml
├── .specs/               # Generated plans
└── README.md
```

## Requirements

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **Python 3.11+** with UV
- **rich** package (installed by setup)

## Usage

```powershell
# Planning workflow
uv run python .orchestrator/run.py plan "Add user authentication"
uv run python .orchestrator/run.py plan "Build a REST API for products"
uv run python .orchestrator/run.py plan "Refactor database layer"

# Output
cat .specs/user-authentication.md
```

## Adding Workflows

Create a new workflow in `.orchestrator/workflows/`:

```python
from core import Agent, Workflow, WorkflowResult

class MyWorkflow(Workflow):
    def __init__(self, project_root):
        super().__init__(name="My Workflow", output_dir=project_root / ".output")

        self.register_agent(Agent(
            name="analyzer",
            system_prompt="You analyze code...",
            cwd=project_root,
        ))

    def execute(self, request: str) -> WorkflowResult:
        result = self.run_agent("analyzer", message=request)
        # ... orchestration logic
        return WorkflowResult(success=True, output_file=...)
```

Then add it to `run.py`.

## License

MIT
