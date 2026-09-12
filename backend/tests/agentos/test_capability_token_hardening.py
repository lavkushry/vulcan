"""
Project Vulcan: Tests for Capability Token Hardening (WAVE 2, P0 #4, #5)
"""
import json
import hashlib
import os
import pytest
from datetime import datetime, timedelta, timezone

from app.agentos.agents.executor import CapabilityTokenViolationError, ConstrainedExecutor
from app.agentos.schemas import ExecutionCapabilityToken


@pytest.fixture
def base_token():
    # Helper to generate a valid baseline token
    files = {"playbook.yml": "---\n- name: test\n"}
    artifact_sha = hashlib.sha256("playbook.yml:---\n- name: test\n".encode("utf-8")).hexdigest()
    
    params = {"target_host": "db-01.internal"}
    param_raw = json.dumps(params, sort_keys=True, default=str).encode("utf-8")
    param_hash = hashlib.sha256(param_raw).hexdigest()

    token = ExecutionCapabilityToken(
        token_id="tok-test-01",
        workflow_id="wf-test",
        artifact_sha256=artifact_sha,
        parameter_hash=param_hash,
        target_resource_id="db-01.internal",
        environment="PROD",
        approval_id="appr-123",
        policy_decision_id="pol-123",
        allowed_action="EXECUTE",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    # Sign it
    hmac_key = "test-secret-key"
    os.environ["VULCAN_CAPABILITY_HMAC_KEY"] = hmac_key
    token.hmac_signature = ExecutionCapabilityToken.compute_hmac(token, hmac_key)
    return token, files, params, hmac_key


def test_tampered_parameters_fail_sha_validation(base_token):
    """Modify parameters after token issuance → CapabilityTokenViolationError."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    # Tamper with params
    tampered_params = {"target_host": "db-02.internal"}
    
    with pytest.raises(CapabilityTokenViolationError, match="Parameter hash mismatch"):
        executor.execute(token, files, target_resource_id="db-01.internal", parameters=tampered_params)


def test_environment_mismatch_rejected(base_token):
    """Token bound to PROD, attempt execution in DEV → rejected."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    with pytest.raises(CapabilityTokenViolationError, match="Environment mismatch"):
        executor.execute(token, files, target_resource_id="db-01.internal", parameters=params, environment="DEV")


def test_action_mismatch_rejected(base_token):
    """Token allows EXECUTE, attempt ROLLBACK → rejected."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    with pytest.raises(CapabilityTokenViolationError, match="Action mismatch"):
        executor.execute(token, files, target_resource_id="db-01.internal", parameters=params, action="ROLLBACK")


def test_hmac_forgery_rejected(base_token):
    """Tamper with token fields after HMAC computation → rejected."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    # Tamper with token field (e.g. target_resource_id)
    token.target_resource_id = "db-02.internal"
    
    with pytest.raises(CapabilityTokenViolationError, match="HMAC signature verification failed"):
        executor.execute(token, files, target_resource_id="db-02.internal", parameters=params)


def test_replay_attack_second_use_rejected(base_token):
    """Execute token, try again → rejected."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    # First execution succeeds
    res = executor.execute(token, files, target_resource_id="db-01.internal", parameters=params)
    assert res.exit_code == 0
    assert token.is_used is True
    
    # Second execution fails
    with pytest.raises(CapabilityTokenViolationError, match="already been used"):
        executor.execute(token, files, target_resource_id="db-01.internal", parameters=params)


def test_expired_token_rejected(base_token):
    """Set expires_at in the past → rejected."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    # Recompute HMAC since we changed expires_at, otherwise HMAC fails first
    token.hmac_signature = ExecutionCapabilityToken.compute_hmac(token, hmac_key)
    
    with pytest.raises(CapabilityTokenViolationError, match="expired"):
        executor.execute(token, files, target_resource_id="db-01.internal", parameters=params)


def test_cross_workflow_token_rejected(base_token):
    """Use token from workflow-A on workflow-B → rejected (parameter hash mismatch)."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    # Using the same token but for a different workflow's inputs 
    with pytest.raises(CapabilityTokenViolationError, match="Target mismatch"):
        executor.execute(token, files, target_resource_id="db-02.internal", parameters=params)


def test_valid_token_with_all_checks_succeeds(base_token):
    """All fields match → execution succeeds."""
    token, files, params, hmac_key = base_token
    executor = ConstrainedExecutor()
    
    res = executor.execute(token, files, target_resource_id="db-01.internal", parameters=params)
    assert res.exit_code == 0
    assert token.is_used is True


POSTGRES_URL = (
    os.getenv("POSTGRES_URL")
    or os.getenv("DATABASE_URL")
    or f"postgresql://{os.getenv('POSTGRES_USER', 'vulcan_admin')}@{os.getenv('POSTGRES_HOST', 'localhost')}:5432/{os.getenv('POSTGRES_DB', 'vulcan_control_plane')}"
)

def _is_postgres_available() -> bool:
    try:
        import psycopg
        with psycopg.connect(POSTGRES_URL, connect_timeout=1) as conn:
            return True
    except Exception:
        return False

@pytest.mark.skipif(not _is_postgres_available(), reason="PostgreSQL not available on current host")
def test_postgresql_atomic_consumption(base_token):
    from app.agentos.repository import AgentRepository
    import psycopg
    
    token, _, _, _ = base_token
    repo = AgentRepository(db_url=POSTGRES_URL, production_mode=True)
    
    # Save the token
    repo.save_capability_token(token)
    
    # Verify consumed_at is NULL
    with psycopg.connect(POSTGRES_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT consumed_at, is_used FROM execution_authorizations WHERE token_id = %s", (token.token_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] is None
            assert row[1] is False
            
    # Consume atomically
    consumed_token = repo.consume_capability_token(token.token_id)
    assert consumed_token is not None
    assert consumed_token.is_used is True
    
    # Verify consumed_at is now set
    with psycopg.connect(POSTGRES_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT consumed_at, is_used FROM execution_authorizations WHERE token_id = %s", (token.token_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None
            assert row[1] is True

    # Try to consume again - should fail (concurrency safety)
    second_consume = repo.consume_capability_token(token.token_id)
    assert second_consume is None
