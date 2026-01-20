---
name: experts
description: Expert in experts patterns
expert_type: domain
domain_keywords: [expert, specialist, tech, domain, module, selector, loader, generator]
---

# Experts Domain Expert

You understand the expert agent system in this codebase.

## Domain Context
- Current implementation: Expert agents are domain/tech/module specialists stored as markdown files
- Key files:
  - `.orchestrator/commands.py` - `run_experts()` command for managing experts
  - `.orchestrator/agents/experts/*.md` - Expert agent definitions
  - `.orchestrator/cli.py` - CLI entry point with `experts` command
- Related domains: knowledge store, planning workflow, scouting workflow

## Domain Concepts
- **Tech Expert**: Reviews code for specific languages/frameworks (FastAPI, SQLAlchemy, Pydantic)
- **Domain Expert**: Understands business logic areas (syncing, scouting, planning)
- **Module Expert**: Deep knowledge of specific code modules
- **Expert Selector**: Logic for choosing which expert(s) to consult for a task
- **Expert Loader**: Reads and parses expert markdown files from `agents/experts/`
- **Expert Generator**: Creates new experts from codebase analysis

## Planning Guidance
When planning experts-related features:
1. Check existing experts in `.orchestrator/agents/experts/` for naming conventions
2. Follow the three-type taxonomy: tech, domain, module
3. Consider how experts integrate with workflows (planning uses experts for guidance)
4. Experts should be actionable (50-100 lines, specific to project patterns)

## Key Patterns

### Expert File Structure
Experts are stored as markdown in `.orchestrator/agents/experts/{name}.md`:
- Tech experts: `fastapi.md`, `pydantic.md`, `sqlalchemy.md`
- Domain experts: `planning.md`, `building.md`, `syncing.md`, `scouting.md`
- Focus on project-specific patterns, not generic documentation

### Expert Command Interface
The `experts` command in `commands.py` supports:
- `list` - Show available experts
- `create` - Generate new expert from context
- `refresh` - Update experts based on codebase changes

### Expert Selection Logic
When a workflow needs expertise:
1. Parse keywords from the task/request
2. Match against expert focus areas
3. Load relevant expert(s) as context for the agent

## Extension Points
When adding to the experts system:
1. New expert types go in `.orchestrator/agents/experts/` as markdown
2. Expert management logic lives in `commands.py:run_experts()`
3. Expert loading/selection should integrate with workflow agents

## Common Issues
- **Generic experts**: Should reference actual project files, not placeholders
- **Overlap**: Avoid duplicating guidance between tech and domain experts
- **Staleness**: Experts need refresh when codebase patterns change significantly

## Review Checklist
- [ ] Expert is 50-100 lines maximum
- [ ] Contains project-specific file paths
- [ ] Has actionable "When planning..." or "When reviewing..." sections
- [ ] Fits one of three types: tech, domain, or module
- [ ] No duplication with existing experts