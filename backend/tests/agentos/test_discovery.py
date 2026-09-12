"""
Project Vulcan: Tests for Discovery Intelligence & Trust Model (AGENT-03)
"""
import pytest
from app.agentos.agents.discovery import DiscoveryAgent
from app.agentos.context import WorkflowContext
from app.agentos.trust import ProvenanceRecord, TrustScoringEngine, TrustState


def test_discovery_agent_finds_curated_and_external():
    agent = DiscoveryAgent()
    ctx = WorkflowContext(
        workflow_id="wf-disc-01",
        correlation_id="corr-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL 16 on RHEL 9",
    )
    out = agent.execute(ctx)
    assert out.total_found >= 2
    assert out.exact_catalog_match is True
    curated = [c for c in out.candidates if c.is_curated]
    assert len(curated) == 1
    assert curated[0].identifier == "vulcan.database.postgresql_cluster"
    assert curated[0].trust_state == "CURATED"


def test_trust_scoring_rejects_dangerous_commands():
    prov = ProvenanceRecord(
        source="galaxy",
        repository_url="https://galaxy.ansible.com/bad/role",
        publisher="unknown",
        version="1.0.0",
        immutable_sha="1" * 40,
        dangerous_commands_found=["rm -rf /"],
    )
    res = TrustScoringEngine.evaluate(prov)
    assert res["trust_state"] == TrustState.REJECTED
    assert res["can_execute_in_prod"] is False
    assert res["trust_score"] == 0.0


def test_trust_scoring_quarantines_known_vulnerabilities():
    prov = ProvenanceRecord(
        source="galaxy",
        repository_url="https://galaxy.ansible.com/vulnerable/role",
        publisher="community",
        version="1.0.0",
        immutable_sha="2" * 40,
        known_vulnerabilities=["CVE-2024-1234"],
    )
    res = TrustScoringEngine.evaluate(prov)
    assert res["trust_state"] == TrustState.QUARANTINED
    assert res["can_execute_in_prod"] is False
