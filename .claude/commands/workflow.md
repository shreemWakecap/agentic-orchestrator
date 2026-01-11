# Workflow

Three workflows: **plan → build → review**

## Plan
```bash
uv run python .orchestrator/run.py plan "Add feature X"
```
Output: `.specs/pending/feature-x.md`

## Build
```bash
uv run python .orchestrator/run.py build .specs/pending/feature-x.md
```
Output: Code written + `.specs/completed/feature-x.md`

## Review
```bash
uv run python .orchestrator/run.py review .specs/completed/feature-x.md --refresh-docs
```
Output: `.specs/reviews/feature-x-review.md`

## Utils
```bash
uv run python .orchestrator/run.py list      # all plans
uv run python .orchestrator/run.py docs      # ai docs status
uv run python .orchestrator/run.py experts   # available experts
```
