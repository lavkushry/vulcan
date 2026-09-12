"""
Project Vulcan: Tests for Curation Lifecycle & Catalog Promotion (AGENT-11)
"""
import pytest
from app.agentos.agents.curator import CuratorAgent
from app.agentos.context import WorkflowContext, WorkflowState


def test_curator_proposes_candidate_after_verified_success():
    agent = CuratorAgent()
    ctx = WorkflowContext(
        workflow_id="wf-cur-01",
        correlation_id="corr-cur-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL",
        normalized_intent={"automation_domain": "database"},
        execution_result={"exit_code": 0, "artifact_sha256": "sha256-verified-art"},
        postcondition_verification={"all_passed": True, "probes": [{"probe_id": "p1"}]},
    )
    out = agent.execute(ctx)
    assert out.proposed_promotion is True
    assert out.promotion_tier == "CANDIDATE"
    assert "database" in out.item_identifier
    assert out.proposed_next_state == WorkflowState.EVALUATING.value


def test_curator_rejects_promotion_if_postconditions_failed():
    agent = CuratorAgent()
    ctx = WorkflowContext(
        workflow_id="wf-cur-02",
        correlation_id="corr-cur-02",
        requester_id="alice",
        original_request="Deploy PostgreSQL",
        execution_result={"exit_code": 0},
        postcondition_verification={"all_passed": False},  # Failed postconditions!
    )
    out = agent.execute(ctx)
    assert out.proposed_promotion is False
    assert out.promotion_tier == "REJECTED"
