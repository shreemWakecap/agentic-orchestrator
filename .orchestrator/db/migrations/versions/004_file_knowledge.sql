-- Migration: 004_file_knowledge
-- Created: 2024-01-21
-- Description: Add file-level knowledge scouting tables

-- =====================================================
-- FILE KNOWLEDGE DOMAIN
-- =====================================================
-- Stores detailed metadata for individual files scouted
-- independently of bulk codebase scans

PRAGMA foreign_keys = ON;

-- =====================================================
-- FILE KNOWLEDGE TABLE
-- =====================================================
-- Stores file-specific metadata extracted during targeted scouting

CREATE TABLE IF NOT EXISTS file_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    language TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    line_count INTEGER NOT NULL DEFAULT 0,
    last_modified TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    imports_json TEXT,
    exports_json TEXT,
    classes_json TEXT,
    functions_json TEXT,
    dependencies_json TEXT,
    domain_hints_json TEXT,
    notes TEXT,
    scouted_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index for fast lookups by file path (most common query)
CREATE INDEX IF NOT EXISTS idx_file_knowledge_file_path ON file_knowledge(file_path);

-- Index for finding files by language
CREATE INDEX IF NOT EXISTS idx_file_knowledge_language ON file_knowledge(language);

-- Index for finding recently scouted files
CREATE INDEX IF NOT EXISTS idx_file_knowledge_scouted_at ON file_knowledge(scouted_at DESC);

-- Index for content hash to detect unchanged files
CREATE INDEX IF NOT EXISTS idx_file_knowledge_content_hash ON file_knowledge(content_hash);

-- Index for finding files by name
CREATE INDEX IF NOT EXISTS idx_file_knowledge_file_name ON file_knowledge(file_name);

-- =====================================================
-- FILE SCAN HISTORY TABLE
-- =====================================================
-- Tracks individual file scan operations for auditing and debugging

CREATE TABLE IF NOT EXISTS file_scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT UNIQUE NOT NULL,
    file_path TEXT NOT NULL,
    scan_type TEXT NOT NULL DEFAULT 'manual',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL,
    success INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    file_knowledge_id INTEGER,
    FOREIGN KEY (file_knowledge_id) REFERENCES file_knowledge(id) ON DELETE SET NULL,
    CONSTRAINT valid_scan_type CHECK (scan_type IN ('manual', 'bulk', 'watch', 'incremental'))
);

-- Index for finding scans by file path
CREATE INDEX IF NOT EXISTS idx_file_scan_history_file_path ON file_scan_history(file_path);

-- Index for finding scans by type
CREATE INDEX IF NOT EXISTS idx_file_scan_history_scan_type ON file_scan_history(scan_type);

-- Index for finding recent scans
CREATE INDEX IF NOT EXISTS idx_file_scan_history_started_at ON file_scan_history(started_at DESC);

-- Index for finding successful/failed scans
CREATE INDEX IF NOT EXISTS idx_file_scan_history_success ON file_scan_history(success);

-- Composite index for file path + scan type queries
CREATE INDEX IF NOT EXISTS idx_file_scan_history_path_type ON file_scan_history(file_path, scan_type);
