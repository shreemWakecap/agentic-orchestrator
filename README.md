# SDLC Orchestrator

AI-powered software development lifecycle automation.

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  PLAN   │ ─► │  BUILD  │ ─► │ REVIEW  │ ─► │   FIX   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

## Quick Start

```bash
.\.orchestrator\setup.ps1                    # Setup
uv run python .orchestrator/cli.py <command> # Run
```

## CLI Commands

```
┌────────────────────────────────────────────────────────────┐
│  cli.py <command> [args]                                   │
├────────────┬───────────────────────────────────────────────┤
│  setup     │  Initialize environment, fetch docs           │
│  plan      │  Create implementation plan                   │
│  build     │  Execute plan, write code                     │
│  review    │  Review completed build                       │
│  fix       │  Auto-fix issues from review                  │
│  list      │  List all plans by status                     │
│  docs      │  Check/refresh AI documentation               │
│  experts   │  Manage expert agents                         │
│  cost      │  Cost estimation & budgets                    │
│  test      │  Run test suite                               │
│  portal    │  Start management portal                      │
└────────────┴───────────────────────────────────────────────┘
```

### Workflow Example

```bash
cli.py plan "Add JWT authentication"
cli.py build .orchestrator/specs/pending/jwt-authentication.md
cli.py review .orchestrator/specs/completed/jwt-authentication.md
cli.py fix .orchestrator/specs/reviews/review-jwt-authentication.md
```

### Expert Management

```bash
cli.py experts list
cli.py experts create auth --type domain --keywords auth,login,jwt
cli.py experts create core-api --type module --module src/api
```

```
┌─────────────────────────────────────────────────────────┐
│  Expert Types                                           │
├─────────────┬───────────────────────────────────────────┤
│  tech       │  Languages, frameworks (auto-detected)    │
│  domain     │  Business domains (consulted in planning) │
│  module     │  Project-specific modules                 │
└─────────────┴───────────────────────────────────────────┘
```

### Cost & Budget

```bash
cli.py cost estimate plan --request "Add auth"
cli.py cost report daily|weekly|monthly
cli.py cost budget set --daily 10.00 --monthly 100.00
```

## Workflows

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PLANNING                                                                   │
│                                                                             │
│    ┌───────┐   ┌───────────┐   ┌─────────────────────┐   ┌─────────┐       │
│    │ Scout │ ─►│ Architect │ ─►│ Expert Consultation │ ─►│ Planner │ ─► Plan│
│    └───────┘   └───────────┘   └─────────────────────┘   └─────────┘       │
│                                         │                                   │
│                              ┌──────────┴──────────┐                       │
│                              │ Domain/Module Experts│                       │
│                              └─────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  BUILDING                                                                   │
│                                                                             │
│    ┌────────┐   ┌───────────────────────┐   ┌────────┐   ┌──────────┐      │
│    │ Parser │ ─►│   Parallel Builders   │ ─►│ Tester │ ─►│ Reviewer │      │
│    └────────┘   │  ┌─────┐ ┌─────┐     │   └────────┘   └──────────┘      │
│                 │  │ B1  │ │ B2  │ ... │                                   │
│                 │  └─────┘ └─────┘     │                                   │
│                 └───────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  REVIEWING                                                                  │
│                                                                             │
│    ┌───────────┐   ┌────────────┐   ┌────────────────┐   ┌────────┐        │
│    │ Stack     │ ─►│ Compliance │ ─►│ Expert Reviews │ ─►│ Report │        │
│    │ Detector  │   │ Checker    │   │ (parallel)     │   │        │        │
│    └───────────┘   └────────────┘   └────────────────┘   └────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Plan Lifecycle

```
                    .orchestrator/specs/
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   ┌─────────┐   ┌─────────────┐   ┌───────────┐    │
    │   │ pending │ ─►│ in-progress │ ─►│ completed │    │
    │   └─────────┘   └─────────────┘   └─────┬─────┘    │
    │        │                                │          │
    │        │ plan                    review │          │
    │        ▼                                ▼          │
    │   ┌─────────┐                    ┌──────────┐      │
    │   │ failed  │                    │ reviews/ │      │
    │   └─────────┘                    └──────────┘      │
    │                                                     │
    └─────────────────────────────────────────────────────┘
```

## Project Structure

```
project/
│
├── .orchestrator/              ◄── Single encapsulated folder
│   ├── cli.py                      Entry point
│   ├── setup.ps1                   Setup script
│   │
│   ├── workflows/                  Workflow engines
│   │   ├── planning.py
│   │   ├── building.py
│   │   ├── reviewing.py
│   │   └── fixing.py
│   │
│   ├── core/                       Core modules
│   │   ├── agent.py                Agent executor
│   │   ├── workflow.py             Base workflow
│   │   ├── docs_loader.py          Documentation loader
│   │   ├── expert_loader.py        Expert management
│   │   └── cost.py                 Cost tracking
│   │
│   ├── server/                     Portal backend
│   │   └── app.py
│   │
│   ├── agents/                     AI agent definitions
│   │   ├── scout.md
│   │   ├── architect.md
│   │   ├── planner.md
│   │   ├── builder.md
│   │   ├── reviewer.md
│   │   └── experts/                Tech/Domain/Module experts
│   │       ├── python.md
│   │       └── ...
│   │
│   ├── specs/                      Plan lifecycle
│   │   ├── pending/
│   │   ├── in-progress/
│   │   ├── completed/
│   │   ├── failed/
│   │   ├── reviews/
│   │   └── fixes/
│   │
│   ├── docs/                       Cached AI documentation
│   │   └── README.md               URLs to fetch
│   │
│   ├── config/                     Configuration
│   │   └── budget.json
│   │
│   └── tests/                      Test suite
│
└── src/                        ◄── Your project source code
```

## Requirements

```
┌────────────────────────────────────────────────────────────┐
│  Claude Code CLI    npm i -g @anthropic-ai/claude-code     │
│  Python 3.11+                                              │
│  UV                 (auto-installed via setup.ps1)         │
└────────────────────────────────────────────────────────────┘
```

---

## Roadmap: Python Package Distribution

### Overview

Package the orchestrator for distribution via PyPI, enabling installation with:

```bash
pip install sdlc-orchestrator
sdlc-orchestrator init     # Initialize in current project
sdlc-orchestrator plan "Add feature"
```

### Implementation Steps

#### 1. Package Structure

```
sdlc-orchestrator/
├── pyproject.toml              # Package metadata & build config
├── src/
│   └── sdlc_orchestrator/      # Main package
│       ├── __init__.py
│       ├── __main__.py         # CLI entry point
│       ├── cli.py
│       ├── core/
│       ├── workflows/
│       ├── server/
│       └── data/               # Bundled agents & templates
│           ├── agents/
│           │   ├── scout.md
│           │   └── experts/
│           └── templates/
│               └── docs_readme.md
└── tests/
```

#### 2. pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sdlc-orchestrator"
version = "0.1.0"
description = "AI-powered SDLC automation with Claude Code"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [{ name = "Your Name", email = "you@example.com" }]
keywords = ["ai", "sdlc", "automation", "claude", "development"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Build Tools",
]
dependencies = [
    "httpx>=0.25.0",
    "rich>=13.0.0",
    "pyyaml>=6.0",
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "ruff>=0.1.0"]

[project.scripts]
sdlc-orchestrator = "sdlc_orchestrator.cli:main"

[project.urls]
Homepage = "https://github.com/yourusername/sdlc-orchestrator"
Documentation = "https://github.com/yourusername/sdlc-orchestrator#readme"
Repository = "https://github.com/yourusername/sdlc-orchestrator.git"
Issues = "https://github.com/yourusername/sdlc-orchestrator/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/sdlc_orchestrator"]

[tool.hatch.build.targets.wheel.shared-data]
"src/sdlc_orchestrator/data" = "share/sdlc-orchestrator"
```

#### 3. CLI Entry Point (`__main__.py`)

```python
"""Allow running as: python -m sdlc_orchestrator"""
from sdlc_orchestrator.cli import main

if __name__ == "__main__":
    main()
```

#### 4. Init Command

New `init` command to bootstrap orchestrator in any project:

```python
def cmd_init():
    """Initialize SDLC orchestrator in current directory."""
    project_root = Path.cwd()
    orchestrator_dir = project_root / ".orchestrator"

    if orchestrator_dir.exists():
        print("Already initialized")
        return

    # Create directory structure
    dirs = ["specs/pending", "specs/in-progress", "specs/completed",
            "specs/reviews", "specs/fixes", "agents/experts", "docs", "config"]
    for d in dirs:
        (orchestrator_dir / d).mkdir(parents=True, exist_ok=True)

    # Copy bundled agents from package data
    package_data = importlib.resources.files("sdlc_orchestrator.data")

    # Copy agents
    for agent_file in (package_data / "agents").iterdir():
        if agent_file.name.endswith(".md"):
            content = agent_file.read_text()
            (orchestrator_dir / "agents" / agent_file.name).write_text(content)

    # Copy expert templates
    experts_src = package_data / "agents" / "experts"
    for expert_file in experts_src.iterdir():
        if expert_file.name.endswith(".md"):
            content = expert_file.read_text()
            (orchestrator_dir / "agents" / "experts" / expert_file.name).write_text(content)

    # Create docs README template
    docs_template = (package_data / "templates" / "docs_readme.md").read_text()
    (orchestrator_dir / "docs" / "README.md").write_text(docs_template)

    print("Initialized .orchestrator/")
    print("Run: sdlc-orchestrator plan 'Your feature request'")
```

#### 5. GitHub Repository Setup

```
.github/
├── workflows/
│   ├── test.yml              # Run tests on PR
│   ├── publish.yml           # Publish to PyPI on release
│   └── docs.yml              # Build docs (optional)
└── ISSUE_TEMPLATE/
    ├── bug_report.md
    └── feature_request.md
```

**`.github/workflows/test.yml`:**

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: pytest tests/ -v

      - name: Lint
        run: ruff check src/
```

**`.github/workflows/publish.yml`:**

```yaml
name: Publish to PyPI
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # For trusted publishing

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install build tools
        run: pip install build

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Uses trusted publishing - no API token needed
        # Configure at: https://pypi.org/manage/project/.../settings/publishing/
```

#### 6. PyPI Trusted Publishing Setup

1. Create account at https://pypi.org
2. Go to: Account Settings > Publishing > Add a new pending publisher
3. Configure:
   - PyPI Project Name: `sdlc-orchestrator`
   - Owner: `yourusername`
   - Repository: `sdlc-orchestrator`
   - Workflow name: `publish.yml`
   - Environment: (leave blank)

#### 7. Release Process

```bash
# 1. Update version in pyproject.toml
# 2. Commit and tag
git add pyproject.toml
git commit -m "Bump version to 0.1.0"
git tag v0.1.0
git push origin main --tags

# 3. Create GitHub Release
gh release create v0.1.0 --title "v0.1.0" --notes "Initial release"

# 4. GitHub Actions automatically publishes to PyPI
```

#### 8. User Installation

```bash
# Install from PyPI
pip install sdlc-orchestrator

# Or with uv
uv pip install sdlc-orchestrator

# Initialize in project
cd your-project/
sdlc-orchestrator init

# Start using
sdlc-orchestrator plan "Add user authentication"
sdlc-orchestrator build .orchestrator/specs/pending/user-authentication.md
```

### Migration Checklist

- [ ] Restructure code into `src/sdlc_orchestrator/` layout
- [ ] Create `pyproject.toml` with metadata
- [ ] Bundle agent definitions in `data/` directory
- [ ] Add `init` command for project bootstrapping
- [ ] Update imports to use package-relative paths
- [ ] Set up GitHub Actions workflows
- [ ] Configure PyPI trusted publishing
- [ ] Create initial release

---

## License

MIT
