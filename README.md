# Self-Evolving SDLC Orchestrator

A workflow system that orchestrates multiple **Claude Code CLI** subprocesses to create implementation plans.

## Quick Start

```powershell
# Setup (installs rich for console output)
./scripts/setup.ps1

# Run the planning workflow
uv run python scripts/plan.py "Add user authentication with JWT"

# Output saved to .specs/
```

## How It Works

The orchestrator spawns **4 Claude Code CLI processes** sequentially:

```
"Add User Authentication with JWT"
              │
              ▼
┌─────────────────────────────────────┐
│  claude --print -p "Scout prompt"   │  ← Process 1
│  Output: codebase context           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  claude --print -p "Architect..."   │  ← Process 2
│  Output: architecture design        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  claude --print -p "Planner..."     │  ← Process 3
│  Output: implementation steps       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  claude --print -p "Validator..."   │  ← Process 4
│  Output: plan approval              │
└──────────────┬──────────────────────┘
               │
               ▼
         .specs/plan.md
```

**No API keys in the orchestrator** - it uses Claude Code CLI which handles authentication.

## Project Structure

```
.
├── .orchestrator/           # Workflow code
│   ├── core/
│   │   ├── agent.py        # Spawns Claude Code subprocess
│   │   └── workflow.py     # Workflow base class
│   ├── workflows/
│   │   └── planning.py     # Planning workflow (4 agents)
│   └── pyproject.toml      # Just needs: rich
│
├── .specs/                  # Generated implementation plans
│
├── scripts/
│   ├── setup.ps1           # Setup script
│   └── plan.py             # Run planning workflow
│
└── README.md
```

## The 4 Agents

| Agent | System Prompt Focus | Output |
|-------|---------------------|--------|
| **Scout** | Explore codebase structure | Project context |
| **Architect** | Design high-level approach | Architecture |
| **Planner** | Create implementation steps | Task list |
| **Validator** | Verify plan completeness | Approval |

Each agent runs as a separate `claude --print -p "..."` subprocess.

## Requirements

- **Claude Code CLI** installed: `npm install -g @anthropic-ai/claude-code`
- **Python 3.11+** with UV
- **rich** (for console output)

## Usage

```powershell
# Run planning
uv run python scripts/plan.py "Add user authentication with JWT"

# Check output
cat .specs/user-authentication-jwt.md
```

## Philosophy

- **Uses Claude Code directly** - No API wrappers
- **Subprocess-based** - Each agent is a Claude Code process
- **Simple orchestration** - Python coordinates the sequence
- **Human-readable output** - Plans saved as markdown

## License

MIT
