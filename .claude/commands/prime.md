# Prime Command

Load system context and prepare for work.

## Steps

### 1. Load AI Documentation Status

Check documentation freshness:
```bash
uv run python .orchestrator/run.py docs
```

If docs are stale (>2 days), refresh them:
```bash
uv run python .orchestrator/run.py docs --refresh
```

### 2. Load Available Experts

List tech-specific experts:
```bash
uv run python .orchestrator/run.py experts
```

Available experts provide specialized code review and guidance:
- **meta-expert**: Creates new experts dynamically
- **python**: Python best practices, typing, async patterns

### 3. Check Plan Status

Review current plans in the pipeline:
```bash
uv run python .orchestrator/run.py list
```

Plan states:
- `pending/` - Awaiting build
- `in-progress/` - Currently building
- `completed/` - Successfully built
- `failed/` - Build failures
- `reviews/` - Review reports

### 4. System Architecture Summary

```
Workflows:
  plan   → Create implementation plans
  build  → Execute plans (write code)
  review → Review completed builds

Agents (19 total):
  Discovery: scout, analyzer, stack_detector
  Planning:  architect, planner, decomposer, validator
  Execution: builder, coordinator, parser, integrator, synthesizer
  Testing:   tester
  Review:    reviewer, compliance_checker, standards_checker, report_generator

Agent Modes:
  Print Mode (read-only): scout, architect, planner, analyzer...
  Agentic Mode (writes):  builder, tester, integrator
```

## Quick Reference

```bash
# Create a plan
uv run python .orchestrator/run.py plan "Add feature X"

# Build a plan
uv run python .orchestrator/run.py build .specs/pending/feature-x.md

# Review a build
uv run python .orchestrator/run.py review .specs/completed/feature-x.md --refresh-docs

# List all
uv run python .orchestrator/run.py list
```

## AI Docs Coverage

Cached documentation for agents:
- Claude Code SDK (headless, Python, TypeScript)
- Claude Code features (sub-agents, MCP, hooks, slash-commands)
- Python: uv, Pydantic, FastAPI
- TypeScript: Zod, React, Next.js
