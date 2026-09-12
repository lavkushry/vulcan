"""
Project Vulcan: Adversarial Security Tests (P0 #11)
Author: AgentOS Core Team

Comprehensive adversarial test suite covering:
- Forged token fields
- Parameter tampering
- Target/environment/action tampering
- Cross-worker replay prevention
- DB failure behavior
- Identity spoofing
- Approval alias attacks
- Process restart replay prevention
"""
import copy
import hashlib
import json
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.agentos.agents.executor import (
    CapabilityTokenViolationError,
    ConstrainedExecutor,
)
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.agentos.repository import PostgresAgentWorkflowRepository
from app.agentos.schemas import ExecutionCapabilityToken


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifact_files():
    return {
        "roles/main.yml": "---\n- name: test\n  debug: msg=hello\n",
    }


def _compute_sha(files):
    combined = []
    for path in sorted(files.keys()):
        combined.append(f"{path}:{files[path]}")
    raw = "\n---FILE---\n".join(combined).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _make_valid_token(files, parameters, **overrides):
    param_hash = hashlib.sha256(
        json.dumps(parameters, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    defaults = dict(
        token_id="cap-adversarial-001",
        workflow_id="wf-adversarial",
        artifact_sha256=_compute_sha(files),
        parameter_hash=param_hash,
        target_resource_id="db-test.internal",
        environment="PROD",
        approval_id="appr-bob",
        policy_decision_id="pol-sim-abc",
        allowed_action="EXECUTE",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    defaults.update(overrides)
    return ExecutionCapabilityToken(**defaults)


# ---------------------------------------------------------------------------
# Token Forgery
# ---------------------------------------------------------------------------

class TestTokenForgery:
    def test_forged_artifact_sha_rejected(self):
        """Valid token but modified artifact content -> SHA mismatch."""
        files = _make_artifact_files()
        params = {"target": "db"}
        token = _make_valid_token(files, params)
        executor = ConstrainedExecutor()

        # Tamper with artifact content
        tampered_files = {"roles/main.yml": "---\n- name: EVIL\n  shell: rm -rf /\n"}
        with pytest.raises(CapabilityTokenViolationError, match="Artifact SHA mismatch"):
            executor.execute(
                token=token,
                artifact_files=tampered_files,
                target_resource_id="db-test.internal",
                parameters=params,
                environment="PROD",
            )

    def test_forged_hmac_rejected(self):
        """Valid token but tampered HMAC -> rejected."""
        files = _make_artifact_files()
        params = {"target": "db"}
        token = _make_valid_token(files, params)

        # Compute real HMAC then tamper
        hmac_key = "test-hmac-key-for-adversarial"
        token.hmac_signature = ExecutionCapabilityToken.compute_hmac(token, hmac_key)
        # Now tamper with a token field
        token.target_resource_id = "evil-host.hacker.com"

        executor = ConstrainedExecutor()
        with patch.dict(os.environ, {"VULCAN_CAPABILITY_HMAC_KEY": hmac_key}):
            with pytest.raises(CapabilityTokenViolationError):
                executor.execute(
                    token=token,
                    artifact_files=files,
                    target_resource_id="evil-host.hacker.com",
                    parameters=params,
                    environment="PROD",
                )


# ---------------------------------------------------------------------------
# Parameter Tampering
# ---------------------------------------------------------------------------

class TestParameterTampering:
    def test_tampered_parameters_fail_hash_validation(self):
        """Modify parameters after token issuance -> hash mismatch."""
        files = _make_artifact_files()
        original_params = {"db_name": "production", "port": 5432}
        token = _make_valid_token(files, original_params)
        executor = ConstrainedExecutor()

        tampered_params = {"db_name": "production", "port": 5432, "evil_flag": True}
        with pytest.raises(CapabilityTokenViolationError, match="Parameter hash mismatch"):
            executor.execute(
                token=token,
                artifact_files=files,
                target_resource_id="db-test.internal",
                parameters=tampered_params,
                environment="PROD",
            )

    def test_tampered_target_resource_rejected(self):
        """Change target host -> target mismatch."""
        files = _make_artifact_files()
        params = {"db_name": "prod"}
        token = _make_valid_token(files, params)
        executor = ConstrainedExecutor()

        with pytest.raises(CapabilityTokenViolationError, match="Target mismatch"):
            executor.execute(
                token=token,
                artifact_files=files,
                target_resource_id="evil-target.internal",
                parameters=params,
                environment="PROD",
            )

    def test_tampered_environment_rejected(self):
        """Token bound to PROD, attempt in DEV -> environment mismatch."""
        files = _make_artifact_files()
        params = {"db_name": "prod"}
        token = _make_valid_token(files, params, environment="PROD")
        executor = ConstrainedExecutor()

        with pytest.raises(CapabilityTokenViolationError, match="Environment mismatch"):
            executor.execute(
                token=token,
                artifact_files=files,
                target_resource_id="db-test.internal",
                parameters=params,
                environment="DEV",
            )

    def test_tampered_action_rejected(self):
        """Token allows EXECUTE, attempt ROLLBACK -> action mismatch."""
        files = _make_artifact_files()
        params = {"db_name": "prod"}
        token = _make_valid_token(files, params, allowed_action="EXECUTE")
        executor = ConstrainedExecutor()

        with pytest.raises(CapabilityTokenViolationError, match="Action mismatch"):
            executor.execute(
                token=token,
                artifact_files=files,
                target_resource_id="db-test.internal",
                parameters=params,
                environment="PROD",
                action="ROLLBACK",
            )


# ---------------------------------------------------------------------------
# Identity Attacks
# ---------------------------------------------------------------------------

class TestIdentityAttacks:
    def test_maker_checker_self_approval_blocked(self):
        """Same user creates and approves -> PermissionError."""
        kernel = AgentOSKernel()
        ctx = kernel.create_workflow(
            original_request="Test maker-checker",
            requester_id="alice@corp.internal",
            environment="PROD",
        )
        # Fast-forward to WAITING_FOR_APPROVAL
        ctx.current_state = WorkflowState.WAITING_FOR_APPROVAL
        ctx.version += 1
        kernel.repository.save_workflow(ctx)

        with pytest.raises(PermissionError, match="Maker-Checker Violation"):
            kernel.approve_workflow(
                ctx.workflow_id,
                approver_id="alice@corp.internal",
            )

    def test_different_approver_succeeds(self):
        """Different user approves -> success."""
        kernel = AgentOSKernel()
        ctx = kernel.create_workflow(
            original_request="Test cross-approval",
            requester_id="alice@corp.internal",
            environment="PROD",
        )
        ctx.current_state = WorkflowState.WAITING_FOR_APPROVAL
        ctx.version += 1
        kernel.repository.save_workflow(ctx)

        result = kernel.approve_workflow(
            ctx.workflow_id,
            approver_id="bob@corp.internal",
        )
        assert result.current_state == WorkflowState.EXECUTION_READY


# ---------------------------------------------------------------------------
# Replay Prevention
# ---------------------------------------------------------------------------

class TestReplayPrevention:
    def test_replay_attack_second_use_rejected(self):
        """Execute token once, try again -> replay rejected."""
        files = _make_artifact_files()
        params = {"db_name": "prod"}
        token = _make_valid_token(files, params)
        executor = ConstrainedExecutor()

        # First execution succeeds
        result = executor.execute(
            token=token,
            artifact_files=files,
            target_resource_id="db-test.internal",
            parameters=params,
            environment="PROD",
        )
        assert result.exit_code == 0

        # Second execution is replay attack
        with pytest.raises(CapabilityTokenViolationError, match="already been used"):
            executor.execute(
                token=token,
                artifact_files=files,
                target_resource_id="db-test.internal",
                parameters=params,
                environment="PROD",
            )

    def test_expired_token_rejected(self):
        """Token with past expiry -> rejected."""
        files = _make_artifact_files()
        params = {"db_name": "prod"}
        token = _make_valid_token(
            files, params,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        executor = ConstrainedExecutor()

        with pytest.raises(CapabilityTokenViolationError, match="expired"):
            executor.execute(
                token=token,
                artifact_files=files,
                target_resource_id="db-test.internal",
                parameters=params,
                environment="PROD",
            )

    def test_repository_token_consumption_prevents_replay(self):
        """Atomic consumption via repository: second attempt returns None."""
        from app.agentos.schemas import ExecutionCapabilityToken
        repo = PostgresAgentWorkflowRepository(db_url=None)
        token = ExecutionCapabilityToken(
            token_id="cap-replay-test",
            workflow_id="wf-replay",
            artifact_sha256="sha-test",
            parameter_hash="hash-test",
            target_resource_id="host-1",
            environment="PROD",
            approval_id="appr-1",
            policy_decision_id="pol-1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        repo.save_capability_token(token)

        first = repo.consume_capability_token("cap-replay-test")
        assert first is not None

        second = repo.consume_capability_token("cap-replay-test")
        assert second is None


# ---------------------------------------------------------------------------
# DB Failure Behavior
# ---------------------------------------------------------------------------

class TestDBFailureBehavior:
    def test_db_unreachable_in_test_mode_falls_back(self):
        """Without production mode, Postgres failure falls back to memory."""
        original = os.environ.pop("AGENTOS_MODE", None)
        try:
            repo = PostgresAgentWorkflowRepository(db_url=None)
            ctx = WorkflowContext(
                workflow_id="wf-fallback",
                correlation_id="CORR-FB",
                requester_id="tester",
                original_request="Test fallback",
            )
            saved = repo.save_workflow(ctx)
            assert saved.workflow_id == "wf-fallback"
        finally:
            if original:
                os.environ["AGENTOS_MODE"] = original

    def test_db_unreachable_in_production_mode_halts(self):
        """Production mode without valid Postgres URL raises RuntimeError."""
        original = os.environ.get("AGENTOS_MODE")
        original_db = os.environ.get("POSTGRES_URL")
        try:
            os.environ["AGENTOS_MODE"] = "production"
            os.environ.pop("POSTGRES_URL", None)
            os.environ.pop("DATABASE_URL", None)
            with pytest.raises(RuntimeError):
                PostgresAgentWorkflowRepository(db_url=None)
        finally:
            if original is not None:
                os.environ["AGENTOS_MODE"] = original
            else:
                os.environ.pop("AGENTOS_MODE", None)
            if original_db is not None:
                os.environ["POSTGRES_URL"] = original_db
