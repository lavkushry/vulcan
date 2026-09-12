-- ==============================================================================
-- Project Vulcan: Migration 011 - External Resources & Microsoft Foundry (EXT-01 / EXT-02)
-- Author: Alex Xu & Uncle Bob
-- Creates:
--   1. external_resources: Central registry for AI models, ITSM, PAM, GitOps, and observability
--   2. external_resource_versions: Immutable configuration history snapshots
--   3. external_resource_health: Time-series health telemetry & latency tracking
--   4. external_resource_audit: SHA-256 Merkle-chained tamper-evident audit ledger
-- Enforces:
--   Zero-Raw-Secrets Invariant, DB check constraints, strict typing, cascade deletes
-- ==============================================================================

-- 1. Master External Resources Table
CREATE TABLE IF NOT EXISTS external_resources (
    resource_id VARCHAR(128) PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    environment VARCHAR(32) NOT NULL DEFAULT 'PROD',
    endpoint TEXT NOT NULL,
    auth_mode VARCHAR(64) NOT NULL DEFAULT 'API_KEY',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    secret_refs JSONB NOT NULL DEFAULT '{}'::jsonb,
    health_status VARCHAR(32) NOT NULL DEFAULT 'CONFIGURED',
    latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_tested_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    created_by VARCHAR(128) NOT NULL DEFAULT 'system',
    updated_by VARCHAR(128) NOT NULL DEFAULT 'system',
    revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ext_res_revision CHECK (revision >= 1),
    CONSTRAINT chk_ext_res_latency CHECK (latency_ms >= 0.0),
    CONSTRAINT chk_ext_res_category CHECK (category IN (
        'AI & Models', 'ITSM & CMDB', 'Secrets & PAM', 'Source Control',
        'Execution', 'Observability', 'Storage & Data'
    )),
    CONSTRAINT chk_ext_res_auth_mode CHECK (auth_mode IN (
        'ENTRA_SERVICE_PRINCIPAL', 'MANAGED_IDENTITY', 'API_KEY', 'OAUTH2',
        'BASIC', 'MUTUAL_TLS', 'NONE'
    )),
    CONSTRAINT chk_ext_res_health_status CHECK (health_status IN (
        'CONFIGURED', 'CONNECTED', 'DEGRADED', 'AUTH_FAILED', 'DISABLED'
    )),
    CONSTRAINT chk_ext_res_environment CHECK (environment IN (
        'PROD', 'STAGE', 'DEV'
    ))
);

-- Indexes on external_resources
CREATE INDEX IF NOT EXISTS idx_ext_res_provider ON external_resources(provider);
CREATE INDEX IF NOT EXISTS idx_ext_res_category ON external_resources(category);
CREATE INDEX IF NOT EXISTS idx_ext_res_environment ON external_resources(environment);
CREATE INDEX IF NOT EXISTS idx_ext_res_health_status ON external_resources(health_status);
CREATE INDEX IF NOT EXISTS idx_ext_res_created_at ON external_resources(created_at DESC);


-- 2. Configuration Revision History (Immutable Snapshots)
CREATE TABLE IF NOT EXISTS external_resource_versions (
    id BIGSERIAL PRIMARY KEY,
    resource_id VARCHAR(128) NOT NULL REFERENCES external_resources(resource_id) ON DELETE CASCADE,
    revision INT NOT NULL,
    snapshot JSONB NOT NULL,
    actor VARCHAR(128) NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ext_res_versions_rev CHECK (revision >= 1)
);

CREATE INDEX IF NOT EXISTS idx_ext_res_versions_rid_rev ON external_resource_versions(resource_id, revision DESC);


-- 3. Time-Series Health Telemetry & Diagnostic Probes
CREATE TABLE IF NOT EXISTS external_resource_health (
    id BIGSERIAL PRIMARY KEY,
    resource_id VARCHAR(128) NOT NULL REFERENCES external_resources(resource_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    http_status INT,
    message TEXT NOT NULL DEFAULT '',
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ext_res_health_rid_checked ON external_resource_health(resource_id, checked_at DESC);


-- 4. Merkle-Chained Tamper-Evident Audit Ledger
CREATE TABLE IF NOT EXISTS external_resource_audit (
    id BIGSERIAL PRIMARY KEY,
    resource_id VARCHAR(128) NOT NULL,
    timestamp VARCHAR(64) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    action VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_hash VARCHAR(64) NOT NULL,
    current_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ext_res_audit_rid ON external_resource_audit(resource_id, id ASC);
CREATE INDEX IF NOT EXISTS idx_ext_res_audit_created ON external_resource_audit(created_at DESC);


-- 5. Zero-Raw-Secrets Compliant Seed Data (using vault:// or cyberark:// pointers)
INSERT INTO external_resources (
    resource_id, provider, category, display_name, environment, endpoint,
    auth_mode, enabled, config, secret_refs, health_status, latency_ms,
    created_by, updated_by, revision
) VALUES
(
    'res-foundry-default',
    'microsoft_foundry',
    'AI & Models',
    'Microsoft Foundry AI (Default)',
    'PROD',
    'https://vulcan-ai.services.ai.azure.com/api/projects/vulcan-prod',
    'ENTRA_SERVICE_PRINCIPAL',
    TRUE,
    '{"tenant_id": "00000000-0000-0000-0000-000000000001", "client_id": "00000000-0000-0000-0000-000000000002", "default_chat_deployment": "gpt-4o", "default_embedding_deployment": "text-embedding-3-small"}'::jsonb,
    '{"client_secret": "vault://secret/vulcan/azure/sp_secret"}'::jsonb,
    'CONFIGURED',
    0.0,
    'system',
    'system',
    1
),
(
    'res-servicenow-default',
    'servicenow',
    'ITSM & CMDB',
    'Enterprise ServiceNow',
    'PROD',
    'https://enterprise.service-now.com',
    'BASIC',
    TRUE,
    '{"username": "vulcan_service_acct"}'::jsonb,
    '{"password": "vault://secret/vulcan/servicenow/password"}'::jsonb,
    'CONFIGURED',
    0.0,
    'system',
    'system',
    1
),
(
    'res-cyberark-default',
    'cyberark',
    'Secrets & PAM',
    'CyberArk Enterprise CCP',
    'PROD',
    'https://cyberark.internal.net/AIMWebService',
    'MUTUAL_TLS',
    TRUE,
    '{"app_id": "VULCAN_CONTROL_PLANE"}'::jsonb,
    '{"client_cert": "cyberark://vulcan/pki/cert"}'::jsonb,
    'CONFIGURED',
    0.0,
    'system',
    'system',
    1
)
ON CONFLICT (resource_id) DO NOTHING;
