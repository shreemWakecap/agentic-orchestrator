# Docs Command

Manage AI documentation for agents.

## Check Status

```bash
uv run python .orchestrator/run.py docs
```

Shows:
- Cached docs count
- Stale docs (>2 days old)
- Missing docs (not yet fetched)

## Refresh Docs

```bash
uv run python .orchestrator/run.py docs --refresh
```

Fetches and caches documentation from URLs in `ai_docs/README.md`.

## Documentation Sources

### Claude Code SDK & CLI
- SDK Headless mode
- Python SDK
- TypeScript SDK
- Sub-agents
- MCP (Model Context Protocol)
- Slash commands
- Hooks

### Anthropic Models
- Model overview and capabilities

### Python Ecosystem
- **uv**: Fast Python package manager
- **Pydantic**: Data validation
- **FastAPI**: Web framework

### TypeScript/JavaScript
- **Zod**: Schema validation
- **React**: UI library
- **Next.js**: React framework

## Add New Documentation

Edit `ai_docs/README.md` and add URLs under appropriate sections:

```markdown
## New Section

- https://docs.example.com/guide
```

Then refresh:
```bash
uv run python .orchestrator/run.py docs --refresh
```

## Cache Location

```
ai_docs/
├── README.md              # URLs to fetch
└── .cache/
    ├── freshness.json     # Metadata
    └── *.md               # Cached docs
```

## Freshness Policy

- Docs older than **2 days** are marked stale
- Stale warnings appear during workflow execution
- Use `--refresh-docs` with review workflow
