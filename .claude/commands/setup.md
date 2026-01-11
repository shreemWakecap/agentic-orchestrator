# Setup Command

Initialize the SDLC Orchestrator environment.

## Steps

### 1. Verify Prerequisites

Check that required tools are installed:
- Claude Code CLI (`claude --version`)
- Python 3.11+ (`python --version`)
- UV package manager (`uv --version`)

### 2. Install Dependencies

```bash
cd .orchestrator && uv sync
```

### 3. Create Spec Directories

Ensure the plan lifecycle directories exist:
```bash
mkdir -p .specs/pending .specs/in-progress .specs/completed .specs/failed .specs/reviews
```

### 4. Load AI Documentation

Check and refresh AI docs for agents:
```bash
uv run python .orchestrator/run.py docs --refresh
```

This fetches documentation from URLs listed in `ai_docs/README.md`:
- Claude Code SDK & CLI docs
- Python ecosystem (uv, Pydantic, FastAPI)
- TypeScript/JavaScript ecosystem (Zod, React, Next.js)

### 5. Verify Setup

Run a quick check:
```bash
uv run python .orchestrator/run.py list
uv run python .orchestrator/run.py experts
uv run python .orchestrator/run.py docs
```

## Output

After setup, you should see:
- All dependencies installed
- `.specs/` directories created
- AI docs cached and fresh
- Experts available (python, meta)

## Next Steps

Run `/prime` to load full system context, or start with:
```bash
uv run python .orchestrator/run.py plan "Your feature request"
```
