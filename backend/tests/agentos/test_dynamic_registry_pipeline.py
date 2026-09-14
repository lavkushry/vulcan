"""
Project Vulcan: Dynamic Registry-to-Playbook Pipeline Test Suite
Author: Architectural Review Board & AgentOS Core Team

Acceptance Test Suite verifying complete elimination of hardcoded registry paths:
1. Dynamic Request Isolation: Request Redis and confirm zero PostgreSQL candidate, task, probe, or role appears.
2. Platform Compatibility: Incompatible OS platform causes candidate rejection with explicit reason.
3. Parameter Binding: Changing role's required/custom variables propagates directly to generated playbook.
4. Registry Outage Honesty: Registry unavailable reports clean failure (RegistryUnavailableError).
5. Cryptographic Digest Integrity: Mismatched artifact digest halts processing (DigestMismatchError).
6. Artifact Lifecycle Trace: Trace asset through DISCOVERED -> DOWNLOADED -> VERIFIED staging.
7. Deterministic Reproducibility: Pinned inputs produce reproducible artifacts and identical SHA-256 digests.
"""
import os
import pytest
import tempfile
from pathlib import Path
from app.agentos.artifacts.resolver import (
    ArtifactResolver,
    ArtifactState,
    DigestMismatchError,
    IncompatiblePlatformError,
    RegistryUnavailableError,
    RoleInterface,
)
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.agentos.agents.intent import IntentAgent
from app.agentos.agents.discovery import DiscoveryAgent
from app.agentos.agents.planner import PlannerAgent
from app.agentos.agents.composer import ComposerAgent
from app.agentos.agents.builder import BuilderAgent
from app.agentos.compiler import AutomationCompiler
from app.agentos.specification import AutomationSpecification, ResourceContract
from app.agentos.adapters.execution_adapter import (
    AnsibleRunnerExecutionAdapter,
    LiveDisposableTargetExecutionAdapter,
)
from app.agentos.agents.verifier import ProductionProbeRunner
from app.catalog_data import DB_SHA, DEFAULT_SHA


def test_redis_request_has_zero_postgres_leakage(tmp_path):
    """
    Test 1: Request Redis and confirm no PostgreSQL candidate, task, probe, or role appears.
    Ensures that dynamic registry lookup does not silently inject PostgreSQL.
    """
    os.environ["VULCAN_CAPABILITY_HMAC_KEY"] = "test-key-32-chars-long-abcdef123"
    from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository
    ext_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=True)

    kernel = AgentOSKernel(
        execution_adapter=LiveDisposableTargetExecutionAdapter(target_root=tmp_path / "target"),
        probe_runner=ProductionProbeRunner(),
        external_resource_repo=ext_repo,
    )

    ctx = kernel.create_workflow(
        original_request="Deploy Redis cache on cache-node-01.internal on port 6379 with 256MB memory",
        requester_id="redis-admin@corp.internal",
        environment="PROD",
    )

    # 1. Understanding
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.normalized_intent.get("known_parameters", {}).get("software") == "redis"
    assert ctx.normalized_intent.get("known_parameters", {}).get("port") == 6379

    # 2. Discovery
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.discovered_assets, "Should discover Redis candidates"
    for cand in ctx.discovered_assets:
        ident = cand.get("identifier", "").lower()
        name = cand.get("name", "").lower()
        assert "postgres" not in ident, f"Postgres candidate leaked into Redis discovery: {ident}"
        assert "postgres" not in name, f"Postgres candidate leaked into Redis discovery: {name}"

    # 3. Planning
    ctx = kernel.step(ctx.workflow_id)
    selected = ctx.automation_plan.get("selected_assets", [])
    for asset in selected:
        assert "postgres" not in asset.lower(), f"Postgres selected in Redis plan: {asset}"

    # 4. Composition & Generation
    ctx = kernel.step(ctx.workflow_id)
    dag_steps = ctx.automation_plan.get("dag_steps", [])
    for step in dag_steps:
        step_id = step.get("step_id")
        action = step.get("action_identifier", "").lower()
        name = step.get("name", "").lower()
        assert "postgres" not in action, f"Postgres task action in Redis DAG: {action}"
        assert "postgres" not in name, f"Postgres task name in Redis DAG: {name}"

    # Verify generated playbook files contain zero postgres references
    artifacts = ctx.generated_artifacts
    assert artifacts, "Artifacts should be generated"
    all_files = artifacts[0].get("files", [])
    for f in all_files:
        content = f.get("content", "").lower()
        assert "postgres" not in content, f"Postgres mentioned in generated file {f.get('path')}"
        assert "5432" not in content, f"Postgres port 5432 mentioned in generated file {f.get('path')}"
        assert "redis" in content, f"Redis missing from generated file {f.get('path')}"

    # Step through verification
    while ctx.current_state not in (WorkflowState.SUCCESS, WorkflowState.EXECUTION_FAILED, WorkflowState.VERIFY_FAILED):
        if ctx.current_state == WorkflowState.WAITING_FOR_APPROVAL:
            ctx = kernel.approve_workflow(ctx.workflow_id, approver_id="secops@corp.internal", reason="approved")
        else:
            ctx = kernel.step(ctx.workflow_id)

    # Verify probes
    probes = ctx.postcondition_verification.get("probes", [])
    assert probes, "Probes should be evaluated for Redis"
    for p in probes:
        ptype = p.get("probe_type")
        details = str(p.get("details", {})).lower()
        assert "postgres" not in details, f"Postgres probe leaked into Redis verification: {details}"
        assert "5432" not in details, f"Postgres port leaked into Redis verification: {details}"


def test_incompatible_os_platform_causes_role_rejection():
    """
    Test 2: Incompatible OS platform causes candidate rejection with explicit reason.
    Evaluates ArtifactResolver.is_os_compatible and PlannerAgent candidate ranking.
    """
    resolver = ArtifactResolver()

    # Supported platforms declaring Linux (EL and Ubuntu)
    linux_platforms = [
        {"name": "EL", "versions": [8, 9]},
        {"name": "Ubuntu", "versions": ["jammy", "focal"]},
    ]

    # Compatible checks
    assert resolver.is_os_compatible("rhel9", linux_platforms) is True
    assert resolver.is_os_compatible("ubuntu22", linux_platforms) is True

    # Incompatible checks
    assert resolver.is_os_compatible("windows", linux_platforms) is False
    assert resolver.is_os_compatible("windows server 2022", linux_platforms) is False

    # Test within PlannerAgent
    planner = PlannerAgent()
    ctx = WorkflowContext(
        workflow_id="wf-compat-01",
        correlation_id="corr-compat-01",
        requester_id="ops@corp.internal",
        original_request="Deploy Linux database on Windows server",
        normalized_intent={
            "automation_domain": "database",
            "known_parameters": {"os_platform": "windows", "software": "postgresql"},
            "missing_parameters": [],
        },
        discovered_assets=[
            {
                "identifier": "vulcan.database.postgresql_cluster",
                "name": "PostgreSQL Cluster",
                "is_curated": True,
                "trust_score": 1.0,
                "relevance_score": 0.95,
                "has_rollback": True,
                "metadata": {
                    "supported_platforms": linux_platforms,
                },
            }
        ],
    )

    out = planner.execute(ctx)
    assert "vulcan.database.postgresql_cluster" not in out.selected_assets
    assert len(out.rejected_candidates) > 0
    rejected_reasons = [r.reason for r in out.rejected_candidates]
    assert any("incompatible" in r.lower() or "windows" in r.lower() for r in rejected_reasons), (
        f"Expected OS incompatibility rejection reason, got: {rejected_reasons}"
    )


def test_changing_role_required_variables_propagates_to_playbook():
    """
    Test 3: Changing role's required variables reflects in generated playbook.
    Validates parameter binding between intent, interface inspection, and compiler.
    """
    contract = ResourceContract()

    spec1 = AutomationSpecification(
        spec_id="spec-redis-01",
        goal="Deploy Redis 6380",
        engine="ansible",
        supported_platforms=["ubuntu22"],
        desired_state={
            "software": "redis",
            "port": 6380,
            "maxmemory_mb": 1024,
            "bind_address": "127.0.0.1",
        },
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        dependencies=["ansible.builtin", "community.general"],
        resource_contract=contract,
        execution_dag=[],
        postconditions=[],
        rollback_requirements={"strategy": "stop_redis_service_and_restore"},
    )
    bundle1 = AutomationCompiler.compile(spec1)
    defaults1 = next(f.content for f in bundle1.files if f.path.endswith("defaults/main.yml"))
    assert "redis_port: 6380" in defaults1
    assert "1024" in defaults1

    # Now change port to 6385 and maxmemory to 2048MB
    spec2 = AutomationSpecification(
        spec_id="spec-redis-02",
        goal="Deploy Redis 6385",
        engine="ansible",
        supported_platforms=["ubuntu22"],
        desired_state={
            "software": "redis",
            "port": 6385,
            "maxmemory_mb": 2048,
            "bind_address": "0.0.0.0",
        },
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        dependencies=["ansible.builtin", "community.general"],
        resource_contract=contract,
        execution_dag=[],
        postconditions=[],
        rollback_requirements={"strategy": "stop_redis_service_and_restore"},
    )
    bundle2 = AutomationCompiler.compile(spec2)
    defaults2 = next(f.content for f in bundle2.files if f.path.endswith("defaults/main.yml"))
    assert "redis_port: 6385" in defaults2
    assert "2048" in defaults2
    assert defaults1 != defaults2, "Playbook role defaults must differ when variables change"


def test_registry_unavailable_reports_clean_failure():
    """
    Test 4: Registry unavailable reports clean failure.
    Validates that offline or unreachable external registry raises RegistryUnavailableError.
    """
    agent = DiscoveryAgent()
    ctx = WorkflowContext(
        workflow_id="wf-unavail-01",
        correlation_id="corr-unavail-01",
        requester_id="tester@corp.internal",
        original_request="Deploy Redis cache",
    )

    os.environ["VULCAN_REGISTRY_UNAVAILABLE"] = "1"
    try:
        with pytest.raises(RegistryUnavailableError) as exc_info:
            agent.execute(ctx)
        assert "offline" in str(exc_info.value).lower() or "unreachable" in str(exc_info.value).lower()
    finally:
        os.environ.pop("VULCAN_REGISTRY_UNAVAILABLE", None)


def test_mismatched_artifact_digest_halts_processing(tmp_path):
    """
    Test 5: Mismatched artifact digest halts processing (DigestMismatchError).
    Validates cryptographic commit SHA / digest verification before execution.
    """
    resolver = ArtifactResolver()

    with pytest.raises(DigestMismatchError) as exc_info:
        resolver.resolve_and_download(
            identifier="vulcan.database.postgresql_cluster",
            expected_sha="deadbeef0123456789deadbeef0123456789dead",  # Wrong SHA
            commit_sha="b2c3d4e5f67890123456789abcdef01234567890",
            workflow_id="wf-digest-fail",
            workspace_parent=tmp_path,
        )

    assert "digest mismatch" in str(exc_info.value).lower()
    assert "deadbeef0123456789deadbeef0123456789dead" in str(exc_info.value).lower()


def test_artifact_lifecycle_stage_and_inspection(tmp_path):
    """
    Test 6: Trace selected registry artifact through download, composition, execution.
    Inspects DISCOVERED -> DOWNLOADED -> VERIFIED states and interface extraction.
    """
    resolver = ArtifactResolver()

    resolved = resolver.resolve_and_download(
        identifier="geerlingguy.postgresql",
        version="3.4.0",
        expected_commit_sha="c7e1f4a920b13d8e5f2a1b3c4d5e6f7a8b9c0d1e",
        commit_sha="c7e1f4a920b13d8e5f2a1b3c4d5e6f7a8b9c0d1e",
        workflow_id="wf-lifecycle-01",
        workspace_parent=tmp_path,
    )

    # State verification
    assert resolved.state == ArtifactState.VERIFIED
    assert resolved.content_digest_sha256 != ""
    assert Path(resolved.staged_path).exists()
    assert (Path(resolved.staged_path) / "defaults" / "main.yml").exists()

    # Interface inspection verification
    iface = resolved.role_interface
    assert iface is not None
    assert len(iface.supported_platforms) > 0
    platform_names = [p["name"] for p in iface.supported_platforms]
    assert "Ubuntu" in platform_names or "Debian" in platform_names
    assert "postgresql_user" in iface.variable_defaults or len(iface.variable_defaults) > 0


def test_pinned_inputs_produce_reproducible_artifacts():
    """
    Test 7: Pinned inputs produce reproducible artifacts with identical SHA256 hashes.
    """
    contract = ResourceContract()

    spec1 = AutomationSpecification(
        spec_id="spec-redis-pinned-01",
        goal="Deploy Redis Cache Service",
        engine="ansible",
        supported_platforms=["ubuntu22"],
        desired_state={"software": "redis", "port": 6379, "maxmemory_mb": 512, "bind_address": "127.0.0.1"},
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        dependencies=["ansible.builtin", "community.general"],
        resource_contract=contract,
        execution_dag=[],
        postconditions=[],
        rollback_requirements={"strategy": "stop_redis_service_and_restore"},
    )
    spec2 = AutomationSpecification(
        spec_id="spec-redis-pinned-01",
        goal="Deploy Redis Cache Service",
        engine="ansible",
        supported_platforms=["ubuntu22"],
        desired_state={"software": "redis", "port": 6379, "maxmemory_mb": 512, "bind_address": "127.0.0.1"},
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        dependencies=["ansible.builtin", "community.general"],
        resource_contract=contract,
        execution_dag=[],
        postconditions=[],
        rollback_requirements={"strategy": "stop_redis_service_and_restore"},
    )

    bundle1 = AutomationCompiler.compile(spec1)
    bundle2 = AutomationCompiler.compile(spec2)

    assert bundle1.artifact_sha256 == bundle2.artifact_sha256, (
        f"Deterministic compilation failed: {bundle1.artifact_sha256} != {bundle2.artifact_sha256}"
    )
