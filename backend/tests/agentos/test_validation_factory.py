"""
Project Vulcan: Tests for Validation Factory (AGENT-07)
"""
import pytest
from app.agentos.agents.validator import ValidatorAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import ValidationCheckStatus


def test_validator_fails_on_hardcoded_plaintext_secrets():
    agent = ValidatorAgent()
    ctx = WorkflowContext(
        workflow_id="wf-val-01",
        correlation_id="corr-val-01",
        requester_id="alice",
        original_request="Deploy DB",
        generated_artifacts=[{
            "files": [
                {"path": "playbook.yml", "content": 'password: "supersecretplaintextpassword"'}
            ]
        }],
    )
    out = agent.execute(ctx)
    assert out.all_passed is False
    assert out.proposed_next_state == WorkflowState.VALIDATION_FAILED.value
    secret_checks = [c for c in out.checks if c.check_name == "secret_scan"]
    assert len(secret_checks) == 1
    assert secret_checks[0].status == ValidationCheckStatus.FAIL


def test_validator_fails_on_destructive_commands():
    agent = ValidatorAgent()
    ctx = WorkflowContext(
        workflow_id="wf-val-02",
        correlation_id="corr-val-02",
        requester_id="alice",
        original_request="Deploy DB",
        generated_artifacts=[{
            "files": [
                {"path": "playbook.yml", "content": 'command: rm -rf /'}
            ]
        }],
    )
    out = agent.execute(ctx)
    assert out.all_passed is False
    cmd_checks = [c for c in out.checks if c.check_name == "dangerous_command_check"]
    assert cmd_checks[0].status == ValidationCheckStatus.FAIL


def test_validator_passes_hardened_spec():
    agent = ValidatorAgent()
    ctx = WorkflowContext(
        workflow_id="wf-val-03",
        correlation_id="corr-val-03",
        requester_id="alice",
        original_request="Deploy DB",
        generated_artifacts=[{
            "files": [
                {"path": "playbook.yml", "content": '---\n- name: Clean playbook\n  ansible.builtin.package:\n    name: postgresql16\n'}
            ]
        }],
    )
    out = agent.execute(ctx)
    assert out.all_passed is True
    assert out.proposed_next_state == WorkflowState.SECURITY_REVIEW.value
    assert all(c.status in (ValidationCheckStatus.PASS, ValidationCheckStatus.SKIPPED) for c in out.checks)
    assert any(c.status == ValidationCheckStatus.PASS for c in out.checks)


def test_validator_fails_closed_on_empty_artifacts():
    agent = ValidatorAgent()
    ctx = WorkflowContext(
        workflow_id="wf-val-04",
        correlation_id="corr-val-04",
        requester_id="alice",
        original_request="Deploy DB",
        generated_artifacts=[],  # No artifacts!
    )
    out = agent.execute(ctx)
    assert out.all_passed is False
    assert out.proposed_next_state == WorkflowState.VALIDATION_FAILED.value

