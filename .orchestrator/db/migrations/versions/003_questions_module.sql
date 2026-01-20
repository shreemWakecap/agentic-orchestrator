-- Migration: 003_questions_module
-- Created: 2026-01-20
-- Description: Questions & Answers module for knowledge base queries and code exploration

-- =====================================================
-- QUESTIONS & ANSWERS DOMAIN
-- =====================================================
-- Stores user questions and their answers sourced from
-- knowledge base (scouting results) or code exploration

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT UNIQUE NOT NULL,
    question_text TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'knowledge_base',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT valid_source_type CHECK (source_type IN ('knowledge_base', 'code_exploration')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'answered', 'obsolete'))
);

CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status);
CREATE INDEX IF NOT EXISTS idx_questions_source_type ON questions(source_type);
CREATE INDEX IF NOT EXISTS idx_questions_created_at ON questions(created_at DESC);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id TEXT UNIQUE NOT NULL,
    question_id TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    source_details_json TEXT,
    is_obsolete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);
CREATE INDEX IF NOT EXISTS idx_answers_is_obsolete ON answers(is_obsolete);
CREATE INDEX IF NOT EXISTS idx_answers_created_at ON answers(created_at DESC);
