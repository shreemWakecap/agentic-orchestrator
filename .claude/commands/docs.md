# Docs

Manage AI documentation for agents.

```bash
# Check status
uv run python .orchestrator/run.py docs

# Refresh stale/missing
uv run python .orchestrator/run.py docs --refresh
```

## Add new docs

Edit `ai_docs/README.md`, add URL, then refresh.

## Sources

See `ai_docs/README.md` for full list:
- Claude Code SDK & CLI
- Python (uv, Pydantic, FastAPI)
- TypeScript (Zod, React, Next.js)
