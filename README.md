# SDLC Orchestrator

Orchestrates Claude Code agents through the full SDLC: Plan → Build → Test → Review.

## Architecture

```
.claude/                         .orchestrator/
├── agents/                      ├── workflows/
│   ├── scout.md                 │   ├── planning.py
│   ├── architect.md             │   │   └── Smart planning with decomposition
│   ├── planner.md               │   │
│   ├── validator.md             │   └── building.py
│   ├── analyzer.md              │       └── Parallel building with coordination
│   ├── decomposer.md            │
│   ├── synthesizer.md           ├── core/
│   ├── parser.md                │   ├── agent.py    (loads from .claude/agents/)
│   ├── builder.md               │   └── workflow.py (base class)
│   ├── tester.md                │
│   ├── reviewer.md              └── run.py (entry point)
│   ├── coordinator.md
│   └── integrator.md
│
├── commands/                    .specs/
│   └── (interactive commands)   ├── pending/      ← New plans land here
│                                ├── in-progress/  ← Currently building
└── settings.json                ├── completed/    ← Successfully built
                                 └── failed/       ← Build failures
```

## Quick Start

```powershell
# Setup
./.orchestrator/setup.ps1

# Create a plan
uv run python .orchestrator/run.py plan "Add user authentication with JWT"

# List all plans
uv run python .orchestrator/run.py list

# Build a plan
uv run python .orchestrator/run.py build .specs/pending/user-authentication.md
```

## Agent Execution Modes

Agents run in two modes depending on their purpose:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Print Mode (read-only)           │  Agentic Mode (can write)      │
│  claude --print -p "..."          │  claude -p "..." --yes         │
│                                   │  --allowedTools "Write,..."    │
├───────────────────────────────────┼─────────────────────────────────┤
│  • scout                          │  • builder                      │
│  • architect                      │  • tester                       │
│  • planner                        │  • integrator                   │
│  • validator                      │                                 │
│  • analyzer                       │                                 │
│  • decomposer                     │                                 │
│  • synthesizer                    │                                 │
│  • parser                         │                                 │
│  • coordinator                    │                                 │
│  • reviewer                       │                                 │
└───────────────────────────────────┴─────────────────────────────────┘
```

**Agentic agents** spawn Claude Code subprocesses that can:
- Create files (Write tool)
- Modify files (Edit tool)
- Run commands (Bash tool)
- Search codebase (Glob, Grep tools)

## Workflows

### Planning Workflow

Creates implementation plans with smart complexity analysis.

```
Simple/Medium Features:
  Scout → Architect → Planner → Validator

Complex/Massive Features:
  Analyzer → Decomposer → [Parallel Sub-Plans] → Synthesizer → Validator
```

**Agents:**
- `scout` - Explores codebase structure
- `architect` - Designs high-level approach
- `planner` - Creates implementation steps
- `validator` - Validates plan completeness
- `analyzer` - Determines complexity
- `decomposer` - Breaks into sub-features
- `synthesizer` - Combines sub-plans

### Building Workflow

Executes plans with parallel subagents that actually write code.

```
Simple Plans:
  Parser → Builder (per step) → Tester → Reviewer

Complex/Master Plans:
  Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Reviewer
```

**Agents:**
- `parser` - Extracts structured steps from plan
- `builder` - **AGENTIC** - Actually writes code using tools
- `tester` - **AGENTIC** - Runs tests and validation
- `reviewer` - Reviews code quality
- `coordinator` - Manages parallel execution
- `integrator` - **AGENTIC** - Merges sub-feature builds

**Features:**
- Parallel subagent execution via ThreadPoolExecutor
- Each builder runs as independent Claude subprocess
- Incremental building with checkpoints
- Resume from failure
- Automatic file organization

## Plan Lifecycle

```
Plan Created          Building           Outcome
     │                   │                  │
     ▼                   ▼                  ▼
┌──────────┐      ┌─────────────┐     ┌───────────┐
│ pending/ │  →   │ in-progress/│  →  │ completed/│
└──────────┘      └─────────────┘     └───────────┘
                                            │
                                      or    ▼
                                      ┌─────────┐
                                      │ failed/ │
                                      └─────────┘
```

## How Subagents Work

When building a plan, the orchestrator spawns Claude Code subprocesses:

```python
# Planning agents (print mode - read only)
subprocess.run(["claude", "--print", "-p", prompt])

# Building agents (agentic mode - can write files)
subprocess.run([
    "claude", "-p", prompt,
    "--yes",                              # Auto-accept prompts
    "--output-format", "json",            # Structured output
    "--allowedTools", "Read,Write,Edit,Bash,Glob,Grep"
])
```

Each subagent:
- Runs in isolated context (no context overflow)
- Can execute tools to modify the codebase
- Reports files created/modified back to orchestrator
- Can run in parallel with other independent steps

## Project Structure

```
.
├── .claude/                  # Knowledge Base
│   ├── agents/              # Agent definitions (13 agents)
│   ├── commands/            # Interactive commands
│   └── settings.json        # Permissions
│
├── .orchestrator/           # Workflow Engine
│   ├── core/
│   │   ├── agent.py        # Agent runner (print + agentic modes)
│   │   └── workflow.py     # Workflow base class
│   ├── workflows/
│   │   ├── planning.py     # Smart planning workflow
│   │   └── building.py     # Smart building workflow
│   ├── run.py              # Entry point
│   └── setup.ps1           # Setup script
│
├── .specs/                  # Plan Storage
│   ├── pending/            # Awaiting build
│   ├── in-progress/        # Currently building
│   ├── completed/          # Successfully built
│   └── failed/             # Build failures
│
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

2. Register in workflow:
```python
self.register_agent(Agent.load("my-agent", project_root))
```

3. For agentic agents (need to write files), add to `AGENTIC_AGENTS`:
```python
# In agent.py
AGENTIC_AGENTS = {"builder", "tester", "integrator", "my-agent"}
```

## Commands

```bash
# Planning
uv run python .orchestrator/run.py plan "Your feature request"

# Building
uv run python .orchestrator/run.py build <plan-file>
uv run python .orchestrator/run.py build user-auth.md  # Searches in .specs/

# List Plans
uv run python .orchestrator/run.py list
```

## Context Protection

Both workflows implement context protection to prevent data loss:

- **Truncation**: Large content is truncated before passing to agents
- **Isolated Contexts**: Each subagent runs in isolated subprocess
- **Summarized Handoff**: Only essential context passed between agents
- **Checkpointing**: Build state saved after each step

## Requirements

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **Python 3.11+** with UV
- **rich** package

## License

MIT
