# Agentic Orchestrator

A practical system for automating software development using Claude Code.

## Overview

```
User Request (plain text)
    ↓
cli.py plan "Add feature X"
    ↓
specs/pending/001_feature-x/plan.md
    ↓
cli.py build specs/pending/001_feature-x
    ↓
specs/completed/001_feature-x/plan.md
```

## Quick Start

```bash
# Create a plan
python cli.py plan "Add a health check endpoint that returns status"

# Build from plan
python cli.py build specs/pending/001_add-health-check

# Or use the web portal
python cli.py portal
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

### Directory Structure

```
.orchestrator/
├── agents/              # Agent system prompts
│   ├── planner.md      # Creates implementation plans
│   ├── builder.md      # Executes plan steps
│   └── goal-verifier.md
├── actions/            # Workflow implementations
│   ├── planning.py     # Plan creation workflow
│   └── building.py     # Plan execution workflow
├── core/               # Core components
│   ├── agent.py        # Agent runner (calls Claude Code)
│   ├── workflow.py     # Base workflow class
│   └── plan_parser.py  # Deterministic plan parser
├── specs/              # Plans storage
│   ├── pending/        # Plans waiting to be built
│   ├── completed/      # Successfully built plans
│   └── failed/         # Failed builds
├── portal/             # Web portal
│   └── app.py          # FastAPI application
└── docs/               # Documentation
```

## Key Design Decisions

### 1. Single Planner Agent

Instead of multiple agents (scout → architect → planner → validator), we use **one planner** that:
- Explores the codebase using tools (Glob, Grep, Read)
- Designs the implementation approach
- Outputs a structured plan

**Why?** Fewer LLM calls = faster, cheaper, simpler.

### 2. Deterministic Parser

The plan is parsed using **regex, not an LLM**:
- Faster (no API call)
- Reliable (same input = same output)
- Validates structure during parsing

See `core/plan_parser.py`.

### 3. DONE Criteria Flow

Every step has a DONE field that flows through the system:
```
Planner → plan.md (DONE: "file has router and endpoint")
    ↓
Parser → PlanStep.done field
    ↓
Builder receives → Verifies against DONE criteria
    ↓
Reports → VERIFIED: yes/no
```

### 4. Simple File Structure

Each plan is one folder with one file:
```
specs/pending/001_feature-name/
└── plan.md
```

Not 5 separate files. Simple is better.

## API Reference

### Planning Workflow

```python
from actions.planning import PlanningWorkflow

workflow = PlanningWorkflow(project_root=Path("."))
result = workflow.run("Add user authentication")

# Result:
# - result.success: bool
# - result.output_file: Path to plan.md
# - result.data: {"plan_id": "001_add-user", "steps": 5, "goal": "..."}
```

### Building Workflow

```python
from actions.building import BuildingWorkflow

workflow = BuildingWorkflow(project_root=Path("."))
result = workflow.run("specs/pending/001_add-user")

# Result:
# - result.success: bool
# - result.steps_completed: int
# - result.data: {"files_created": [...], "files_modified": [...]}
```

### Plan Parser

```python
from core.plan_parser import PlanParser, parse_plan

# Parse from string
result = parse_plan(plan_content)
if result.success:
    plan = result.plan
    for step in plan.all_steps:
        print(f"{step.id}: {step.action} → {step.target}")
        print(f"  DONE: {step.done}")

# Parse from file
result = parse_plan_file(Path("plan.md"))
```

## Web Portal

```bash
python cli.py portal
# Opens http://localhost:8000
```

Features:
- Dashboard with plan status counts
- Create new plans via web form
- Trigger builds from browser
- Real-time progress via SSE

## Configuration

See `config/agents.yaml` for agent configuration:
- Timeout settings
- Token limits
- Parallel execution settings
- Model selection
