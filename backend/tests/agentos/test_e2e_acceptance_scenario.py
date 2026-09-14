"""
Project Vulcan: Section 59 End-to-End Acceptance Scenario Test
Author: Architectural Review Board & AgentOS Core Team

Tests the complete canonical governed workflow:
User: "Build and deploy a hardened PostgreSQL 16 production cluster on three RHEL 9 nodes
      with 500GB storage, Datadog monitoring, S3 backups, ServiceNow change control,
      and CyberArk credentials."
"""
import pytest
from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository
from app.agentos.context import WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.agentos.repository import PostgresAgentWorkflowRepository
from app.domain.external_resource_entities import (
    AuthMode,
    ExternalResource,
    HealthStatus,
    ResourceCategory,
    ResourceEnvironment,
)


def test_section_59_end_to_end_acceptance_workflow():
    # 1. Setup isolated persistence and external resources repository
    ext_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=True)
    agent_repo = PostgresAgentWorkflowRepository()
    kernel = AgentOSKernel(repository=agent_repo, external_resource_repo=ext_repo)

    prompt = (
        "Build and deploy a hardened PostgreSQL 16 production cluster on three RHEL 9 nodes "
        "with 500GB storage, Datadog monitoring, S3 backups, ServiceNow change control, "
        "and CyberArk credentials."
    )
    requester = "operator-alice@corp.internal"
    environment = "PROD"

    # Step 1: Create workflow (RECEIVED)
    ctx = kernel.create_workflow(original_request=prompt, requester_id=requester, environment=environment)
    assert ctx.current_state == WorkflowState.RECEIVED
    wf_id = ctx.workflow_id

    # Step 2: Intent Understanding & Parameter Extraction
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.DISCOVERING
    assert ctx.normalized_intent["automation_domain"] == "database"
    assert ctx.normalized_intent["known_parameters"]["db_version"] == 16
    assert ctx.normalized_intent["known_parameters"]["node_count"] == 3
    assert ctx.normalized_intent["known_parameters"]["os_platform"] == "rhel9"
    assert ctx.normalized_intent["known_parameters"]["storage_capacity"] == "500GB"

    # Step 3: Discovery Intelligence (prioritizes Curated Catalog)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.PLANNING
    assert len(ctx.discovered_assets) >= 1
    assert any(c.get("is_curated") for c in ctx.discovered_assets)

    # Step 4: Planner Agent (Selects COMPOSE over raw GENERATE)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.COMPOSING
    assert ctx.automation_plan["decision"] == "COMPOSE"

    # Step 5: Composer + Builder (Assembles DAG & compiles specification-first)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.RESOLVING_RESOURCES
    assert len(ctx.generated_artifacts) == 1
    artifact = ctx.generated_artifacts[0]
    assert len(artifact["artifact_sha256"]) == 64
    assert len(artifact["files"]) >= 4

    # Step 6 & 7: Resource Intelligence & Dependency Resolution
    # Notice Datadog is requested in prompt, but not in seeded defaults!
    # Resource Agent will detect missing Datadog and halt in WAITING_FOR_RESOURCE.
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.WAITING_FOR_RESOURCE
    assert "datadog" in ctx.normalized_intent.get("known_parameters", {}).get("monitoring", "")

    # Verify workflow is safely paused
    assert ctx.current_state == WorkflowState.WAITING_FOR_RESOURCE

    # Step 8 & 9: Operator configures Datadog and S3 via External Resources Console
    ext_repo.save(
        ExternalResource(
            resource_id="res-datadog-prod",
            provider="datadog",
            category=ResourceCategory.OBSERVABILITY,
            display_name="Corporate Datadog APM",
            environment=ResourceEnvironment.PROD,
            endpoint="https://api.datadoghq.com",
            auth_mode=AuthMode.API_KEY,
            enabled=True,
            secret_refs={"api_key": "vault://secret/vulcan/datadog/api_key"},
            health_status=HealthStatus.CONNECTED,
        ),
        actor=requester,
    )
    ext_repo.save(
        ExternalResource(
            resource_id="res-s3-prod",
            provider="s3",
            category=ResourceCategory.STORAGE_DATA,
            display_name="Corporate S3 Backup Store",
            environment=ResourceEnvironment.PROD,
            endpoint="https://s3.amazonaws.com",
            auth_mode=AuthMode.API_KEY,
            enabled=True,
            secret_refs={"aws_access_key_id": "vault://secret/vulcan/aws/key", "aws_secret_access_key": "vault://secret/vulcan/aws/secret"},
            health_status=HealthStatus.CONNECTED,
        ),
        actor=requester,
    )

    # Step 10: Operator clicks "Resume Workflow" (no re-typing of prompt required!)
    ctx = kernel.resume_after_resource_config(wf_id)
    assert ctx.current_state == WorkflowState.RESOLVING_RESOURCES

    # Step 11: Re-evaluate resources with Datadog now available
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.VALIDATING

    # Step 12: Preflight Validation Factory (Syntax, Lint, Molecule Sandbox, Secret Scan)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.SECURITY_REVIEW
    assert len(ctx.validation_results) >= 4

    # Step 13: Security Agent (Scans for injection, shell downloads, permission leaks)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.CRITIC_REVIEW
    assert len(ctx.security_findings) == 0

    # Step 14: Critic Agent (Adversarial challenge on assumptions & rollback)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.POLICY_CHECK

    # Step 15: Policy Check (PROD + HIGH risk requires Maker-Checker sign-off)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.WAITING_FOR_APPROVAL

    # Step 16: Maker-Checker Enforcement
    # Requester Alice cannot self-approve
    with pytest.raises(PermissionError):
        kernel.approve_workflow(wf_id, approver_id=requester)

    # Independent Checker Bob signs off
    checker = "sre-lead-bob@corp.internal"
    ctx = kernel.approve_workflow(wf_id, approver_id=checker, reason="Reviewed architecture and change ticket CHG0091823.")
    assert ctx.current_state == WorkflowState.EXECUTION_READY
    assert len(ctx.approval_records) == 1

    # Step 17: Constrained Execution under ExecutionCapabilityToken
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.VERIFYING
    assert ctx.execution_result["exit_code"] == 0
    assert "ok=5" in ctx.execution_result["stdout"]

    # Step 18: Independent Desired-State Verification (Exit code 0 is NOT enough!)
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.SUCCESS
    assert ctx.postcondition_verification["all_passed"] is True
    assert ctx.postcondition_verification["actual_state_matches_desired"] is True
    probes = ctx.postcondition_verification["probes"]
    assert len(probes) >= 4

    # Step 19: Curation Agent proposes promotion to CANDIDATE
    ctx = kernel.step(wf_id)
    assert ctx.current_state == WorkflowState.EVALUATING
    assert ctx.curation_state["proposed_promotion"] is True
    assert ctx.curation_state["promotion_tier"] == "CANDIDATE"

    # Step 20: Eval Agent records multi-metric evaluation and bootstrap statistics
    ctx = kernel.step(wf_id)
    assert ctx.eval_result["pass_rate"] >= 80.0
    assert ctx.eval_result["gate_passed"] is True

    # Step 21: Cryptographic Event Audit Trail Verification
    events = kernel.repository.get_events(wf_id)
    assert len(events) >= 12
    # Verify hash chain continuity: ev[i].current_hash == ev[i+1].prev_hash
    for i in range(len(events) - 1):
        if events[i+1].prev_hash != "0" * 64:
            assert events[i+1].prev_hash == events[i].current_hash
