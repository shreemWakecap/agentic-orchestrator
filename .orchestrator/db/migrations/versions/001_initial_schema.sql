-- Migration: 001_initial_schema
-- Created: 2024-01-17
-- Description: Initial database schema for orchestrator

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
