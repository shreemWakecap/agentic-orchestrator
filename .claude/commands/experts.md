# Experts

Tech-specific expert agents for code review.

```bash
# List available
uv run python .orchestrator/run.py experts

# Check what's there
ls .claude/agents/experts/
```

## Current experts
- **meta-expert** - Creates new experts dynamically
- **python** - Python best practices

## Create new expert

Add `.claude/agents/experts/<tech>.md`:

```markdown
---
name: fastapi
description: Expert in FastAPI
---

# FastAPI Expert

You are an expert in FastAPI...

## Review Checklist
- Async endpoints
- Dependency injection
- Pydantic models
```

Auto-discovered when tech is detected.
