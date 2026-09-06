-- ============================================================================
-- Project Vulcan: Production PostgreSQL 16 + pgvector Schema Migration
-- Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")
-- Version: 003_vulcan_core_schema.sql
-- ============================================================================

-- 1. Enable pgvector extension for high-speed semantic playbook retrieval
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Execution Jobs Aggregate Persistence
CREATE TABLE IF NOT EXISTS execution_jobs (
    id VARCHAR(64) PRIMARY KEY,
    correlation_id VARCHAR(64) NOT NULL,
    catalog_identifier VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    risk_tier VARCHAR(16) NOT NULL,
    requester_id VARCHAR(128) NOT NULL,
    approver_id VARCHAR(128),
    target_resource_id VARCHAR(255) NOT NULL,
    environment VARCHAR(32) NOT NULL DEFAULT 'PROD',
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    servicenow_chg VARCHAR(64),
    storage_artifact_uri VARCHAR(512),
    storage_artifact_sha256 CHAR(64),
    approval_requested_at TIMESTAMPTZ,
    approval_decision JSONB,
    exit_code INT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_execution_jobs_status ON execution_jobs(status);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_target_resource ON execution_jobs(target_resource_id);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_correlation_id ON execution_jobs(correlation_id);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_created_at ON execution_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_pending_approval ON execution_jobs(status, approval_requested_at) 
WHERE status = 'PENDING_APPROVAL';

-- 4. Immutable Merkle Cryptographic Audit Ledger
CREATE TABLE IF NOT EXISTS audit_ledger (
    id BIGSERIAL PRIMARY KEY,
    correlation_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor VARCHAR(128) NOT NULL,
    action VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_hash CHAR(64) NOT NULL,
    current_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_ledger_correlation ON audit_ledger(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_timestamp ON audit_ledger(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_ledger_current_hash ON audit_ledger(current_hash);

-- 5. Distributed Fencing Tokens
CREATE TABLE IF NOT EXISTS resource_fencing_tokens (
    resource_id VARCHAR(255) PRIMARY KEY,
    current_token BIGINT NOT NULL DEFAULT 1000,
    locked_by VARCHAR(255),
    locked_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
