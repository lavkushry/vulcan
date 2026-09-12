"""
Project Vulcan: Tests for Governed Execution & Capability Tokens (AGENT-09)
"""
from datetime import datetime, timedelta, timezone
import hashlib
import pytest
from app.agentos.agents.executor import CapabilityTokenViolationError, ConstrainedExecutor
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.agentos.schemas import ExecutionCapabilityToken


def test_maker_checker_invariant_blocks_self_approval():
    kernel = AgentOSKernel()
    ctx = kernel.create_workflow(
        original_request="Deploy PostgreSQL 16 cluster",
        requester_id="alice@corp.internal",
        environment="PROD",
    )

    # Fast-forward to WAITING_FOR_APPROVAL
    ctx.transition_to(WorkflowState.UNDERSTANDING)
    ctx.transition_to(WorkflowState.DISCOVERING)
    ctx.transition_to(WorkflowState.PLANNING)
    ctx.transition_to(WorkflowState.COMPOSING)
    ctx.transition_to(WorkflowState.RESOLVING_RESOURCES)
    ctx.transition_to(WorkflowState.VALIDATING)
    ctx.transition_to(WorkflowState.SECURITY_REVIEW)
    ctx.transition_to(WorkflowState.CRITIC_REVIEW)
    ctx.transition_to(WorkflowState.POLICY_CHECK)
    ctx.transition_to(WorkflowState.WAITING_FOR_APPROVAL)
    kernel.repository.save_workflow(ctx)

    # Alice cannot approve her own request (Maker-Checker violation)
    with pytest.raises(PermissionError) as exc_info:
        kernel.approve_workflow(ctx.workflow_id, approver_id="alice@corp.internal")
    assert "Maker-Checker Violation" in str(exc_info.value)

    # Bob (independent checker) can approve
    approved = kernel.approve_workflow(ctx.workflow_id, approver_id="bob@corp.internal")
    assert approved.current_state == WorkflowState.EXECUTION_READY
    assert len(approved.approval_records) == 1


def test_constrained_executor_enforces_artifact_sha_binding():
    executor = ConstrainedExecutor()
    files = {"playbook.yml": "---\n- name: test\n"}
    sha = hashlib.sha256("playbook.yml:---\n- name: test\n".encode()).hexdigest()

    token = ExecutionCapabilityToken(
        token_id="tok-01",
        workflow_id="wf-01",
        artifact_sha256=sha,
        parameter_hash="hash-params",
        target_resource_id="db-01.internal",
        environment="PROD",
        approval_id="appr-bob",
        policy_decision_id="pol-01",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )

    # Valid execution consumes token
    res = executor.execute(token, files, target_resource_id="db-01.internal", parameters={})
    assert res.exit_code == 0
    assert "ok=5" in res.stdout
    assert token.is_used is True

    # Replay attack with already-used token MUST be rejected
    with pytest.raises(CapabilityTokenViolationError) as exc_replay:
        executor.execute(token, files, target_resource_id="db-01.internal", parameters={})
    assert "already been used" in str(exc_replay.value)

    # Tampered file content on fresh token must be rejected with SHA mismatch
    token2 = ExecutionCapabilityToken(
        token_id="tok-02",
        workflow_id="wf-01",
        artifact_sha256=sha,
        parameter_hash="hash-params",
        target_resource_id="db-01.internal",
        environment="PROD",
        approval_id="appr-bob",
        policy_decision_id="pol-01",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    tampered_files = {"playbook.yml": "---\n- name: TAMPERED\n"}
    with pytest.raises(CapabilityTokenViolationError) as exc_info:
        executor.execute(token2, tampered_files, target_resource_id="db-01.internal", parameters={})
    assert "Artifact SHA mismatch" in str(exc_info.value)


def test_constrained_executor_rejects_expired_token():
    executor = ConstrainedExecutor()
    files = {"playbook.yml": "---\n- name: test\n"}
    sha = hashlib.sha256("playbook.yml:---\n- name: test\n".encode()).hexdigest()

    expired_token = ExecutionCapabilityToken(
        token_id="tok-expired",
        workflow_id="wf-01",
        artifact_sha256=sha,
        parameter_hash="hash-params",
        target_resource_id="db-01.internal",
        environment="PROD",
        approval_id="appr-bob",
        policy_decision_id="pol-01",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # Expired!
    )

    with pytest.raises(CapabilityTokenViolationError) as exc_info:
        executor.execute(expired_token, files, target_resource_id="db-01.internal", parameters={})
    assert "expired" in str(exc_info.value)
