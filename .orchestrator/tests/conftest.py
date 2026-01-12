"""
Shared pytest fixtures for SDLC Orchestrator tests.

Provides:
- project_root: Isolated project directory with required structure
- mock_agent_runner: Mock agent execution for deterministic tests
- Sample fixtures for plans and reviews
"""
import json
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional
from unittest.mock import MagicMock

import pytest

# Set up paths for proper imports
# Tests are inside .orchestrator/tests/
ORCHESTRATOR_DIR = Path(__file__).parent.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

# Add orchestrator dir to path for imports (workflows use absolute imports from here)
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """
    Create isolated project directory with required structure.

    Creates:
    - .orchestrator/specs/ directories (pending, in-progress, completed, failed, reviews, fixes)
    - .orchestrator/agents/ with agent definitions copied from real project
    - .orchestrator/docs/ directory
    """
    # Create .orchestrator directory structure
    orchestrator_dir = tmp_path / ".orchestrator"

    # Create specs directories
    specs_dirs = ["pending", "in-progress", "completed", "failed", "reviews", "fixes"]
    for d in specs_dirs:
        (orchestrator_dir / "specs" / d).mkdir(parents=True, exist_ok=True)

    # Create agents directory
    agents_dir = orchestrator_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Create experts directory
    experts_dir = agents_dir / "experts"
    experts_dir.mkdir(parents=True, exist_ok=True)

    # Copy agent definitions from real project
    real_agents = PROJECT_ROOT / ".orchestrator" / "agents"
    if real_agents.exists():
        for agent_file in real_agents.glob("*.md"):
            shutil.copy(agent_file, agents_dir)
        # Copy experts too
        real_experts = real_agents / "experts"
        if real_experts.exists():
            for expert_file in real_experts.glob("*.md"):
                shutil.copy(expert_file, experts_dir)

    # Create docs directory
    (orchestrator_dir / "docs").mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture
def mock_agent_result():
    """Factory for creating mock AgentResult objects."""
    from core.agent import AgentResult

    def _create(
        content: str = "Mock response",
        agent_name: str = "mock",
        success: bool = True,
        files_created: list = None,
        files_modified: list = None,
        tokens_used: int = 100,
        error: str = None,
    ) -> AgentResult:
        return AgentResult(
            content=content,
            agent_name=agent_name,
            success=success,
            files_created=files_created or [],
            files_modified=files_modified or [],
            commands_run=[],
            tokens_used=tokens_used,
            error=error,
        )

    return _create


@pytest.fixture
def mock_agent_runner(mock_agent_result):
    """
    Mock agent execution for deterministic tests.

    Usage:
        responses = {
            "analyzer": json.dumps({"complexity": "simple"}),
            "scout": "Found: src/, tests/",
        }
        with patch.object(Workflow, 'run_agent', mock_agent_runner(responses)):
            ...
    """

    def _create_mock(responses: dict[str, str]) -> Callable:
        def mock_run(
            self_or_name,
            message_or_name: str = None,
            context: Optional[str] = None,
            show_progress: bool = True,
        ):
            # Handle both bound method call and direct call patterns
            if isinstance(self_or_name, str):
                agent_name = self_or_name
            else:
                agent_name = message_or_name

            response = responses.get(agent_name, "Mock response")
            return mock_agent_result(
                content=response,
                agent_name=agent_name,
                success=True,
                tokens_used=100,
            )

        return mock_run

    return _create_mock


@pytest.fixture
def sample_simple_plan() -> str:
    """Sample simple plan content for testing."""
    return """# Simple Feature Plan

## Overview
Add a simple utility function to the codebase.

## Phase 1: Implementation
### Step 1.1: Create utility file
- Create `src/utils.py` with helper functions

### Step 1.2: Add main function
- Add the main utility function

## Phase 2: Testing
### Step 2.1: Add tests
- Create tests for the utility function

## Validation
- Run: python -m pytest tests/
- Check: src/utils.py exists
"""


@pytest.fixture
def sample_complex_plan() -> str:
    """Sample complex plan content for testing."""
    return """# Complex Feature Plan: User Authentication

## Overview
Implement complete user authentication system with login, registration, and session management.

## Sub-Features
1. User Registration
2. Login/Logout
3. Session Management
4. Password Reset

## Phase 1: Database Setup
### Step 1.1: Create user model
- Create `src/models/user.py` with User class
- Add fields: id, email, password_hash, created_at

### Step 1.2: Create session model
- Create `src/models/session.py` with Session class

## Phase 2: Authentication Logic
### Step 2.1: Create auth service
- Create `src/services/auth.py` with authentication logic

### Step 2.2: Add password hashing
- Implement secure password hashing

## Phase 3: API Endpoints
### Step 3.1: Register endpoint
- Create POST /auth/register

### Step 3.2: Login endpoint
- Create POST /auth/login

### Step 3.3: Logout endpoint
- Create POST /auth/logout

## Validation
- Run: python -m pytest tests/
- Test: curl -X POST /auth/register
"""


@pytest.fixture
def sample_review_report() -> str:
    """Sample review report content for testing."""
    return """# Review Report: test-feature

> Generated: 2024-01-15 10:00
> Status: **NEEDS_WORK**

## Executive Summary

| Metric | Score |
|--------|-------|
| Overall | 72/100 |
| Compliance | 85/100 |
| Standards | 70/100 |
| Expert Avg | 65/100 |

## Compliance Check

Score: 85/100

Issues:
- Missing error handling in user service
- No input validation on registration endpoint

## Expert Reviews

- **python**: 65/100 (3 issues)
  - Missing type hints
  - No docstrings
  - Inconsistent naming

## Standards Check

Score: 70/100

Issues:
- Critical: SQL injection vulnerability in query
- High: Passwords stored in plain text
- Medium: No rate limiting on login endpoint

## Recommendations

1. Add input validation using pydantic
2. Implement password hashing with bcrypt
3. Add rate limiting to prevent brute force
4. Add comprehensive error handling

---
*Generated by SDLC Orchestrator Review Workflow*
"""


@pytest.fixture
def pending_plan(project_root: Path, sample_simple_plan: str) -> Path:
    """Create a plan file in the pending directory."""
    plan_path = project_root / ".orchestrator" / "specs" / "pending" / "test_plan.md"
    plan_path.write_text(sample_simple_plan, encoding="utf-8")
    return plan_path


@pytest.fixture
def completed_plan(project_root: Path, sample_simple_plan: str) -> Path:
    """Create a plan file in the completed directory."""
    plan_path = project_root / ".orchestrator" / "specs" / "completed" / "test_feature.md"
    plan_path.write_text(sample_simple_plan, encoding="utf-8")

    # Create some source files to review
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "main.py").write_text(
        'def hello():\n    """Say hello."""\n    print("Hello")\n',
        encoding="utf-8",
    )
    (src_dir / "utils.py").write_text(
        'def helper():\n    """Helper function."""\n    pass\n',
        encoding="utf-8",
    )

    return plan_path


@pytest.fixture
def review_report(project_root: Path, sample_review_report: str) -> Path:
    """Create a review report file."""
    review_path = project_root / ".orchestrator" / "specs" / "reviews" / "review-test-feature.md"
    review_path.write_text(sample_review_report, encoding="utf-8")
    return review_path


@pytest.fixture
def mock_subprocess_success(monkeypatch):
    """Mock subprocess.run to return success."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"result": "success"}'
    mock_result.stderr = ""

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    return mock_result


@pytest.fixture
def mock_subprocess_failure(monkeypatch):
    """Mock subprocess.run to return failure."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Error: Command failed"

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr("subprocess.run", mock_run)
    return mock_result
