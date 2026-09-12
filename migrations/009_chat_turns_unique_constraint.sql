-- ============================================================================
-- Project Vulcan: PostgreSQL 16 Chat Turns Unique Constraint (CHAT-03)
-- Author: Alex Xu (Distributed Systems Lead)
-- Guarantees atomic turn ordering and prevents duplicate turn indices per session.
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_chat_turns_session_index'
    ) THEN
        ALTER TABLE chat_turns ADD CONSTRAINT uq_chat_turns_session_index UNIQUE (session_id, turn_index);
    END IF;
END $$;
