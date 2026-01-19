"""Pytest fixtures for orchestrator tests.

This module provides fixtures that enable testing without a real database
by using dependency injection overrides.
"""
import pytest
from typing import Dict, List, Optional
from fastapi.testclient import TestClient


# ============== Mock Repositories ==============


class MockPlanRepository:
    """Mock plan repository for testing."""

    def __init__(self):
        self.plans: Dict[str, Dict] = {}
        self._next_id = 1

    def get_by_id(self, plan_id: str) -> Optional[Dict]:
        return self.plans.get(plan_id)

    def list_all(self) -> List[Dict]:
        return list(self.plans.values())

    def list_by_status(self, status: str) -> List[Dict]:
        return [p for p in self.plans.values() if p.get("status") == status]

    def create(self, plan_id: str, **kwargs) -> int:
        self.plans[plan_id] = {
            "plan_id": plan_id,
            "status": kwargs.get("status", "pending"),
            "raw_content": kwargs.get("raw_content", ""),
            "request": kwargs.get("request", ""),
            "goal": kwargs.get("goal", ""),
            **kwargs,
        }
        self._next_id += 1
        return self._next_id - 1

    def update_status(self, plan_id: str, status: str) -> None:
        if plan_id in self.plans:
            self.plans[plan_id]["status"] = status

    def delete(self, plan_id: str) -> None:
        if plan_id in self.plans:
            del self.plans[plan_id]

    def get_next_plan_number(self) -> int:
        return self._next_id


class MockBuildStateRepository:
    """Mock build state repository for testing."""

    def __init__(self):
        self.states: Dict[str, Dict] = {}
        self.step_states: Dict[str, List[Dict]] = {}

    def get(self, plan_id: str) -> Optional[Dict]:
        return self.states.get(plan_id)

    def create(self, plan_id: str, total_steps: int = 0) -> int:
        self.states[plan_id] = {
            "plan_id": plan_id,
            "status": "pending",
            "total_steps": total_steps,
            "completed_steps": [],
            "failed_steps": [],
            "files_created": [],
            "files_modified": [],
        }
        self.step_states[plan_id] = []
        return 1

    def update(self, plan_id: str, **kwargs) -> None:
        if plan_id in self.states:
            self.states[plan_id].update(kwargs)

    def get_step_states(self, plan_id: str) -> List[Dict]:
        return self.step_states.get(plan_id, [])

    def set_step_state(self, plan_id: str, step_id: str, **kwargs) -> None:
        if plan_id not in self.step_states:
            self.step_states[plan_id] = []

        # Update existing or add new
        for state in self.step_states[plan_id]:
            if state.get("step_id") == step_id:
                state.update(kwargs)
                return

        self.step_states[plan_id].append({"step_id": step_id, **kwargs})


class MockRunRepository:
    """Mock run repository for testing."""

    def __init__(self):
        self.runs: Dict[str, Dict] = {}
        self.events: Dict[str, List[Dict]] = {}

    def get(self, run_id: str) -> Optional[Dict]:
        return self.runs.get(run_id)

    def list_active(self, status: str = None) -> List[Dict]:
        runs = list(self.runs.values())
        if status:
            runs = [r for r in runs if r.get("status") == status]
        return runs

    def create(self, run_id: str, workflow: str, **kwargs) -> None:
        self.runs[run_id] = {
            "run_id": run_id,
            "workflow": workflow,
            "status": "pending",
            **kwargs,
        }
        self.events[run_id] = []

    def update(self, run_id: str, **kwargs) -> None:
        if run_id in self.runs:
            self.runs[run_id].update(kwargs)

    def add_event(self, run_id: str, event_type: str, data: Dict = None) -> None:
        if run_id not in self.events:
            self.events[run_id] = []
        self.events[run_id].append({
            "id": len(self.events[run_id]) + 1,
            "event_type": event_type,
            "data": data or {},
        })

    def get_events(self, run_id: str, since_id: int = 0) -> List[Dict]:
        events = self.events.get(run_id, [])
        return [e for e in events if e.get("id", 0) > since_id]


# ============== Fixtures ==============


@pytest.fixture
def mock_plan_repo():
    """Create a mock plan repository."""
    return MockPlanRepository()


@pytest.fixture
def mock_build_state_repo():
    """Create a mock build state repository."""
    return MockBuildStateRepository()


@pytest.fixture
def mock_run_repo():
    """Create a mock run repository."""
    return MockRunRepository()


@pytest.fixture
def test_client(mock_plan_repo, mock_build_state_repo, mock_run_repo):
    """Create a test client with mocked dependencies.

    This fixture overrides the dependency injection to use mock
    repositories instead of the real database.
    """
    import sys
    from pathlib import Path

    # Add orchestrator to path
    orchestrator_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(orchestrator_dir))

    from portal.app import app
    from portal.dependencies import get_plan_repo, get_build_state_repo, get_run_repo

    # Override dependencies
    app.dependency_overrides[get_plan_repo] = lambda: mock_plan_repo
    app.dependency_overrides[get_build_state_repo] = lambda: mock_build_state_repo
    app.dependency_overrides[get_run_repo] = lambda: mock_run_repo

    client = TestClient(app)
    yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def sample_plan(mock_plan_repo):
    """Create a sample plan in the mock repository."""
    mock_plan_repo.create(
        plan_id="001_test_plan",
        status="pending",
        raw_content="# Plan: Test Plan\n\nRequest: Test request\n\nComplexity: low",
        request="Test request",
        goal="Test goal",
    )
    return "001_test_plan"


@pytest.fixture
def sample_run(mock_run_repo):
    """Create a sample run in the mock repository."""
    mock_run_repo.create(
        run_id="test123",
        workflow="planning",
        status="running",
    )
    return "test123"


# ============================================================================
# Job Management System Fixtures (Step 14)
# ============================================================================

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Add orchestrator to path for imports
orchestrator_dir = Path(__file__).parent.parent
sys.path.insert(0, str(orchestrator_dir))


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a fresh database engine for each test.

    Uses StaticPool to ensure all connections share the same in-memory database.
    This is required for SQLite in-memory databases to work correctly across
    multiple sessions/connections.
    """
    from portal.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session
        await session.rollback()


# ============================================================================
# Service Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def job_service(db_session):
    """Create a JobService instance."""
    from portal.services import JobService
    return JobService(db_session)


@pytest_asyncio.fixture
async def worker_pool(db_engine, monkeypatch):
    """Create a worker pool for testing with mocked database."""
    from portal.services import WorkerPool
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    # Create a session maker for the test database
    test_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Patch the async_session_maker in the worker_pool module
    monkeypatch.setattr(
        "portal.services.worker_pool.async_session_maker",
        test_session_maker
    )

    pool = WorkerPool(max_workers=2, max_queue_size=10)

    async def mock_executor(job_id: str):
        await asyncio.sleep(0.1)

    pool.set_executor(mock_executor)
    await pool.start()

    yield pool

    await pool.shutdown()


@pytest_asyncio.fixture
async def event_collector(db_engine, monkeypatch):
    """Create an event collector for testing with mocked database."""
    from portal.services import EventCollector
    from portal import models
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    # Create a session maker for the test database
    test_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Patch the async_session_maker in the event_collector module
    monkeypatch.setattr(
        "portal.services.event_collector.async_session_maker",
        test_session_maker
    )

    collector = EventCollector(batch_size=5, flush_interval=0.5)
    await collector.start()

    yield collector

    await collector.stop()


@pytest_asyncio.fixture
async def jsonl_parser():
    """Create a JSONLParser instance."""
    from portal.services import JSONLParser
    return JSONLParser()


# ============================================================================
# Test Data Factories
# ============================================================================

@pytest.fixture
def job_factory(db_session):
    """Factory for creating test jobs."""
    from portal.models import Job, JobStatus, JobType
    import uuid

    async def create_job(**kwargs):
        defaults = {
            "id": uuid.uuid4().hex,
            "job_type": JobType.PLAN,
            "status": JobStatus.PENDING,
            "parameters": {"spec_id": "test-001"},
        }
        defaults.update(kwargs)
        job = Job(**defaults)
        db_session.add(job)
        await db_session.flush()
        return job

    return create_job


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def job_api_client(db_engine, monkeypatch):
    """Create a test client for the job management API using portal.main with lifespan."""
    from httpx import AsyncClient, ASGITransport
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    # Patch database session makers in modules that import async_session_maker
    test_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Patch the engine in base module (used by init_db and close_db)
    monkeypatch.setattr("portal.models.base.engine", db_engine)

    # Patch async_session_maker in all modules that import it at module level
    monkeypatch.setattr("portal.models.base.async_session_maker", test_session_maker)
    monkeypatch.setattr("portal.models.async_session_maker", test_session_maker)
    monkeypatch.setattr("portal.services.event_collector.async_session_maker", test_session_maker)
    monkeypatch.setattr("portal.services.worker_pool.async_session_maker", test_session_maker)
    monkeypatch.setattr("portal.streaming.sse.async_session_maker", test_session_maker)
    monkeypatch.setattr("portal.lifecycle.async_session_maker", test_session_maker)
    monkeypatch.setattr("portal.api.jobs.async_session_maker", test_session_maker)

    # Patch init_db to be a no-op since db_engine fixture already created tables
    async def noop_init_db():
        pass

    monkeypatch.setattr("portal.models.base.init_db", noop_init_db)
    monkeypatch.setattr("portal.models.init_db", noop_init_db)
    monkeypatch.setattr("portal.lifecycle.init_db", noop_init_db)

    # Import app after patching
    from portal.main import app

    # Use the app's lifespan context to properly start/stop services
    async with app.router.lifespan_context(app) as state:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


@pytest.fixture
def mock_cli_output():
    """Sample CLI JSONL output for testing."""
    return [
        '{"type":"start","phase":"init","ts":"2025-01-19T10:30:00Z"}',
        '{"type":"progress","phase":"analyzing","percent":25,"message":"Working...","ts":"2025-01-19T10:30:15Z"}',
        '{"type":"log","level":"info","message":"Found 5 items","ts":"2025-01-19T10:30:16Z"}',
        '{"type":"checkpoint","id":"chk_001","phase":"analyzing","percent":25,"state":{"items":5},"ts":"2025-01-19T10:30:20Z"}',
        '{"type":"progress","phase":"generating","percent":75,"ts":"2025-01-19T10:31:00Z"}',
        '{"type":"complete","exit_code":0,"result":{"files":10},"ts":"2025-01-19T10:33:00Z"}',
    ]
