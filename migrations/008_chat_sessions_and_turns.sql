-- ============================================================================
-- Project Vulcan: PostgreSQL 16 Chat Sessions & Multi-Turn History (CHAT-03)
-- Author: Alex Xu (Distributed Systems Lead)
-- Version: 008_chat_sessions_and_turns.sql
-- ============================================================================

-- 1. Chat Sessions Aggregate Root
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    title VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id, updated_at DESC);

-- 2. Chat Turns (Immutable conversational history entries)
CREATE TABLE IF NOT EXISTS chat_turns (
    turn_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    turn_index INT NOT NULL DEFAULT 0,
    role VARCHAR(32) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    intent_state VARCHAR(32), -- 'READY', 'NEEDS_INPUT', 'DISAMBIGUATION', 'REJECTED'
    catalog_identifier VARCHAR(128),
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    token_usage INT,
    latency_ms DOUBLE PRECISION,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chat_turns_session_index UNIQUE (session_id, turn_index)
);

CREATE INDEX IF NOT EXISTS idx_chat_turns_session ON chat_turns(session_id, turn_index ASC);
CREATE INDEX IF NOT EXISTS idx_chat_turns_created_at ON chat_turns(created_at DESC);
