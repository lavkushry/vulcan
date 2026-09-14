"""
Project Vulcan: Tests for Planner & Composer Agents (AGENT-04)
"""
import pytest
from app.agentos.agents.composer import ComposerAgent
from app.agentos.agents.planner import PlannerAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import PlannerDecision


def test_planner_prefers_composition_when_curated_candidate_exists():
    agent = PlannerAgent()
    ctx = WorkflowContext(
        workflow_id="wf-plan-01",
        correlation_id="corr-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL 16",
        discovered_assets=[{
            "identifier": "vulcan.database.postgresql_cluster",
            "is_curated": True,
            "trust_state": "CURATED",
        }],
    )
    out = agent.execute(ctx)
    assert out.decision == PlannerDecision.COMPOSE
    assert "vulcan.database.postgresql_cluster" in out.selected_assets
    assert out.proposed_next_state == WorkflowState.COMPOSING.value


def test_planner_generates_when_no_assets_discovered():
    agent = PlannerAgent()
    ctx = WorkflowContext(
        workflow_id="wf-plan-02",
        correlation_id="corr-02",
        requester_id="alice",
        original_request="Build proprietary custom telemetry bridge",
        discovered_assets=[],
    )
    out = agent.execute(ctx)
    assert out.decision == PlannerDecision.GENERATE
    assert out.proposed_next_state == WorkflowState.GENERATING.value


def test_composer_assembles_acyclic_execution_dag():
    agent = ComposerAgent()
    ctx = WorkflowContext(
        workflow_id="wf-comp-01",
        correlation_id="corr-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL 16 cluster with Datadog and S3 backups",
    )
    out = agent.execute(ctx)
    assert len(out.dag_steps) == 4
    step_ids = [s.step_id for s in out.dag_steps]
    assert "step-1" in step_ids
    assert "step-2" in step_ids
    assert "step-3" in step_ids
    assert "step-4" in step_ids

    # Verify dependency links
    assert out.execution_graph["step-2"] == ["step-1"]
    assert "step-rollback" in out.rollback_dag.values()
