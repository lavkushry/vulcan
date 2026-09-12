-- ============================================================================
-- Project Vulcan: PostgreSQL 16 Chat Feedback & RLHF Reinforcement (CHAT-26)
-- Author: Andrej Karpathy (AI Systems Lead)
-- Version: 010_chat_intent_feedback.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS chat_intent_feedback (
    feedback_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES chat_sessions(session_id) ON DELETE SET NULL,
    turn_index INT,
    user_id VARCHAR(128) NOT NULL,
    prompt TEXT NOT NULL,
    resolved_identifier VARCHAR(128),
    rating VARCHAR(32) NOT NULL, -- 'thumbs_up', 'thumbs_down', 'rejected', 'corrected'
    correction_identifier VARCHAR(128),
    comment TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_feedback_user_id ON chat_intent_feedback(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_rating ON chat_intent_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_resolved ON chat_intent_feedback(resolved_identifier);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_created ON chat_intent_feedback(created_at DESC);
