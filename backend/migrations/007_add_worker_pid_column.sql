-- ============================================================================
-- Project Vulcan: Worker PID Tracking for Orphan Job Reaper (Milestone B)
-- Version: 007_add_worker_pid_column.sql
-- ============================================================================

-- 1. Add worker_pid column to track which OS process owns a RUNNING job
ALTER TABLE execution_jobs ADD COLUMN IF NOT EXISTS worker_pid INT;

-- 2. Partial index for the orphan reaper: quickly find RUNNING jobs by PID
CREATE INDEX IF NOT EXISTS idx_execution_jobs_running_pid
  ON execution_jobs(worker_pid) WHERE status = 'RUNNING';
