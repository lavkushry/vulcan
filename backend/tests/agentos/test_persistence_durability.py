"""
Project Vulcan: Persistence Durability Tests (P0 #6, #7, #9, #10)
"""
import os
import pytest
from datetime import datetime, timezone
from app.agentos.context import OptimisticLockError, WorkflowContext, WorkflowState
from app.agentos.repository import PostgresAgentWorkflowRepository
from app.agentos.policy_engine import SimulationPolicyEngine, PolicyDecision
from app.agentos.adapters.foundry_adapter import DeterministicAgentRuntime, FoundryAgentRuntime
from app.agentos.adapters.execution_adapter import SimulationExecutionAdapter


def test_optimistic_lock_prevents_stale_write():
    """Two concurrent saves with same version raise OptimisticLockError."""
    repo = PostgresAgentWorkflowRepository(db_url=None)
    ctx = WorkflowContext(
        workflow_id="wf-lock-test",
        correlation_id="CORR-LOCK",
        requester_id="tester",
        original_request="Test locking",
        current_state=WorkflowState.RECEIVED,
        version=1,
    )
    repo.save_workflow(ctx)

    # Advance version
    ctx.version = 2
    ctx.current_state = WorkflowState.UNDERSTANDING
    repo.save_workflow(ctx)

    # Stale write with version=2 (already at 2)
    stale = WorkflowContext(
        workflow_id="wf-lock-test",
        correlation_id="CORR-LOCK",
        requester_id="tester",
        original_request="Test locking",
        current_state=WorkflowState.DISCOVERING,
        version=2,
    )
    with pytest.raises(OptimisticLockError):
        repo.save_workflow(stale)


def test_production_mode_requires_postgres_url():
    """Production mode without POSTGRES_URL raises RuntimeError."""
    original = os.environ.get("AGENTOS_MODE")
    original_db = os.environ.get("POSTGRES_URL")
    try:
        os.environ["AGENTOS_MODE"] = "production"
        os.environ.pop("POSTGRES_URL", None)
        os.environ.pop("DATABASE_URL", None)
        with pytest.raises(RuntimeError, match="requires POSTGRES_URL"):
            PostgresAgentWorkflowRepository(db_url=None)
    finally:
        if original is not None:
            os.environ["AGENTOS_MODE"] = original
        else:
            os.environ.pop("AGENTOS_MODE", None)
        if original_db is not None:
            os.environ["POSTGRES_URL"] = original_db


def test_simulation_policy_engine_requires_approval_for_prod():
    """PROD environment requires Maker-Checker approval."""
    engine = SimulationPolicyEngine()
    ctx = WorkflowContext(
        workflow_id="wf-pol",
        correlation_id="CORR-POL",
        requester_id="op",
        original_request="test",
        environment="PROD",
    )
    ctx.risk_classification = {"risk_tier": "MEDIUM", "requires_maker_checker": True}
    decision = engine.evaluate(ctx)
    assert decision.decision == "REQUIRES_APPROVAL"
    assert decision.decision_id.startswith("pol-sim-")


def test_simulation_policy_engine_auto_approves_low_risk_dev():
    """DEV + low risk + no maker-checker auto-approves."""
    engine = SimulationPolicyEngine()
    ctx = WorkflowContext(
        workflow_id="wf-pol2",
        correlation_id="CORR-POL2",
        requester_id="op",
        original_request="test",
        environment="DEV",
    )
    ctx.risk_classification = {"risk_tier": "LOW", "requires_maker_checker": False}
    decision = engine.evaluate(ctx)
    assert decision.decision == "APPROVED"


def test_deterministic_runtime_is_deterministic():
    runtime = DeterministicAgentRuntime()
    assert runtime.is_deterministic is True
    assert runtime.is_simulation is True
    assert runtime.runtime_name == "deterministic_python"


def test_foundry_runtime_is_not_deterministic():
    runtime = FoundryAgentRuntime()
    assert runtime.is_deterministic is False
    assert runtime.is_simulation is False
    assert runtime.runtime_name == "foundry_llm"


def test_simulation_execution_adapter_labeled():
    adapter = SimulationExecutionAdapter()
    assert adapter.is_simulation is True


def test_token_consumption_prevents_double_use():
    """Atomic token consumption: second attempt returns None."""
    from app.agentos.schemas import ExecutionCapabilityToken
    from datetime import timedelta
    repo = PostgresAgentWorkflowRepository(db_url=None)
    token = ExecutionCapabilityToken(
        token_id="cap-consume-test",
        workflow_id="wf-consume",
        artifact_sha256="abc123",
        parameter_hash="def456",
        target_resource_id="host-1",
        environment="PROD",
        approval_id="appr-1",
        policy_decision_id="pol-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    repo.save_capability_token(token)

    # First consumption succeeds
    consumed = repo.consume_capability_token("cap-consume-test")
    assert consumed is not None
    assert consumed.is_used is True

    # Second consumption fails
    second = repo.consume_capability_token("cap-consume-test")
    assert second is None
