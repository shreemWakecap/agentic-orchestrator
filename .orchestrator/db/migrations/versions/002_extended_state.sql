-- Migration: 002_extended_state
-- Created: 2026-01-18
-- Description: Extended state persistence for goal context, parallel execution, retry history, and thinking support

-- =====================================================
-- GOAL VERIFICATION STATE TABLE
-- =====================================================
-- Persists goal context across pauses/interruptions

CREATE TABLE IF NOT EXISTS goal_verification_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT UNIQUE NOT NULL,
    goal TEXT NOT NULL,
    original_request TEXT,
    verification_attempt INTEGER NOT NULL DEFAULT 0,
    missing_items_json TEXT,
    completion_percentage INTEGER NOT NULL DEFAULT 0,
    goal_achieved INTEGER NOT NULL DEFAULT 0,
    context_notes_json TEXT,
    verify_commands_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_goal_verification_plan_id ON goal_verification_state(plan_id);

-- =====================================================
-- BUILD STATES EXTENSIONS
-- =====================================================
-- Add parallel execution tracking and thinking support

-- execution_mode: 'sequential', 'parallel', or 'coordinated'
ALTER TABLE build_states ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'sequential';

-- current_wave_index: for tracking parallel wave progress
ALTER TABLE build_states ADD COLUMN current_wave_index INTEGER NOT NULL DEFAULT 0;

-- thinking_enabled: whether extended thinking was used
ALTER TABLE build_states ADD COLUMN thinking_enabled INTEGER NOT NULL DEFAULT 0;

-- =====================================================
-- STEP STATES EXTENSIONS
-- =====================================================
-- Add retry history and full output storage

-- retry_history_json: array of {timestamp, error, duration_ms}
ALTER TABLE step_states ADD COLUMN retry_history_json TEXT;

-- full_output: stores up to 5000 chars of step output (vs 200 char summary)
ALTER TABLE step_states ADD COLUMN full_output TEXT;

-- thinking_tokens_used: tokens consumed by extended thinking for this step
ALTER TABLE step_states ADD COLUMN thinking_tokens_used INTEGER DEFAULT 0;
