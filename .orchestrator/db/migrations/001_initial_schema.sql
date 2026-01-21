-- Migration: 001_initial_schema
-- Description: Initial database schema for the orchestrator
-- Created: 2025-01-22

-- =============================================================================
-- PLANS AND STEPS
-- =============================================================================

CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(255) UNIQUE NOT NULL,
    goal TEXT,
    request TEXT,
    raw_content TEXT,
    context_json TEXT DEFAULT '[]',
    verify_json TEXT DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plans_plan_id ON plans(plan_id);
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);

CREATE TABLE IF NOT EXISTS plan_phases (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(255) NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
    phase_id VARCHAR(255) NOT NULL,
    name VARCHAR(500),
    phase_number INTEGER DEFAULT 0,
    can_parallelize BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_plan_phases_plan_id ON plan_phases(plan_id);

CREATE TABLE IF NOT EXISTS plan_steps (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(255) NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
    phase_id VARCHAR(255),
    step_id VARCHAR(255) NOT NULL,
    action VARCHAR(255),
    target TEXT,
    description TEXT,
    done TEXT,
    inputs_json TEXT DEFAULT '[]',
    needs_json TEXT DEFAULT '[]',
    step_order INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_plan_steps_plan_id ON plan_steps(plan_id);

-- =============================================================================
-- BUILD STATE AND STEP STATE
-- =============================================================================

CREATE TABLE IF NOT EXISTS build_states (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(255) UNIQUE NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    current_step VARCHAR(255),
    current_phase INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    last_error TEXT,
    execution_mode VARCHAR(50) DEFAULT 'sequential',
    current_wave_index INTEGER DEFAULT 0,
    completed_steps_json TEXT DEFAULT '[]',
    failed_steps_json TEXT DEFAULT '[]',
    skipped_steps_json TEXT DEFAULT '[]',
    files_created_json TEXT DEFAULT '[]',
    files_modified_json TEXT DEFAULT '[]',
    started_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_build_states_plan_id ON build_states(plan_id);
CREATE INDEX IF NOT EXISTS idx_build_states_status ON build_states(status);

CREATE TABLE IF NOT EXISTS step_states (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(255) NOT NULL REFERENCES build_states(plan_id) ON DELETE CASCADE,
    step_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    error TEXT,
    files_affected_json TEXT DEFAULT '[]',
    summary TEXT,
    full_output TEXT,
    retry_history_json TEXT DEFAULT '[]',
    CONSTRAINT uq_step_states_plan_step UNIQUE(plan_id, step_id)
);

CREATE INDEX IF NOT EXISTS idx_step_states_plan_id ON step_states(plan_id);
CREATE INDEX IF NOT EXISTS idx_step_states_step_id ON step_states(step_id);

CREATE TABLE IF NOT EXISTS goal_verification_state (
    id SERIAL PRIMARY KEY,
    plan_id VARCHAR(255) UNIQUE NOT NULL,
    goal TEXT DEFAULT '',
    original_request TEXT DEFAULT '',
    verification_attempt INTEGER DEFAULT 0,
    missing_items_json TEXT DEFAULT '[]',
    completion_percentage INTEGER DEFAULT 0,
    goal_achieved BOOLEAN DEFAULT FALSE,
    context_notes_json TEXT DEFAULT '[]',
    verify_commands_json TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_goal_verification_plan_id ON goal_verification_state(plan_id);

-- =============================================================================
-- ACTIVE RUNS AND EVENTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS active_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) UNIQUE NOT NULL,
    workflow VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    plan_id VARCHAR(255),
    plan_path TEXT,
    description TEXT,
    progress INTEGER DEFAULT 0,
    error TEXT,
    data_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_active_runs_run_id ON active_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_active_runs_status ON active_runs(status);
CREATE INDEX IF NOT EXISTS idx_active_runs_plan_id ON active_runs(plan_id);

CREATE TABLE IF NOT EXISTS run_events (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL REFERENCES active_runs(run_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id);

-- =============================================================================
-- COST TRACKING
-- =============================================================================

CREATE TABLE IF NOT EXISTS cost_history (
    id SERIAL PRIMARY KEY,
    workflow VARCHAR(50) NOT NULL,
    run_id VARCHAR(255),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_tokens INTEGER DEFAULT 0,
    estimated_cost FLOAT DEFAULT 0.0,
    actual_cost FLOAT,
    agents_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_cost_history_workflow ON cost_history(workflow);
CREATE INDEX IF NOT EXISTS idx_cost_history_run_id ON cost_history(run_id);

-- =============================================================================
-- CODEBASE KNOWLEDGE
-- =============================================================================

CREATE TABLE IF NOT EXISTS codebase_knowledge (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) DEFAULT '1.0',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    project_name VARCHAR(255),
    project_type VARCHAR(100),
    primary_language VARCHAR(100),
    statistics_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS technologies (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER NOT NULL REFERENCES codebase_knowledge(id) ON DELETE CASCADE,
    tech_type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    confidence FLOAT DEFAULT 0.0,
    version VARCHAR(100),
    entry_point TEXT,
    config_file TEXT
);

CREATE INDEX IF NOT EXISTS idx_technologies_knowledge_id ON technologies(knowledge_id);

CREATE TABLE IF NOT EXISTS architecture_info (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER UNIQUE NOT NULL REFERENCES codebase_knowledge(id) ON DELETE CASCADE,
    pattern VARCHAR(100) DEFAULT 'unknown',
    entry_points_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_architecture_info_knowledge_id ON architecture_info(knowledge_id);

CREATE TABLE IF NOT EXISTS architecture_modules (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER NOT NULL REFERENCES codebase_knowledge(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    path TEXT,
    purpose TEXT,
    depends_on_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_architecture_modules_knowledge_id ON architecture_modules(knowledge_id);

CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER NOT NULL REFERENCES codebase_knowledge(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    keywords_json TEXT DEFAULT '[]',
    files_json TEXT DEFAULT '[]',
    models_json TEXT DEFAULT '[]',
    routes_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_domains_knowledge_id ON domains(knowledge_id);

CREATE TABLE IF NOT EXISTS patterns (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER UNIQUE NOT NULL REFERENCES codebase_knowledge(id) ON DELETE CASCADE,
    naming_json TEXT DEFAULT '{}',
    structure_json TEXT DEFAULT '{}',
    conventions_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_patterns_knowledge_id ON patterns(knowledge_id);

-- =============================================================================
-- EXPERT INDEX
-- =============================================================================

CREATE TABLE IF NOT EXISTS expert_index (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) DEFAULT '1.0',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    keyword_map_json TEXT DEFAULT '{}',
    path_map_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS expert_entries (
    id SERIAL PRIMARY KEY,
    index_id INTEGER NOT NULL REFERENCES expert_index(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    expert_type VARCHAR(50),
    file_path TEXT,
    weight FLOAT DEFAULT 1.0,
    triggers_keywords_json TEXT DEFAULT '[]',
    triggers_paths_json TEXT DEFAULT '[]',
    triggers_topics_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_expert_entries_index_id ON expert_entries(index_id);

-- =============================================================================
-- SCAN METADATA
-- =============================================================================

CREATE TABLE IF NOT EXISTS scan_metadata (
    id SERIAL PRIMARY KEY,
    scan_id VARCHAR(255) UNIQUE NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds FLOAT DEFAULT 0,
    files_scanned INTEGER DEFAULT 0,
    scan_type VARCHAR(50) DEFAULT 'full',
    trigger_type VARCHAR(50) DEFAULT 'manual',
    experts_generated_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_scan_metadata_scan_id ON scan_metadata(scan_id);

CREATE TABLE IF NOT EXISTS extended_scan_metadata (
    id SERIAL PRIMARY KEY,
    git_commit_hash VARCHAR(64),
    git_branch VARCHAR(255),
    scanned_paths_json TEXT DEFAULT '[]',
    trigger_type VARCHAR(50) DEFAULT 'manual',
    scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scan_mode VARCHAR(50) DEFAULT 'full'
);

CREATE INDEX IF NOT EXISTS idx_extended_scan_metadata_git_commit ON extended_scan_metadata(git_commit_hash);
CREATE INDEX IF NOT EXISTS idx_extended_scan_metadata_scan_time ON extended_scan_metadata(scan_time);

-- =============================================================================
-- CODING RULES
-- =============================================================================

CREATE TABLE IF NOT EXISTS coding_rules (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER REFERENCES codebase_knowledge(id) ON DELETE CASCADE,
    rule_id VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL,
    rule_text TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    examples_json TEXT DEFAULT '[]',
    source_files_json TEXT DEFAULT '[]',
    confidence FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_coding_rules_knowledge_id ON coding_rules(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_coding_rules_rule_id ON coding_rules(rule_id);
CREATE INDEX IF NOT EXISTS idx_coding_rules_category ON coding_rules(category);
CREATE INDEX IF NOT EXISTS idx_coding_rules_severity ON coding_rules(severity);

-- =============================================================================
-- FILE KNOWLEDGE
-- =============================================================================

CREATE TABLE IF NOT EXISTS file_knowledge (
    id SERIAL PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    file_type VARCHAR(50),
    language VARCHAR(50),
    size_bytes INTEGER DEFAULT 0,
    line_count INTEGER DEFAULT 0,
    imports_json TEXT DEFAULT '[]',
    exports_json TEXT DEFAULT '[]',
    classes_json TEXT DEFAULT '[]',
    functions_json TEXT DEFAULT '[]',
    dependencies_json TEXT DEFAULT '[]',
    metadata_json TEXT DEFAULT '{}',
    summary TEXT,
    last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_file_knowledge_file_path ON file_knowledge(file_path);
CREATE INDEX IF NOT EXISTS idx_file_knowledge_language ON file_knowledge(language);
CREATE INDEX IF NOT EXISTS idx_file_knowledge_last_scanned ON file_knowledge(last_scanned);

CREATE TABLE IF NOT EXISTS file_scan_history (
    id SERIAL PRIMARY KEY,
    scan_id VARCHAR(255) UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    scan_type VARCHAR(50) DEFAULT 'single',
    trigger_type VARCHAR(50) DEFAULT 'manual',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds FLOAT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'completed',
    error_message TEXT,
    knowledge_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_file_scan_history_scan_id ON file_scan_history(scan_id);
CREATE INDEX IF NOT EXISTS idx_file_scan_history_file_path ON file_scan_history(file_path);
