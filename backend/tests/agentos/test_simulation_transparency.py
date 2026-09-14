"""
Project Vulcan: Simulation Transparency Tests (P0 #1, #2, #3)
Verifies that simulated agents are honestly labeled and unavailable checks
return SKIPPED instead of fake PASS.
"""
import pytest
from app.agentos.agents.validator import ValidatorAgent
from app.agentos.agents.verifier import VerifierAgent, SimulationProbeRunner
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import ValidationCheckStatus


def _make_ctx_with_artifacts(content="---\n- hosts: all\n  tasks:\n    - name: test\n      debug: msg=hello\n"):
    ctx = WorkflowContext(
        workflow_id="wf-sim-test",
        correlation_id="CORR-SIM",
        requester_id="tester",
        original_request="Install PostgreSQL 16 on db-cluster.internal with Datadog monitoring",
        current_state=WorkflowState.VALIDATING,
    )
    ctx.generated_artifacts = [{
        "files": [{"path": "playbook.yml", "content": content}],
        "test_files": [],
        "rollback_files": [],
    }]
    return ctx


def test_validator_skips_unavailable_checks():
    """Idempotency and molecule checks must return SKIPPED, not fake PASS."""
    agent = ValidatorAgent()
    ctx = _make_ctx_with_artifacts()
    out = agent.execute(ctx)
    check_map = {c.check_name: c for c in out.checks}
    assert check_map["idempotency_verification"].status == ValidationCheckStatus.SKIPPED
    assert check_map["molecule_sandbox_test"].status == ValidationCheckStatus.SKIPPED
    assert out.idempotency_verified is False
    assert out.sandbox_passed is False


def test_validator_yaml_parsing_catches_invalid():
    """Feed invalid YAML -> syntax check must FAIL."""
    agent = ValidatorAgent()
    ctx = _make_ctx_with_artifacts(content="{invalid yaml: [unterminated")
    out = agent.execute(ctx)
    check_map = {c.check_name: c for c in out.checks}
    assert check_map["syntax_check"].status == ValidationCheckStatus.FAIL


def test_validator_secret_scan_catches_secrets():
    """Embedded plaintext secret must be caught."""
    agent = ValidatorAgent()
    ctx = _make_ctx_with_artifacts(content='---\npassword: "hunter2"\n')
    out = agent.execute(ctx)
    check_map = {c.check_name: c for c in out.checks}
    assert check_map["secret_scan"].status == ValidationCheckStatus.FAIL


def test_verifier_simulation_probe_labeled():
    """Simulation probe results must carry simulation=True metadata."""
    agent = VerifierAgent(probe_runner=SimulationProbeRunner())
    ctx = WorkflowContext(
        workflow_id="wf-sim-verify",
        correlation_id="CORR-V",
        requester_id="tester",
        original_request="Install PostgreSQL 16",
        current_state=WorkflowState.VERIFYING,
    )
    ctx.execution_result = {"target_id": "db-test.internal"}
    out = agent.execute(ctx)
    assert out.all_passed is True
    for probe in out.probes:
        assert probe.details.get("simulation") is True, f"Probe {probe.probe_id} missing simulation label"
    assert "SIMULATION" in out.rationale


def test_validator_skipped_checks_dont_block_workflow():
    """SKIPPED checks should not cause validation failure; only FAIL should."""
    agent = ValidatorAgent()
    ctx = _make_ctx_with_artifacts()
    out = agent.execute(ctx)
    assert out.all_passed is True  # Only PASS and SKIPPED, no FAIL
    assert out.proposed_next_state == WorkflowState.SECURITY_REVIEW.value
