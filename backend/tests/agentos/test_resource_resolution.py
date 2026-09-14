"""
Project Vulcan: Tests for Resource Intelligence & WAITING_FOR_RESOURCE Lifecycle (AGENT-06)
"""
import pytest
from app.agentos.agents.resource import ResourceAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository


def test_resource_agent_detects_missing_datadog_and_halts():
    # Empty repository without Datadog configured
    empty_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=False)
    agent = ResourceAgent(resource_repo=empty_repo)

    ctx = WorkflowContext(
        workflow_id="wf-res-01",
        correlation_id="corr-res-01",
        requester_id="alice",
        original_request="Deploy PostgreSQL with Datadog and CyberArk",
    )
    out = agent.execute(ctx)
    assert out.all_dependencies_satisfied is False
    assert "cyberark" in out.missing_resources
    assert "datadog" in out.missing_resources
    assert out.proposed_next_state == WorkflowState.WAITING_FOR_RESOURCE.value


def test_resource_pause_and_resumption_without_repeating_prompt():
    ext_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=True)
    kernel = AgentOSKernel(external_resource_repo=ext_repo)

    ctx = kernel.create_workflow(
        original_request="Deploy PostgreSQL with Datadog monitoring and CyberArk PAM",
        requester_id="alice@corp.internal",
    )

    # Transition to WAITING_FOR_RESOURCE manually to simulate missing resource pause
    ctx.transition_to(WorkflowState.UNDERSTANDING)
    ctx.transition_to(WorkflowState.DISCOVERING)
    ctx.transition_to(WorkflowState.PLANNING)
    ctx.transition_to(WorkflowState.COMPOSING)
    ctx.transition_to(WorkflowState.RESOLVING_RESOURCES)
    ctx.transition_to(WorkflowState.WAITING_FOR_RESOURCE)
    kernel.repository.save_workflow(ctx)

    # Operator configures Datadog in External Resources UI and clicks "Resume"
    resumed_ctx = kernel.resume_after_resource_config(ctx.workflow_id)

    # Must resume directly into RESOLVING_RESOURCES without losing original request
    assert resumed_ctx.current_state == WorkflowState.RESOLVING_RESOURCES
    assert resumed_ctx.original_request == "Deploy PostgreSQL with Datadog monitoring and CyberArk PAM"
    assert resumed_ctx.version > ctx.version
