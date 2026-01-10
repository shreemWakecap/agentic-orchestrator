# SDLC Orchestrator

A workflow system that orchestrates multiple Claude agents for software development.

## Running Workflows

```bash
# Planning workflow
uv run python scripts/plan.py "Add user authentication"

# Output goes to .specs/
```

## Structure

- `.orchestrator/` - Workflow code (Python)
- `.specs/` - Generated plans
- `scripts/` - Runner scripts

## Engineering Rules

### Read files completely
- When reading a file, read ALL of it
- Use chunks for large files

### Use UV for Python
- Always `uv run python ...`
- Never raw python

### Git discipline
- Do NOT commit unless asked
