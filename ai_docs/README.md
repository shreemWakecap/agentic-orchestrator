# AI Docs

> Documentation resources for SDLC Orchestrator agents.
> Files are auto-fetched and cached. Stale docs (>2 days) trigger refresh warnings.

## Claude Code SDK & CLI

- https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-headless
- https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-python
- https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-typescript
- https://docs.anthropic.com/en/docs/claude-code/sub-agents
- https://docs.anthropic.com/en/docs/claude-code/mcp
- https://docs.anthropic.com/en/docs/claude-code/slash-commands
- https://docs.anthropic.com/en/docs/claude-code/hooks

## Anthropic Models

- https://docs.anthropic.com/en/docs/about-claude/models/overview

## Python Ecosystem

- https://docs.astral.sh/uv/guides/scripts/
- https://docs.astral.sh/uv/guides/projects/#managing-dependencies
- https://docs.pydantic.dev/latest/concepts/models/
- https://fastapi.tiangolo.com/tutorial/first-steps/

## TypeScript/JavaScript Ecosystem

- https://zod.dev/
- https://react.dev/reference/react
- https://nextjs.org/docs/getting-started

## Usage

```bash
# Check docs freshness
uv run python .orchestrator/cli.py docs

# Refresh stale/missing docs
uv run python .orchestrator/cli.py docs --refresh
```

## Freshness Policy

- Docs older than **2 days** are marked as stale
- Stale docs trigger warnings during workflow execution
- Use `--refresh-docs` flag to auto-refresh during review workflow
