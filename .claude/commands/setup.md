# Setup

Initialize the orchestrator. Run once.

```bash
# 1. Check prerequisites
claude --version
python --version
uv --version

# 2. Install deps
cd .orchestrator && uv sync && cd ..

# 3. Create directories
mkdir -p .specs/pending .specs/in-progress .specs/completed .specs/failed .specs/reviews

# 4. Load AI docs
uv run python .orchestrator/run.py docs --refresh

# 5. Verify
uv run python .orchestrator/run.py list
```

Then run `/prime` to get oriented.
