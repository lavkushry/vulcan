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
    assert out.confidence < 0.70, f"Confidence {out.confidence} should be < 0.70 when zero candidates have evidence"


def test_planner_ranks_candidates_and_records_rejections():
    agent = PlannerAgent()
    ctx = WorkflowContext(
        workflow_id="wf-plan-03",
        correlation_id="corr-03",
        requester_id="alice",
        original_request="Deploy PostgreSQL 16 database",
        environment="PROD",
        discovered_assets=[
            {
                "identifier": "vulcan.database.postgresql_16_cluster",
                "name": "PostgreSQL 16 Hardened Cluster",
                "is_curated": True,
                "trust_state": "CURATED",
                "trust_score": 0.95,
                "relevance_score": 0.95,
                "has_rollback": True,
                "version": "16.0",
            },
            {
                "identifier": "community.postgres_untested",
                "name": "Untested Postgres without Rollback",
                "is_curated": False,
                "trust_state": "CANDIDATE",
                "trust_score": 0.4,
                "relevance_score": 0.6,
                "has_rollback": False,  # Missing rollback in PROD -> rejected
                "version": "16.0",
            },
            {
                "identifier": "malicious.postgres_quarantined",
                "name": "Quarantined Asset",
                "is_curated": False,
                "trust_state": "QUARANTINED",  # Blocked by security policy
                "trust_score": 0.0,
                "relevance_score": 0.5,
                "has_rollback": True,
            },
            {
                "identifier": "vulcan.database.postgres_12_legacy",
                "name": "Legacy Postgres 12",
                "is_curated": True,
                "trust_state": "CURATED",
                "trust_score": 0.9,
                "relevance_score": 0.7,
                "has_rollback": True,
                "version": "12.0",  # Incompatible version (requested 16)
            },
        ],
    )
    out = agent.execute(ctx)
    assert out.decision == PlannerDecision.COMPOSE
    assert out.selected_assets == ["vulcan.database.postgresql_16_cluster"]
    assert out.confidence >= 0.85
    assert len(out.rejected_candidates) >= 3

    rejected_reasons = {r.identifier: r.reason for r in out.rejected_candidates}
    assert "malicious.postgres_quarantined" in rejected_reasons
    assert "QUARANTINED" in rejected_reasons["malicious.postgres_quarantined"]

    assert "community.postgres_untested" in rejected_reasons
    assert "rollback" in rejected_reasons["community.postgres_untested"].lower()

    assert "vulcan.database.postgres_12_legacy" in rejected_reasons
    assert "incompatible" in rejected_reasons["vulcan.database.postgres_12_legacy"].lower()


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
