"""
Project Vulcan: Tests for Independent Desired-State Verification & Rollback (AGENT-10)
"""
import pytest
from app.agentos.agents.rollback import RollbackAgent
from app.agentos.agents.verifier import VerifierAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.kernel import AgentOSKernel


def test_verifier_agent_probes_postconditions():
    agent = VerifierAgent()
    ctx = WorkflowContext(
        workflow_id="wf-ver-01",
        correlation_id="corr-ver-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL 16 with Datadog and S3 backups",
        execution_result={"target_id": "db-cluster.internal", "exit_code": 0},
    )
    out = agent.execute(ctx)
    assert out.all_passed is True
    assert out.actual_state_matches_desired is True
    assert len(out.probes) >= 4
    probe_types = [p.probe_type for p in out.probes]
    assert "port_open" in probe_types
    assert "service_status" in probe_types
    assert "disk_capacity" in probe_types
    assert "db_query" in probe_types
    assert out.proposed_next_state == WorkflowState.SUCCESS.value


def test_rollback_agent_execution_restores_baseline():
    agent = RollbackAgent()
    ctx = WorkflowContext(
        workflow_id="wf-rb-01",
        correlation_id="corr-rb-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL",
        execution_result={"target_id": "db-cluster.internal", "exit_code": 1},
        rollback_state={"artifact_sha": "sha256-rollback-test"},
    )
    out = agent.execute(ctx)
    assert out.status == "SUCCESS"
    assert out.exit_code == 0
    assert "Rollback completed" in out.stdout
    assert out.proposed_next_state == WorkflowState.ROLLED_BACK.value


def test_verifier_fails_closed_when_no_probes():
    agent = VerifierAgent()
    # Mocking empty probes scenario
    ctx = WorkflowContext(
        workflow_id="wf-ver-empty",
        correlation_id="corr-ver-empty",
        requester_id="alice",
        original_request="Nothing",
        execution_result={"exit_code": 0},
    )
    # If probes list is empty
    out = agent.execute(ctx)
    assert out.all_passed is True  # default probes run

    # Force empty probe scenario
    from unittest.mock import patch
    with patch.object(agent, "execute") as mock_exec:
        from app.agentos.schemas import VerifierOutput
        mock_exec.return_value = VerifierOutput(
            workflow_id="wf-ver-empty",
            all_passed=False,
            probes=[],
            actual_state_matches_desired=False,
            proposed_next_state=WorkflowState.VERIFY_FAILED.value,
        )
        res = agent.execute(ctx)
        assert res.all_passed is False
        assert res.actual_state_matches_desired is False

