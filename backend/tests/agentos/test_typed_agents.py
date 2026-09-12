"""
Project Vulcan: Tests for Typed Agent Framework, Assumption Elimination & Evidence Engine (AGENT-02)
"""
import pytest
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.evidence import Evidence, EvidenceEngine, EvidenceType
from app.agentos.confidence import ConfidenceEngine, ConfidenceTier
from app.agentos.agents.intent import IntentAgent
from app.agentos.agents.supervisor import SupervisorAgent
from app.agentos.schemas import AgentRole, IntentOutput, SupervisorOutput


def test_intent_agent_normalization_and_parameter_extraction():
    agent = IntentAgent()
    ctx = WorkflowContext(
        workflow_id="wf-intent-01",
        correlation_id="corr-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL 16 cluster on three RHEL 9 nodes with 500GB storage and Datadog",
    )
    out = agent.execute(ctx)
    assert isinstance(out, IntentOutput)
    assert out.automation_domain == "database"
    assert out.known_parameters.get("db_version") == 16
    assert out.known_parameters.get("node_count") == 3
    assert out.known_parameters.get("os_platform") == "rhel9"
    assert out.known_parameters.get("storage_capacity") == "500GB"
    assert out.known_parameters.get("monitoring") == "datadog"
    assert out.ambiguity_classification == "UNAMBIGUOUS"
    assert out.requires_operator_input is False


def test_assumption_elimination_halts_in_waiting_for_input():
    agent = IntentAgent()
    # Ambiguous prompt lacking environment, targets, and parameters
    ctx = WorkflowContext(
        workflow_id="wf-intent-02",
        correlation_id="corr-02",
        requester_id="alice",
        original_request="restart database",
    )
    out = agent.execute(ctx)
    assert out.requires_operator_input is True
    assert "target_host" in out.missing_parameters
    assert out.proposed_next_state == WorkflowState.WAITING_FOR_INPUT.value
    assert out.clarification_prompt is not None


def test_evidence_engine_evaluation():
    e1 = Evidence(
        evidence_id="ev-01",
        evidence_type=EvidenceType.CATALOG_ARTIFACT,
        source_uri="vulcan://catalog/postgresql_cluster",
        summary="Curated role matching PostgreSQL 16",
        confidence_weight=0.95,
    )
    e2 = Evidence(
        evidence_id="ev-02",
        evidence_type=EvidenceType.POLICY_RESULT,
        source_uri="vulcan://policy/POL-MAKER-CHECKER",
        summary="Maker-checker policy requirement",
        confidence_weight=0.90,
    )

    res = EvidenceEngine.evaluate_coverage(
        [e1, e2],
        required_types=[EvidenceType.CATALOG_ARTIFACT, EvidenceType.POLICY_RESULT],
        min_weight=0.80,
    )
    assert res["adequate"] is True
    assert res["coverage_score"] >= 0.80
    assert len(res["missing_types"]) == 0

    # Missing required type fails closed
    res_fail = EvidenceEngine.evaluate_coverage(
        [e1],
        required_types=[EvidenceType.POSTCONDITION_RESULT],
    )
    assert res_fail["adequate"] is False
    assert "postcondition_result" in res_fail["missing_types"]


def test_calibrated_confidence_engine():
    # High confidence case
    assess_high = ConfidenceEngine.calculate_confidence(
        model_confidence=0.95,
        retrieval_score=0.90,
        has_catalog_exact_match=True,
        cross_agent_agreement=1.0,
        historical_accuracy=0.98,
        deterministic_validation_passed=True,
        evidence_coverage=0.95,
        environment="PROD",
    )
    assert assess_high.tier == ConfidenceTier.HIGH
    assert assess_high.calibrated_score >= 0.88
    assert assess_high.requires_clarification is False

    # Low confidence when deterministic validation fails
    assess_fail = ConfidenceEngine.calculate_confidence(
        model_confidence=0.99,
        deterministic_validation_passed=False,
        environment="PROD",
    )
    assert assess_fail.tier == ConfidenceTier.LOW
    assert assess_fail.requires_clarification is True
