"""
SQLite Database Module for Orchestrator.

Provides:
- Thread-safe connection management
- Atomic transaction support
- Repository classes for each domain
- JSON helpers for complex fields
- Auto-initialize schema on first use
"""
import json
import sqlite3
import threading
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Generator

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONFIGURATION AND CORE CLASS
# =============================================================================

@dataclass
class DatabaseConfig:
    """Database configuration."""
    db_path: Path
    timeout: float = 30.0
    check_same_thread: bool = False  # Allow multi-thread access


class Database:
    """
    Thread-safe SQLite database manager.

    Usage:
        db = Database(project_root)

        # Single query
        with db.connection() as conn:
            cursor = conn.execute("SELECT * FROM plans WHERE status = ?", ("pending",))
            rows = cursor.fetchall()

        # Transaction
        with db.transaction() as conn:
            conn.execute("INSERT INTO plans ...")
            conn.execute("INSERT INTO plan_steps ...")
            # Auto-commits on success, auto-rollback on exception
    """

    _local = threading.local()
    _init_lock = threading.Lock()
    _initialized_paths: set = set()

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.db_path = self.project_root / ".orchestrator" / "orchestrator.db"
        self.config = DatabaseConfig(db_path=self.db_path)

        # Initialize database on first use for this path
        with self._init_lock:
            if str(self.db_path) not in Database._initialized_paths:
                self._init_database()
                Database._initialized_paths.add(str(self.db_path))

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        conn_key = f"connection_{self.db_path}"
        if not hasattr(self._local, conn_key) or getattr(self._local, conn_key) is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=self.config.timeout,
                check_same_thread=self.config.check_same_thread,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            setattr(self._local, conn_key, conn)
        return getattr(self._local, conn_key)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection (auto-managed)."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            pass  # Connection stays open for reuse

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Execute operations in a transaction.

        Auto-commits on success, auto-rollback on exception.
        """
        conn = self._get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self):
        """Close thread-local connection."""
        conn_key = f"connection_{self.db_path}"
        if hasattr(self._local, conn_key):
            conn = getattr(self._local, conn_key)
            if conn:
                conn.close()
            setattr(self._local, conn_key, None)

    def _init_database(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema = self._get_schema()

        # Use a fresh connection for initialization
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        try:
            conn.executescript(schema)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        finally:
            conn.close()

    def _get_schema(self) -> str:
        """Return embedded schema SQL."""
        return """
-- =====================================================
-- ORCHESTRATOR DATABASE SCHEMA v1.0
-- =====================================================

PRAGMA foreign_keys = ON;

-- =====================================================
-- PLANS DOMAIN
-- =====================================================

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    goal TEXT NOT NULL,
    request TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    context_json TEXT,
    verify_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'building', 'completed', 'failed', 'paused'))
);

CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_created_at ON plans(created_at DESC);

CREATE TABLE IF NOT EXISTS plan_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT 'Implementation',
    phase_number INTEGER NOT NULL DEFAULT 1,
    can_parallelize INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE,
    UNIQUE(plan_id, phase_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_phases_plan_id ON plan_phases(plan_id);

CREATE TABLE IF NOT EXISTS plan_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    description TEXT NOT NULL,
    done TEXT,
    inputs_json TEXT,
    needs_json TEXT,
    step_order INTEGER NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE,
    CONSTRAINT valid_action CHECK (action IN ('create', 'modify', 'delete', 'run')),
    UNIQUE(plan_id, step_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_steps_plan_id ON plan_steps(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_steps_phase_id ON plan_steps(plan_id, phase_id);

-- =====================================================
-- BUILD STATE DOMAIN
-- =====================================================

CREATE TABLE IF NOT EXISTS build_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    updated_at TEXT NOT NULL,
    current_phase INTEGER NOT NULL DEFAULT 0,
    current_step TEXT,
    total_steps INTEGER NOT NULL DEFAULT 0,
    completed_steps_json TEXT,
    failed_steps_json TEXT,
    skipped_steps_json TEXT,
    files_created_json TEXT,
    files_modified_json TEXT,
    last_error TEXT,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'building', 'completed', 'failed', 'paused'))
);

CREATE INDEX IF NOT EXISTS idx_build_states_status ON build_states(status);

CREATE TABLE IF NOT EXISTS step_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    files_affected_json TEXT,
    summary TEXT,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    UNIQUE(plan_id, step_id)
);

CREATE INDEX IF NOT EXISTS idx_step_states_plan_id ON step_states(plan_id);
CREATE INDEX IF NOT EXISTS idx_step_states_status ON step_states(status);

-- =====================================================
-- KNOWLEDGE STORE DOMAIN
-- =====================================================

CREATE TABLE IF NOT EXISTS codebase_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL DEFAULT '1.0',
    last_updated TEXT NOT NULL,
    project_name TEXT,
    project_type TEXT,
    primary_language TEXT,
    statistics_json TEXT
);

CREATE TABLE IF NOT EXISTS technologies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    tech_type TEXT NOT NULL,
    name TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    version TEXT,
    entry_point TEXT,
    config_file TEXT,
    FOREIGN KEY (knowledge_id) REFERENCES codebase_knowledge(id) ON DELETE CASCADE,
    CONSTRAINT valid_type CHECK (tech_type IN ('language', 'framework', 'tool'))
);

CREATE INDEX IF NOT EXISTS idx_technologies_knowledge_id ON technologies(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_technologies_type ON technologies(tech_type);

CREATE TABLE IF NOT EXISTS architecture_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER UNIQUE NOT NULL,
    pattern TEXT NOT NULL DEFAULT 'unknown',
    entry_points_json TEXT,
    FOREIGN KEY (knowledge_id) REFERENCES codebase_knowledge(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS architecture_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    purpose TEXT,
    depends_on_json TEXT,
    FOREIGN KEY (knowledge_id) REFERENCES codebase_knowledge(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_architecture_modules_knowledge_id ON architecture_modules(knowledge_id);

CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    keywords_json TEXT,
    files_json TEXT,
    models_json TEXT,
    routes_json TEXT,
    FOREIGN KEY (knowledge_id) REFERENCES codebase_knowledge(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_domains_knowledge_id ON domains(knowledge_id);

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER UNIQUE NOT NULL,
    naming_json TEXT,
    structure_json TEXT,
    conventions_json TEXT,
    FOREIGN KEY (knowledge_id) REFERENCES codebase_knowledge(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS expert_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL DEFAULT '1.0',
    last_updated TEXT NOT NULL,
    keyword_map_json TEXT,
    path_map_json TEXT
);

CREATE TABLE IF NOT EXISTS expert_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    expert_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    triggers_keywords_json TEXT,
    triggers_paths_json TEXT,
    triggers_topics_json TEXT,
    FOREIGN KEY (index_id) REFERENCES expert_index(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_expert_entries_index_id ON expert_entries(index_id);
CREATE INDEX IF NOT EXISTS idx_expert_entries_name ON expert_entries(name);

CREATE TABLE IF NOT EXISTS scan_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT UNIQUE NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL,
    files_scanned INTEGER NOT NULL DEFAULT 0,
    scan_type TEXT NOT NULL DEFAULT 'full',
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    experts_generated_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_metadata_started_at ON scan_metadata(started_at DESC);

-- =====================================================
-- COST TRACKING DOMAIN
-- =====================================================

CREATE TABLE IF NOT EXISTS cost_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow TEXT NOT NULL,
    run_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    total_tokens INTEGER NOT NULL,
    estimated_cost REAL NOT NULL,
    actual_cost REAL,
    agents_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cost_history_started_at ON cost_history(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_cost_history_workflow ON cost_history(workflow);

-- =====================================================
-- PORTAL / RUNS DOMAIN
-- =====================================================

CREATE TABLE IF NOT EXISTS active_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    workflow TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    plan_id TEXT,
    plan_path TEXT,
    description TEXT,
    progress INTEGER NOT NULL DEFAULT 0,
    current_step TEXT,
    output_file TEXT,
    error TEXT,
    total_tokens INTEGER,
    data_json TEXT,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_active_runs_status ON active_runs(status);
CREATE INDEX IF NOT EXISTS idx_active_runs_started_at ON active_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    data_json TEXT,
    FOREIGN KEY (run_id) REFERENCES active_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id);
CREATE INDEX IF NOT EXISTS idx_run_events_timestamp ON run_events(run_id, timestamp);
"""

    # ====================
    # JSON Helper Methods
    # ====================

    @staticmethod
    def to_json(value: Any) -> Optional[str]:
        """Convert Python value to JSON string for storage."""
        if value is None:
            return None
        return json.dumps(value)

    @staticmethod
    def from_json(value: Optional[str], default: Any = None) -> Any:
        """Parse JSON string from storage to Python value."""
        if value is None:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def row_to_dict(row: sqlite3.Row) -> dict:
        """Convert sqlite3.Row to dict."""
        return dict(zip(row.keys(), row))

    # ====================
    # Query Helpers
    # ====================

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor."""
        with self.connection() as conn:
            return conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute query and fetch one row as dict."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return self.row_to_dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute query and fetch all rows as dicts."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return [self.row_to_dict(row) for row in cursor.fetchall()]


# =============================================================================
# REPOSITORY CLASSES
# =============================================================================

class PlanRepository:
    """Repository for plan operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, plan_id: str, goal: str, request: str, raw_content: str,
               context: list[str] = None, verify: list[str] = None) -> int:
        """Create a new plan. Returns the row ID."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO plans (plan_id, goal, request, raw_content, context_json,
                                   verify_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, goal, request, raw_content,
                self.db.to_json(context or []),
                self.db.to_json(verify or []),
                now, now
            ))
            return cursor.lastrowid

    def get_by_id(self, plan_id: str) -> Optional[dict]:
        """Get plan by plan_id."""
        row = self.db.fetchone("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
        if row:
            row['context'] = self.db.from_json(row.get('context_json'), [])
            row['verify'] = self.db.from_json(row.get('verify_json'), [])
        return row

    def list_by_status(self, status: str) -> list[dict]:
        """List plans by status."""
        rows = self.db.fetchall(
            "SELECT * FROM plans WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
        for row in rows:
            row['context'] = self.db.from_json(row.get('context_json'), [])
            row['verify'] = self.db.from_json(row.get('verify_json'), [])
        return rows

    def list_all(self) -> list[dict]:
        """List all plans ordered by creation."""
        rows = self.db.fetchall("SELECT * FROM plans ORDER BY created_at DESC")
        for row in rows:
            row['context'] = self.db.from_json(row.get('context_json'), [])
            row['verify'] = self.db.from_json(row.get('verify_json'), [])
        return rows

    def update_status(self, plan_id: str, status: str):
        """Update plan status."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            if status == 'completed':
                conn.execute("""
                    UPDATE plans SET status = ?, updated_at = ?, completed_at = ?
                    WHERE plan_id = ?
                """, (status, now, now, plan_id))
            else:
                conn.execute("""
                    UPDATE plans SET status = ?, updated_at = ? WHERE plan_id = ?
                """, (status, now, plan_id))

    def delete(self, plan_id: str):
        """Delete a plan (cascades to steps, phases, build state)."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM plans WHERE plan_id = ?", (plan_id,))

    def add_phase(self, plan_id: str, phase_id: str, name: str,
                  phase_number: int, can_parallelize: bool = False):
        """Add a phase to a plan."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO plan_phases (plan_id, phase_id, name, phase_number, can_parallelize)
                VALUES (?, ?, ?, ?, ?)
            """, (plan_id, phase_id, name, phase_number, int(can_parallelize)))

    def add_step(self, plan_id: str, phase_id: str, step_id: str, action: str,
                 description: str, step_order: int, target: str = None,
                 done: str = None, inputs: list[str] = None, needs: list[str] = None):
        """Add a step to a plan."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO plan_steps (plan_id, phase_id, step_id, action, target,
                                       description, done, inputs_json, needs_json, step_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, phase_id, step_id, action, target, description, done,
                self.db.to_json(inputs or []),
                self.db.to_json(needs or []),
                step_order
            ))

    def get_steps(self, plan_id: str) -> list[dict]:
        """Get all steps for a plan."""
        rows = self.db.fetchall(
            "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_order",
            (plan_id,)
        )
        for row in rows:
            row['inputs'] = self.db.from_json(row.get('inputs_json'), [])
            row['needs'] = self.db.from_json(row.get('needs_json'), [])
        return rows

    def get_phases(self, plan_id: str) -> list[dict]:
        """Get all phases for a plan."""
        return self.db.fetchall(
            "SELECT * FROM plan_phases WHERE plan_id = ? ORDER BY phase_number",
            (plan_id,)
        )

    def get_next_plan_number(self) -> int:
        """Get the next plan number for ID generation."""
        row = self.db.fetchone("SELECT MAX(id) as max_id FROM plans")
        if row and row['max_id']:
            return row['max_id'] + 1
        return 1

    def exists(self, plan_id: str) -> bool:
        """Check if a plan exists."""
        row = self.db.fetchone(
            "SELECT 1 FROM plans WHERE plan_id = ?", (plan_id,)
        )
        return row is not None


class BuildStateRepository:
    """Repository for build state operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, plan_id: str, total_steps: int = 0) -> int:
        """Create build state for a plan."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO build_states (plan_id, status, started_at, updated_at, total_steps,
                                         completed_steps_json, failed_steps_json, skipped_steps_json,
                                         files_created_json, files_modified_json)
                VALUES (?, 'pending', ?, ?, ?, '[]', '[]', '[]', '[]', '[]')
            """, (plan_id, now, now, total_steps))
            return cursor.lastrowid

    def get(self, plan_id: str) -> Optional[dict]:
        """Get build state for a plan."""
        row = self.db.fetchone(
            "SELECT * FROM build_states WHERE plan_id = ?", (plan_id,)
        )
        if row:
            row['completed_steps'] = self.db.from_json(row.get('completed_steps_json'), [])
            row['failed_steps'] = self.db.from_json(row.get('failed_steps_json'), [])
            row['skipped_steps'] = self.db.from_json(row.get('skipped_steps_json'), [])
            row['files_created'] = self.db.from_json(row.get('files_created_json'), [])
            row['files_modified'] = self.db.from_json(row.get('files_modified_json'), [])
        return row

    def update(self, plan_id: str, **kwargs):
        """Update build state fields."""
        if not kwargs:
            return

        kwargs['updated_at'] = datetime.now().isoformat()

        # Convert list fields to JSON
        for field in ['completed_steps', 'failed_steps', 'skipped_steps',
                      'files_created', 'files_modified']:
            if field in kwargs:
                kwargs[f"{field}_json"] = self.db.to_json(kwargs.pop(field))

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [plan_id]

        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE build_states SET {set_clause} WHERE plan_id = ?",
                values
            )

    def set_step_state(self, plan_id: str, step_id: str, status: str,
                       started_at: str = None, completed_at: str = None,
                       retry_count: int = 0, error: str = None,
                       files_affected: list[str] = None, summary: str = None):
        """Create or update step state."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO step_states (plan_id, step_id, status, started_at, completed_at,
                                        retry_count, error, files_affected_json, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id, step_id) DO UPDATE SET
                    status = excluded.status,
                    started_at = COALESCE(excluded.started_at, step_states.started_at),
                    completed_at = excluded.completed_at,
                    retry_count = excluded.retry_count,
                    error = excluded.error,
                    files_affected_json = excluded.files_affected_json,
                    summary = excluded.summary
            """, (
                plan_id, step_id, status, started_at, completed_at,
                retry_count, error,
                self.db.to_json(files_affected or []),
                summary
            ))

    def get_step_states(self, plan_id: str) -> list[dict]:
        """Get all step states for a plan."""
        rows = self.db.fetchall(
            "SELECT * FROM step_states WHERE plan_id = ?", (plan_id,)
        )
        for row in rows:
            row['files_affected'] = self.db.from_json(row.get('files_affected_json'), [])
        return rows

    def get_step_state(self, plan_id: str, step_id: str) -> Optional[dict]:
        """Get step state for a specific step."""
        row = self.db.fetchone(
            "SELECT * FROM step_states WHERE plan_id = ? AND step_id = ?",
            (plan_id, step_id)
        )
        if row:
            row['files_affected'] = self.db.from_json(row.get('files_affected_json'), [])
        return row

    def exists(self, plan_id: str) -> bool:
        """Check if build state exists for a plan."""
        row = self.db.fetchone(
            "SELECT 1 FROM build_states WHERE plan_id = ?", (plan_id,)
        )
        return row is not None


class KnowledgeRepository:
    """Repository for knowledge store operations."""

    def __init__(self, db: Database):
        self.db = db

    def save_knowledge(self, project_name: str, project_type: str, primary_language: str,
                       languages: list[dict], frameworks: list[dict], tools: list[dict],
                       architecture_pattern: str, modules: list[dict], entry_points: list[str],
                       domains: list[dict], naming: dict, structure: dict, conventions: list[str],
                       statistics: dict, version: str = "1.0") -> int:
        """Save codebase knowledge, replacing any existing."""
        now = datetime.now().isoformat()

        with self.db.transaction() as conn:
            # Clear existing knowledge
            conn.execute("DELETE FROM codebase_knowledge")

            # Insert main knowledge record
            cursor = conn.execute("""
                INSERT INTO codebase_knowledge (version, last_updated, project_name,
                                               project_type, primary_language, statistics_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (version, now, project_name, project_type, primary_language,
                  self.db.to_json(statistics)))
            knowledge_id = cursor.lastrowid

            # Insert technologies
            for tech in languages:
                conn.execute("""
                    INSERT INTO technologies (knowledge_id, tech_type, name, confidence, version)
                    VALUES (?, 'language', ?, ?, ?)
                """, (knowledge_id, tech.get('name'), tech.get('confidence', 0.0),
                      tech.get('version')))

            for tech in frameworks:
                conn.execute("""
                    INSERT INTO technologies (knowledge_id, tech_type, name, confidence,
                                             entry_point, config_file)
                    VALUES (?, 'framework', ?, ?, ?, ?)
                """, (knowledge_id, tech.get('name'), tech.get('confidence', 0.0),
                      tech.get('entry_point'), tech.get('config_file')))

            for tech in tools:
                conn.execute("""
                    INSERT INTO technologies (knowledge_id, tech_type, name, confidence, config_file)
                    VALUES (?, 'tool', ?, ?, ?)
                """, (knowledge_id, tech.get('name'), tech.get('confidence', 0.0),
                      tech.get('config_file')))

            # Insert architecture info
            conn.execute("""
                INSERT INTO architecture_info (knowledge_id, pattern, entry_points_json)
                VALUES (?, ?, ?)
            """, (knowledge_id, architecture_pattern, self.db.to_json(entry_points)))

            # Insert modules
            for module in modules:
                conn.execute("""
                    INSERT INTO architecture_modules (knowledge_id, name, path, purpose, depends_on_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (knowledge_id, module.get('name'), module.get('path'),
                      module.get('purpose'), self.db.to_json(module.get('depends_on', []))))

            # Insert domains
            for domain in domains:
                conn.execute("""
                    INSERT INTO domains (knowledge_id, name, keywords_json, files_json,
                                        models_json, routes_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (knowledge_id, domain.get('name'),
                      self.db.to_json(domain.get('keywords', [])),
                      self.db.to_json(domain.get('files', [])),
                      self.db.to_json(domain.get('models', [])),
                      self.db.to_json(domain.get('routes', []))))

            # Insert patterns
            conn.execute("""
                INSERT INTO patterns (knowledge_id, naming_json, structure_json, conventions_json)
                VALUES (?, ?, ?, ?)
            """, (knowledge_id, self.db.to_json(naming), self.db.to_json(structure),
                  self.db.to_json(conventions)))

            return knowledge_id

    def load_knowledge(self) -> Optional[dict]:
        """Load codebase knowledge from database."""
        row = self.db.fetchone("SELECT * FROM codebase_knowledge LIMIT 1")
        if not row:
            return None

        knowledge_id = row['id']

        # Load technologies
        tech_rows = self.db.fetchall(
            "SELECT * FROM technologies WHERE knowledge_id = ?", (knowledge_id,)
        )

        languages = [r for r in tech_rows if r['tech_type'] == 'language']
        frameworks = [r for r in tech_rows if r['tech_type'] == 'framework']
        tools = [r for r in tech_rows if r['tech_type'] == 'tool']

        # Load architecture
        arch_row = self.db.fetchone(
            "SELECT * FROM architecture_info WHERE knowledge_id = ?", (knowledge_id,)
        )
        module_rows = self.db.fetchall(
            "SELECT * FROM architecture_modules WHERE knowledge_id = ?", (knowledge_id,)
        )

        # Load domains
        domain_rows = self.db.fetchall(
            "SELECT * FROM domains WHERE knowledge_id = ?", (knowledge_id,)
        )

        # Load patterns
        pattern_row = self.db.fetchone(
            "SELECT * FROM patterns WHERE knowledge_id = ?", (knowledge_id,)
        )

        return {
            'version': row['version'],
            'last_updated': row['last_updated'],
            'project': {
                'name': row['project_name'],
                'type': row['project_type'],
                'primary_language': row['primary_language'],
            },
            'technologies': {
                'languages': [{
                    'name': t['name'],
                    'confidence': t['confidence'],
                    'version': t['version'],
                } for t in languages],
                'frameworks': [{
                    'name': t['name'],
                    'confidence': t['confidence'],
                    'entry_point': t['entry_point'],
                    'config_file': t['config_file'],
                } for t in frameworks],
                'tools': [{
                    'name': t['name'],
                    'confidence': t['confidence'],
                    'config_file': t['config_file'],
                } for t in tools],
            },
            'architecture': {
                'pattern': arch_row['pattern'] if arch_row else 'unknown',
                'entry_points': self.db.from_json(arch_row['entry_points_json'], []) if arch_row else [],
                'modules': [{
                    'name': m['name'],
                    'path': m['path'],
                    'purpose': m['purpose'],
                    'depends_on': self.db.from_json(m['depends_on_json'], []),
                } for m in module_rows],
            },
            'domains': [{
                'name': d['name'],
                'keywords': self.db.from_json(d['keywords_json'], []),
                'files': self.db.from_json(d['files_json'], []),
                'models': self.db.from_json(d['models_json'], []),
                'routes': self.db.from_json(d['routes_json'], []),
            } for d in domain_rows],
            'patterns': {
                'naming': self.db.from_json(pattern_row['naming_json'], {}) if pattern_row else {},
                'structure': self.db.from_json(pattern_row['structure_json'], {}) if pattern_row else {},
                'conventions': self.db.from_json(pattern_row['conventions_json'], []) if pattern_row else [],
            },
            'statistics': self.db.from_json(row['statistics_json'], {}),
        }

    def exists(self) -> bool:
        """Check if knowledge exists."""
        row = self.db.fetchone("SELECT COUNT(*) as count FROM codebase_knowledge")
        return row and row['count'] > 0

    def clear(self):
        """Clear all knowledge data."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM codebase_knowledge")

    # --- Expert Index ---

    def save_expert_index(self, experts: list[dict], keyword_map: dict,
                          path_map: dict, version: str = "1.0") -> int:
        """Save expert index, replacing any existing."""
        now = datetime.now().isoformat()

        with self.db.transaction() as conn:
            # Clear existing index
            conn.execute("DELETE FROM expert_index")

            # Insert index record
            cursor = conn.execute("""
                INSERT INTO expert_index (version, last_updated, keyword_map_json, path_map_json)
                VALUES (?, ?, ?, ?)
            """, (version, now, self.db.to_json(keyword_map), self.db.to_json(path_map)))
            index_id = cursor.lastrowid

            # Insert expert entries
            for expert in experts:
                triggers = expert.get('triggers', {})
                conn.execute("""
                    INSERT INTO expert_entries (index_id, name, expert_type, file_path, weight,
                                               triggers_keywords_json, triggers_paths_json,
                                               triggers_topics_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    index_id, expert.get('name'), expert.get('type'), expert.get('file'),
                    expert.get('weight', 1.0),
                    self.db.to_json(triggers.get('keywords', [])),
                    self.db.to_json(triggers.get('paths', [])),
                    self.db.to_json(triggers.get('topics', []))
                ))

            return index_id

    def load_expert_index(self) -> Optional[dict]:
        """Load expert index from database."""
        row = self.db.fetchone("SELECT * FROM expert_index LIMIT 1")
        if not row:
            return None

        index_id = row['id']
        expert_rows = self.db.fetchall(
            "SELECT * FROM expert_entries WHERE index_id = ?", (index_id,)
        )

        return {
            'version': row['version'],
            'last_updated': row['last_updated'],
            'experts': [{
                'name': e['name'],
                'type': e['expert_type'],
                'file': e['file_path'],
                'weight': e['weight'],
                'triggers': {
                    'keywords': self.db.from_json(e['triggers_keywords_json'], []),
                    'paths': self.db.from_json(e['triggers_paths_json'], []),
                    'topics': self.db.from_json(e['triggers_topics_json'], []),
                }
            } for e in expert_rows],
            'keyword_map': self.db.from_json(row['keyword_map_json'], {}),
            'path_map': self.db.from_json(row['path_map_json'], {}),
        }

    def has_expert_index(self) -> bool:
        """Check if expert index exists."""
        row = self.db.fetchone("SELECT COUNT(*) as count FROM expert_index")
        return row and row['count'] > 0

    # --- Scan Metadata ---

    def save_scan_meta(self, scan_id: str, started_at: str, completed_at: str = None,
                       duration_seconds: float = 0, files_scanned: int = 0,
                       scan_type: str = "full", trigger: str = "manual",
                       experts_generated: list[str] = None) -> int:
        """Save scan metadata."""
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO scan_metadata (scan_id, started_at, completed_at, duration_seconds,
                                          files_scanned, scan_type, trigger_type, experts_generated_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scan_id) DO UPDATE SET
                    completed_at = excluded.completed_at,
                    duration_seconds = excluded.duration_seconds,
                    files_scanned = excluded.files_scanned,
                    experts_generated_json = excluded.experts_generated_json
            """, (scan_id, started_at, completed_at, duration_seconds, files_scanned,
                  scan_type, trigger, self.db.to_json(experts_generated or [])))
            return cursor.lastrowid

    def load_scan_meta(self) -> Optional[dict]:
        """Load most recent scan metadata."""
        row = self.db.fetchone(
            "SELECT * FROM scan_metadata ORDER BY started_at DESC LIMIT 1"
        )
        if row:
            row['experts_generated'] = self.db.from_json(row.get('experts_generated_json'), [])
        return row


class CostRepository:
    """Repository for cost tracking operations."""

    def __init__(self, db: Database):
        self.db = db

    def record(self, workflow: str, run_id: str, started_at: str, completed_at: str,
               total_tokens: int, estimated_cost: float, agents: dict,
               actual_cost: float = None):
        """Record completed workflow cost."""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO cost_history (workflow, run_id, started_at, completed_at,
                                         total_tokens, estimated_cost, actual_cost, agents_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (workflow, run_id, started_at, completed_at, total_tokens,
                  estimated_cost, actual_cost, self.db.to_json(agents)))

    def get_history(self, since: str = None, workflow: str = None) -> list[dict]:
        """Get cost history with optional filters."""
        sql = "SELECT * FROM cost_history WHERE 1=1"
        params = []

        if since:
            sql += " AND started_at >= ?"
            params.append(since)
        if workflow:
            sql += " AND workflow = ?"
            params.append(workflow)

        sql += " ORDER BY started_at DESC"
        rows = self.db.fetchall(sql, tuple(params))
        for row in rows:
            row['agents'] = self.db.from_json(row.get('agents_json'), {})
        return rows

    def get_total_cost(self, since: str = None) -> float:
        """Get total cost since a given date."""
        sql = "SELECT SUM(estimated_cost) as total FROM cost_history"
        params = []
        if since:
            sql += " WHERE started_at >= ?"
            params.append(since)

        row = self.db.fetchone(sql, tuple(params))
        return row['total'] if row and row['total'] else 0.0


class RunRepository:
    """Repository for active run tracking."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, run_id: str, workflow: str, description: str = None,
               plan_id: str = None, plan_path: str = None) -> int:
        """Create a new run."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO active_runs (run_id, workflow, status, started_at, plan_id,
                                        plan_path, description, progress)
                VALUES (?, ?, 'pending', ?, ?, ?, ?, 0)
            """, (run_id, workflow, now, plan_id, plan_path, description))
            return cursor.lastrowid

    def get(self, run_id: str) -> Optional[dict]:
        """Get run by ID."""
        row = self.db.fetchone(
            "SELECT * FROM active_runs WHERE run_id = ?", (run_id,)
        )
        if row:
            row['data'] = self.db.from_json(row.get('data_json'), {})
        return row

    def update(self, run_id: str, **kwargs):
        """Update run fields."""
        if 'data' in kwargs:
            kwargs['data_json'] = self.db.to_json(kwargs.pop('data'))

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [run_id]

        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE active_runs SET {set_clause} WHERE run_id = ?",
                values
            )

    def add_event(self, run_id: str, event_type: str, data: dict = None):
        """Add event to run."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO run_events (run_id, event_type, timestamp, data_json)
                VALUES (?, ?, ?, ?)
            """, (run_id, event_type, now, self.db.to_json(data)))

    def get_events(self, run_id: str, since_id: int = 0) -> list[dict]:
        """Get events for a run since a given ID."""
        rows = self.db.fetchall("""
            SELECT * FROM run_events WHERE run_id = ? AND id > ?
            ORDER BY timestamp
        """, (run_id, since_id))
        for row in rows:
            row['data'] = self.db.from_json(row.get('data_json'), {})
        return rows

    def list_active(self, status: str = None) -> list[dict]:
        """List active runs with optional status filter."""
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM active_runs WHERE status = ? ORDER BY started_at DESC",
                (status,)
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM active_runs ORDER BY started_at DESC"
            )
        for row in rows:
            row['data'] = self.db.from_json(row.get('data_json'), {})
        return rows

    def delete(self, run_id: str):
        """Delete a run and its events."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM active_runs WHERE run_id = ?", (run_id,))


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_db_instances: dict[str, Database] = {}
_db_lock = threading.Lock()


def get_database(project_root: Path) -> Database:
    """Get or create the database instance for a project."""
    key = str(project_root.resolve())
    with _db_lock:
        if key not in _db_instances:
            _db_instances[key] = Database(project_root)
        return _db_instances[key]


def get_plan_repository(project_root: Path) -> PlanRepository:
    """Get plan repository for a project."""
    return PlanRepository(get_database(project_root))


def get_build_state_repository(project_root: Path) -> BuildStateRepository:
    """Get build state repository for a project."""
    return BuildStateRepository(get_database(project_root))


def get_knowledge_repository(project_root: Path) -> KnowledgeRepository:
    """Get knowledge repository for a project."""
    return KnowledgeRepository(get_database(project_root))


def get_cost_repository(project_root: Path) -> CostRepository:
    """Get cost repository for a project."""
    return CostRepository(get_database(project_root))


def get_run_repository(project_root: Path) -> RunRepository:
    """Get run repository for a project."""
    return RunRepository(get_database(project_root))
