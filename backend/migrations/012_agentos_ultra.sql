-- ==============================================================================
-- Project Vulcan: Migration 012 - AgentOS Ultra Governance & Automation Kernel
-- Author: Architectural Review Board & AgentOS Core Team
-- Creates:
--   1. agent_workflows: Canonical persisted WorkflowContext with optimistic locking
--   2. agent_workflow_events: Cryptographically chained transition audit trail
--   3. agent_runs: Structured agent executions, telemetry, and raw LLM traces
--   4. agent_versions: Immutable versioned agent registry & release stages
--   5. agent_evidence: Structured evidence store for calibrated confidence
--   6. automation_specs: Intermediate AutomationSpecification IR
--   7. automation_artifacts: Immutable generated/composed execution artifacts
--   8. execution_authorizations: Cryptographic ExecutionCapabilityTokens
--   9. verification_results: Independent desired-state verification telemetry
--  10. agent_eval_runs: Multi-tier agent evaluation benchmark records
-- ==============================================================================

-- 1. Canonical Agent Workflows (WorkflowContext persistence)
CREATE TABLE IF NOT EXISTS agent_workflows (
    workflow_id VARCHAR(128) PRIMARY KEY,
    correlation_id VARCHAR(128) NOT NULL,
    requester_id VARCHAR(128) NOT NULL,
    environment VARCHAR(32) NOT NULL DEFAULT 'PROD',
    current_state VARCHAR(64) NOT NULL DEFAULT 'RECEIVED',
    version INT NOT NULL DEFAULT 1,
    original_request TEXT NOT NULL,
    normalized_intent JSONB NOT NULL DEFAULT '{}'::jsonb,
    desired_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_classification JSONB NOT NULL DEFAULT '{}'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    unresolved_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    discovered_assets JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    automation_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_artifacts JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_resources JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolved_resources JSONB NOT NULL DEFAULT '{}'::jsonb,
    secret_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_results JSONB NOT NULL DEFAULT '[]'::jsonb,
    security_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    test_results JSONB NOT NULL DEFAULT '[]'::jsonb,
    critic_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_decision JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_records JSONB NOT NULL DEFAULT '[]'::jsonb,
    execution_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    postcondition_verification JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    curation_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    eval_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_agent_wf_version CHECK (version >= 1),
    CONSTRAINT chk_agent_wf_env CHECK (environment IN ('PROD', 'STAGE', 'DEV')),
    CONSTRAINT chk_agent_wf_state CHECK (current_state IN (
        'RECEIVED', 'UNDERSTANDING', 'DISCOVERING', 'PLANNING', 'COMPOSING',
        'GENERATING', 'RESOLVING_RESOURCES', 'WAITING_FOR_INPUT', 'WAITING_FOR_RESOURCE',
        'WAITING_FOR_SECRET', 'VALIDATING', 'SECURITY_REVIEW', 'TESTING',
        'CRITIC_REVIEW', 'POLICY_CHECK', 'WAITING_FOR_APPROVAL', 'EXECUTION_READY',
        'EXECUTING', 'VERIFYING', 'SUCCESS', 'CURATING', 'EVALUATING',
        'INTENT_UNCERTAIN', 'DISCOVERY_FAILED', 'PLAN_REJECTED', 'GENERATION_FAILED',
        'VALIDATION_FAILED', 'SECURITY_REJECTED', 'TEST_FAILED', 'POLICY_DENIED',
        'EXECUTION_FAILED', 'VERIFY_FAILED', 'ROLLING_BACK', 'ROLLED_BACK',
        'MANUAL_INTERVENTION_REQUIRED'
    ))
);

CREATE INDEX IF NOT EXISTS idx_agent_wf_state ON agent_workflows(current_state);
CREATE INDEX IF NOT EXISTS idx_agent_wf_env ON agent_workflows(environment);
CREATE INDEX IF NOT EXISTS idx_agent_wf_created ON agent_workflows(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_wf_corr ON agent_workflows(correlation_id);

-- 2. State Transition Audit Events
CREATE TABLE IF NOT EXISTS agent_workflow_events (
    event_id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    correlation_id VARCHAR(128) NOT NULL,
    from_state VARCHAR(64) NOT NULL,
    to_state VARCHAR(64) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    agent_name VARCHAR(64),
    agent_version VARCHAR(32),
    reason TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_hash VARCHAR(64) NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000',
    current_hash VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_wf_events_wf ON agent_workflow_events(workflow_id, timestamp ASC);

-- 3. Structured Agent Runs
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id VARCHAR(128) PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    agent_name VARCHAR(64) NOT NULL,
    agent_version VARCHAR(32) NOT NULL,
    model_provider VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_response TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    evidence_count INT NOT NULL DEFAULT 0,
    latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_wf ON agent_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name, agent_version);

-- 4. Versioned Agent Registry
CREATE TABLE IF NOT EXISTS agent_versions (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    version VARCHAR(32) NOT NULL,
    system_instruction_hash VARCHAR(64) NOT NULL,
    model_provider VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    release_stage VARCHAR(32) NOT NULL DEFAULT 'CANARY',
    tools JSONB NOT NULL DEFAULT '[]'::jsonb,
    schemas JSONB NOT NULL DEFAULT '{}'::jsonb,
    policies JSONB NOT NULL DEFAULT '{}'::jsonb,
    eval_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    deployed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_agent_version UNIQUE (agent_name, version),
    CONSTRAINT chk_agent_release_stage CHECK (release_stage IN ('SHADOW', 'CANARY', 'GA', 'RETIRED'))
);

CREATE INDEX IF NOT EXISTS idx_agent_versions_lookup ON agent_versions(agent_name, release_stage);

-- 5. Agent Evidence Records
CREATE TABLE IF NOT EXISTS agent_evidence (
    evidence_id VARCHAR(128) PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    evidence_type VARCHAR(64) NOT NULL,
    source_uri TEXT NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    confidence_weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    summary TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_evidence_wf ON agent_evidence(workflow_id);

-- 6. Intermediate Automation Specifications
CREATE TABLE IF NOT EXISTS automation_specs (
    spec_id VARCHAR(128) PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    engine VARCHAR(32) NOT NULL,
    spec_hash VARCHAR(64) NOT NULL,
    specification JSONB NOT NULL,
    resource_contract JSONB NOT NULL,
    postconditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auto_specs_wf ON automation_specs(workflow_id);

-- 7. Immutable Automation Artifacts
CREATE TABLE IF NOT EXISTS automation_artifacts (
    artifact_id VARCHAR(128) PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    spec_id VARCHAR(128) NOT NULL REFERENCES automation_specs(spec_id) ON DELETE CASCADE,
    engine VARCHAR(32) NOT NULL,
    artifact_sha256 VARCHAR(64) NOT NULL,
    git_repo TEXT,
    git_commit_sha VARCHAR(40),
    files JSONB NOT NULL,
    is_immutable BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auto_artifacts_wf ON automation_artifacts(workflow_id);
CREATE INDEX IF NOT EXISTS idx_auto_artifacts_sha ON automation_artifacts(artifact_sha256);

-- 8. Execution Capability Tokens
CREATE TABLE IF NOT EXISTS execution_authorizations (
    token_id VARCHAR(128) PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    artifact_sha256 VARCHAR(64) NOT NULL,
    parameter_hash VARCHAR(64) NOT NULL,
    target_resource_id VARCHAR(128) NOT NULL,
    environment VARCHAR(32) NOT NULL,
    approval_id VARCHAR(128) NOT NULL,
    policy_decision_id VARCHAR(128) NOT NULL,
    allowed_action VARCHAR(64) NOT NULL DEFAULT 'EXECUTE',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_at TIMESTAMPTZ,

    CONSTRAINT chk_exec_auth_env CHECK (environment IN ('PROD', 'STAGE', 'DEV'))
);

CREATE INDEX IF NOT EXISTS idx_exec_auth_wf ON execution_authorizations(workflow_id);
CREATE INDEX IF NOT EXISTS idx_exec_auth_token ON execution_authorizations(token_id, is_used);

-- 9. Verification Results
CREATE TABLE IF NOT EXISTS verification_results (
    result_id VARCHAR(128) PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    target_id VARCHAR(128) NOT NULL,
    verifier_agent_version VARCHAR(32) NOT NULL,
    all_passed BOOLEAN NOT NULL DEFAULT FALSE,
    probes JSONB NOT NULL DEFAULT '[]'::jsonb,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_results_wf ON verification_results(workflow_id);

-- 10. Agent Evaluation Runs
CREATE TABLE IF NOT EXISTS agent_eval_runs (
    eval_id VARCHAR(128) PRIMARY KEY,
    suite_name VARCHAR(128) NOT NULL,
    tier INT NOT NULL DEFAULT 1,
    target_agent VARCHAR(64) NOT NULL,
    target_version VARCHAR(32) NOT NULL,
    total_scenarios INT NOT NULL,
    passed_scenarios INT NOT NULL,
    failed_scenarios INT NOT NULL,
    pass_rate DOUBLE PRECISION NOT NULL,
    ci_lower DOUBLE PRECISION,
    ci_upper DOUBLE PRECISION,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_eval_target ON agent_eval_runs(target_agent, target_version);
