# Agentic Orchestrator - Project Memory

This repository implements a deterministic, filesystem-first Claude Code orchestration system.

## Architecture

```
.claude/
├── settings.json      # Permissions, hooks configuration
├── agents/            # Subagents (separate context windows)
│   ├── planner.md
│   ├── implementer.md
│   ├── test-runner.md
│   ├── reviewer.md
│   └── memory-summarizer.md
├── skills/            # Reusable skills
│   ├── atomic-planning/
│   ├── tdd-implementation/
│   └── plan-compliance-review/
├── commands/          # Slash commands (interactive mode)
│   ├── orch-plan.md
│   ├── orch-run.md
│   ├── orch-review.md
│   └── orch-status.md
└── hooks/             # Python hook scripts
    ├── pre_tool_use.py
    ├── post_tool_use.py
    └── stop.py

orchistrator/          # Headless TypeScript workflow runner
├── src/
│   ├── index.ts
│   ├── claude.ts
│   └── orchistrator.ts
└── runs/              # Workflow artifacts
    └── <run-id>/
        ├── goal.md
        ├── plan/
        ├── logs/
        ├── subplan-results/
        ├── memory/
        └── FINAL.md
```

## Workflow (Deterministic)

The orchestrator executes a strict Plan → Implement → Test → Review → Iterate loop:

1. **PLAN**: Create atomic subplans in `orchistrator/runs/<run-id>/plan/`
   - `plan.json` - Machine-readable metadata
   - `overview.md` - Human-readable summary
   - `subplans/*.md` - Atomic, testable subplans

2. **For each subplan**:
   - **IMPLEMENT**: Execute only that subplan, including unit tests
   - **TEST**: Run tests and fix failures until green
   - **REVIEW**: Strict pass/fail review against the plan
   - **ITERATE**: If review fails, loop back to implement with feedback (max 5 attempts)

3. **COMPLETE**: Stop when all subplans pass review (or max attempts reached)

## Agents

| Agent | Purpose | Model |
|-------|---------|-------|
| `planner` | Creates atomic subplans from goals | opus |
| `implementer` | Implements one subplan at a time | opus |
| `test-runner` | Runs tests and fixes failures | sonnet |
| `reviewer` | Strict pass/fail review | opus |
| `memory-summarizer` | Compresses context for iterations | haiku |

## Commands

### Orchestrator Commands

| Command | Description |
|---------|-------------|
| `/orch-plan [goal]` | Create planning folder with subplans |
| `/orch-run [goal]` | Execute full orchestrator workflow |
| `/orch-implement [run-id] [subplan-id]` | Manually implement a specific subplan |
| `/orch-test [run-id] [subplan-id]` | Run tests for a subplan, fix until green |
| `/orch-review [run-id]` | Review implementation against plan |
| `/orch-resume [run-id]` | Resume a failed/incomplete run |
| `/orch-status [run-id?]` | Show run status |
| `/orch-logs [run-id] [subplan-id?]` | View logs and debug info |

### General Commands

| Command | Description |
|---------|-------------|
| `/question [question]` | Ask questions about the codebase |
| `/build [path-to-plan]` | Build from an existing plan file |

## Skills

| Skill | Description |
|-------|-------------|
| `atomic-planning` | Create atomic, testable subplans |
| `tdd-implementation` | Test-driven development workflow |
| `plan-compliance-review` | Strict pass/fail review |

## Safety Rules

- **Never read secrets**: `.env`, `.env.*`, `secrets/**`, private keys
- **Minimal changes**: Keep changes scoped to the active subplan
- **No scope creep**: Implement only what the plan specifies
- **Strict reviews**: Reject if acceptance criteria aren't fully met

## Running the Orchestrator

```bash
# Install dependencies
npm --prefix orchistrator install

# Build TypeScript
npm --prefix orchistrator run build

# Run with a goal
node orchistrator/dist/index.js "your goal here"
```

## Headless Mode Notes

The orchestrator uses `claude -p` (headless mode) with:
- `--allowedTools` for auto-approving specific tools
- `--output-format json` + `--json-schema` for structured output
- Slash commands are NOT available in headless mode
