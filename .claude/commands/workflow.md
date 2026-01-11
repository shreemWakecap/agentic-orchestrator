# Workflow Command

Quick reference for SDLC workflows.

## Available Workflows

### 1. Plan Workflow

Create implementation plans from feature requests.

```bash
uv run python .orchestrator/run.py plan "Your feature description"
```

**Simple/Medium Features:**
```
Scout → Architect → Planner → Validator
```

**Complex Features:**
```
Analyzer → Decomposer → [Parallel Sub-Plans] → Synthesizer → Validator
```

Output: `.specs/pending/<feature-name>.md`

---

### 2. Build Workflow

Execute plans by writing actual code.

```bash
uv run python .orchestrator/run.py build .specs/pending/feature.md
```

**Simple Plans:**
```
Parser → Builder (per step) → Tester → Reviewer
```

**Complex Plans:**
```
Parser → Coordinator → [Parallel Builders] → Integrator → Tester → Reviewer
```

Output: Code written + `.specs/completed/<feature-name>.md`

---

### 3. Review Workflow

Review completed builds for quality.

```bash
uv run python .orchestrator/run.py review .specs/completed/feature.md
```

With fresh docs:
```bash
uv run python .orchestrator/run.py review .specs/completed/feature.md --refresh-docs
```

**Review Flow:**
```
Load AI Docs → Stack Detector → Compliance Checker →
[Parallel Expert Reviews] → Standards Checker → Report Generator
```

Output: `.specs/reviews/<feature-name>-review.md`

---

## Plan Lifecycle

```
pending/ → in-progress/ → completed/ → reviews/
                              ↓
                          failed/
```

## Utility Commands

```bash
# List all plans
uv run python .orchestrator/run.py list

# Check AI docs
uv run python .orchestrator/run.py docs

# Refresh AI docs
uv run python .orchestrator/run.py docs --refresh

# List experts
uv run python .orchestrator/run.py experts
```

## Agent Modes

| Mode | Capability | Agents |
|------|------------|--------|
| Print | Read-only analysis | scout, architect, planner, analyzer, parser, reviewer... |
| Agentic | Can write files | builder, tester, integrator |
