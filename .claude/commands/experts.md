# Experts Command

Manage tech-specific expert agents.

## List Experts

```bash
uv run python .orchestrator/run.py experts
```

## Available Experts

### meta-expert (`_meta.md`)
Creates and manages tech experts dynamically.

**Capabilities:**
- Detects technologies in a project
- Creates new expert agents on-the-fly
- Updates existing experts with project patterns
- Recommends which experts to use

### python (`python.md`)
Expert in Python best practices.

**Expertise:**
- Type hints and static typing (mypy, pyright)
- Async/await patterns
- Package management (uv, pip, poetry)
- Testing (pytest, unittest)
- Code quality (ruff, black, isort)
- Performance optimization
- Security best practices

## Create New Expert

1. Create file in `.claude/agents/experts/<tech>.md`:

```markdown
---
name: fastapi
description: Expert in FastAPI best practices
---

# FastAPI Expert

You are an expert in FastAPI with deep knowledge of...

## Review Checklist
- [ ] Async endpoints used correctly
- [ ] Dependency injection patterns
- [ ] Pydantic models for validation
- [ ] OpenAPI documentation

## Common Issues
- Missing response models
- Incorrect async usage
- Poor error handling

## Best Practices
- Use path operations correctly
- Leverage automatic validation
- Document endpoints
```

2. Expert auto-discovered when that tech is detected in project.

## Expert Usage

Experts are used in:
- **Planning**: Tech-specific architecture guidance
- **Building**: Implementation patterns
- **Reviewing**: Code quality checks (parallel expert reviews)

## Stack Detection

The `stack_detector` agent identifies:
- Languages (Python, TypeScript, JavaScript)
- Frameworks (FastAPI, React, Next.js)
- Tools (pytest, ruff, ESLint)

Then loads relevant experts for review.
