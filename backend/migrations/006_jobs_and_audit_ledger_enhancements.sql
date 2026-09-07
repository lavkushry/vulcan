-- ============================================================================
-- Project Vulcan: Execution Jobs & Audit Ledger Enhancements (Milestone B)
-- Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")
-- Version: 006_jobs_and_audit_ledger_enhancements.sql
-- ============================================================================

-- 1. Ensure dispatched_by column exists on execution_jobs
ALTER TABLE execution_jobs ADD COLUMN IF NOT EXISTS dispatched_by VARCHAR(128);

-- 2. Ensure updated_at column exists on execution_jobs
ALTER TABLE execution_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- 3. Ensure unique constraint on correlation_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_execution_jobs_correlation'
    ) THEN
        ALTER TABLE execution_jobs ADD CONSTRAINT uq_execution_jobs_correlation UNIQUE (correlation_id);
    END IF;
END $$;

-- 4. Additional indexes for high-throughput multi-worker execution
CREATE INDEX IF NOT EXISTS idx_execution_jobs_requester ON execution_jobs(requester_id);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_approver ON execution_jobs(approver_id);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_actor ON audit_ledger(actor);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_action ON audit_ledger(action);
