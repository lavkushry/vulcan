"""
Project Vulcan: Tests for AgentOS Kernel, State Machine & Durability (AGENT-01)
"""
import copy
import pytest
from app.agentos.context import (
    AgentOSStateMachine,
    OptimisticLockError,
    StateTransitionError,
    WorkflowContext,
    WorkflowEvent,
    WorkflowState,
)
from app.agentos.kernel import AgentOSKernel
from app.agentos.repository import PostgresAgentWorkflowRepository


def test_workflow_context_initialization():
    ctx = WorkflowContext(
        workflow_id="wf-test-001",
        correlation_id="CORR-001",
        requester_id="alice@corp.internal",
        original_request="Deploy PostgreSQL cluster",
        environment="PROD",
    )
    assert ctx.current_state == WorkflowState.RECEIVED
    assert ctx.version == 1
    assert ctx.workflow_id == "wf-test-001"
    d = ctx.to_dict()
    assert d["workflow_id"] == "wf-test-001"
    assert d["current_state"] == "RECEIVED"

    restored = WorkflowContext.from_dict(d)
    assert restored.workflow_id == ctx.workflow_id
    assert restored.current_state == ctx.current_state
    assert restored.version == ctx.version


def test_legal_state_transitions():
    ctx = WorkflowContext(
        workflow_id="wf-test-002",
        correlation_id="CORR-002",
        requester_id="alice@corp.internal",
        original_request="Deploy PostgreSQL cluster",
    )
    # Legal hop: RECEIVED -> UNDERSTANDING
    ev1 = ctx.transition_to(WorkflowState.UNDERSTANDING, actor="kernel")
    assert ctx.current_state == WorkflowState.UNDERSTANDING
    assert ctx.version == 2
    assert ev1.from_state == WorkflowState.RECEIVED
    assert ev1.to_state == WorkflowState.UNDERSTANDING
    assert len(ev1.current_hash) == 64

    # Legal hop: UNDERSTANDING -> DISCOVERING
    ev2 = ctx.transition_to(WorkflowState.DISCOVERING, actor="kernel", prev_hash=ev1.current_hash)
    assert ctx.current_state == WorkflowState.DISCOVERING
    assert ctx.version == 3
    assert ev2.prev_hash == ev1.current_hash


def test_illegal_state_transition_rejected():
    ctx = WorkflowContext(
        workflow_id="wf-test-003",
        correlation_id="CORR-003",
        requester_id="alice@corp.internal",
        original_request="Deploy PostgreSQL cluster",
    )
    # Attempting to jump directly from RECEIVED to EXECUTING must raise StateTransitionError
    with pytest.raises(StateTransitionError) as exc_info:
        ctx.transition_to(WorkflowState.EXECUTING, actor="rogue_agent")
    assert "Illegal transition from 'RECEIVED' to 'EXECUTING'" in str(exc_info.value)
    assert ctx.current_state == WorkflowState.RECEIVED


def test_cryptographic_audit_event_hash_chain():
    ev1 = WorkflowEvent(
        workflow_id="wf-hash-01",
        correlation_id="corr-01",
        from_state=WorkflowState.RECEIVED,
        to_state=WorkflowState.UNDERSTANDING,
        actor="supervisor",
        prev_hash="0" * 64,
    )
    ev2 = WorkflowEvent(
        workflow_id="wf-hash-01",
        correlation_id="corr-01",
        from_state=WorkflowState.UNDERSTANDING,
        to_state=WorkflowState.DISCOVERING,
        actor="supervisor",
        prev_hash=ev1.current_hash,
    )
    assert ev1.current_hash != ev2.current_hash
    assert ev2.prev_hash == ev1.current_hash
    assert len(ev2.current_hash) == 64


def test_optimistic_locking_prevents_stale_writes():
    repo = PostgresAgentWorkflowRepository()
    ctx = WorkflowContext(
        workflow_id="wf-lock-01",
        correlation_id="corr-lock-01",
        requester_id="alice",
        original_request="Deploy database",
    )
    repo.save_workflow(ctx)

    # Worker A fetches context (version 1)
    worker_a_ctx = repo.get_workflow("wf-lock-01")
    # Worker B fetches context (version 1)
    worker_b_ctx = repo.get_workflow("wf-lock-01")

    # Worker A commits first, bumping version to 2
    worker_a_ctx.transition_to(WorkflowState.UNDERSTANDING)
    repo.save_workflow(worker_a_ctx)

    # Worker B attempts to commit with stale version 1 -> must fail with OptimisticLockError
    worker_b_ctx.original_request = "Stale concurrent update"
    with pytest.raises(OptimisticLockError) as exc_info:
        repo.save_workflow(worker_b_ctx)
    assert "Optimistic lock conflict" in str(exc_info.value)


def test_durability_across_kernel_restart():
    repo = PostgresAgentWorkflowRepository()
    kernel1 = AgentOSKernel(repository=repo)

    ctx = kernel1.create_workflow(
        original_request="Deploy PostgreSQL 16 cluster on three RHEL 9 nodes",
        requester_id="bob@corp.internal",
        environment="PROD",
    )
    kernel1.step(ctx.workflow_id)

    # Simulate backend/kernel crash and restart: instantiate new kernel sharing repo
    kernel2 = AgentOSKernel(repository=repo)
    recovered = kernel2.repository.get_workflow(ctx.workflow_id)

    assert recovered is not None
    assert recovered.workflow_id == ctx.workflow_id
    assert recovered.current_state == WorkflowState.DISCOVERING
    assert recovered.requester_id == "bob@corp.internal"
    assert recovered.environment == "PROD"
    assert recovered.version >= 2


def test_concurrent_writes_same_version_rejected_by_optimistic_locking():
    repo = PostgresAgentWorkflowRepository()
    ctx = WorkflowContext(
        workflow_id="wf-lock-02",
        correlation_id="corr-lock-02",
        requester_id="alice",
        original_request="Deploy database",
    )
    repo.save_workflow(ctx)

    # Worker A and Worker B both read version 1
    worker_a_ctx = repo.get_workflow("wf-lock-02")
    worker_b_ctx = repo.get_workflow("wf-lock-02")
    assert worker_a_ctx.version == 1
    assert worker_b_ctx.version == 1

    # Worker A transitions to version 2 and commits
    worker_a_ctx.transition_to(WorkflowState.UNDERSTANDING)
    assert worker_a_ctx.version == 2
    repo.save_workflow(worker_a_ctx)

    # Worker B also transitioned to version 2 from the same baseline
    worker_b_ctx.transition_to(WorkflowState.UNDERSTANDING)
    assert worker_b_ctx.version == 2

    # Worker B attempting to commit version 2 MUST be rejected with OptimisticLockError
    with pytest.raises(OptimisticLockError) as exc_info:
        repo.save_workflow(worker_b_ctx)
    assert "Optimistic lock conflict" in str(exc_info.value)


def test_supply_input_interactive_pause_and_resumes_to_discovery():
    kernel = AgentOSKernel()
    # Ambiguous prompt lacking required parameters
    ctx = kernel.create_workflow(
        original_request="restart database",
        requester_id="alice@corp.internal",
        environment="PROD",
    )
    assert ctx.current_state == WorkflowState.RECEIVED

    # Step 1: Detects missing parameters -> WAITING_FOR_INPUT
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.current_state == WorkflowState.WAITING_FOR_INPUT
    assert len(ctx.unresolved_questions) > 0

    # Operator supplies missing parameters
    supplied = {
        "target_host": "db-prod-01.corp.internal",
        "environment": "PROD",
        "change_ticket": "CHG0099881",
    }
    ctx = kernel.supply_input(ctx.workflow_id, supplied)
    assert ctx.current_state == WorkflowState.UNDERSTANDING
    assert ctx.normalized_intent["known_parameters"]["target_host"] == "db-prod-01.corp.internal"
    assert len(ctx.unresolved_questions) == 0

    # Step 2: Advances legally from UNDERSTANDING through DISCOVERING to PLANNING
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.current_state == WorkflowState.PLANNING
    assert len(ctx.discovered_assets) >= 1


def test_test_agent_execution_in_testing_state():
    kernel = AgentOSKernel()
    ctx = kernel.create_workflow(
        original_request="Deploy PostgreSQL 16 cluster",
        requester_id="alice@corp.internal",
    )
    # Simulate workflow progressing to TESTING
    ctx.transition_to(WorkflowState.UNDERSTANDING)
    ctx.transition_to(WorkflowState.DISCOVERING)
    ctx.transition_to(WorkflowState.PLANNING)
    ctx.transition_to(WorkflowState.COMPOSING)
    ctx.transition_to(WorkflowState.RESOLVING_RESOURCES)
    ctx.transition_to(WorkflowState.VALIDATING)
    ctx.transition_to(WorkflowState.SECURITY_REVIEW)
    ctx.transition_to(WorkflowState.TESTING)
    ctx.generated_artifacts = [{
        "files": [{"path": "roles/postgresql/tasks/main.yml", "content": "---\n- name: install postgres\n  package:\n    name: postgresql16\n"}],
        "rollback_files": [{"path": "roles/postgresql/tasks/rollback.yml", "content": "---\n- name: stop postgres\n"}],
    }]
    kernel.repository.save_workflow(ctx)

    # Step in TESTING state invokes TestAgent
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.current_state == WorkflowState.CRITIC_REVIEW
    assert len(ctx.test_results) >= 3
    assert all(t["passed"] for t in ctx.test_results)

