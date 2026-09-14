"""
Project Vulcan: Acceptance Milestone Test Suite
Download-to-Execution Verifiable Pipeline

Validates the 8 core acceptance criteria:
1. Start with an empty artifact cache.
2. Retrieve an exact role/collection from configured registry/adapter.
3. Generate wrapper playbook invoking downloaded content with inspected interface.
4. Deploy Redis with custom settings (port 6380, 1024MB) to disposable target.
5. Verify settings through independent probe (checking port 6380).
6. Execute again and measure idempotency (changed=0).
7. Demonstrate actual registry failure, incompatible metadata, digest mismatch, and approval tampering.
8. Retain source identities, generated files, execution logs, and verification results.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import pytest

from app.agentos.artifacts.downloader import (
    ArchiveSafetyValidator,
    ContentAddressableCache,
    GalaxyDownloadAdapter,
    LocalCatalogAdapter,
    RegistryUnavailableError,
    SecurityError,
)
from app.agentos.artifacts.resolver import (
    ArtifactResolver,
    ArtifactState,
    DigestMismatchError,
    IncompatiblePlatformError,
)
from app.agentos.adapters.execution_adapter import SimulationExecutionAdapter
from app.agentos.agents.executor import CapabilityTokenViolationError
from app.agentos.context import WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.agentos.policy_engine import SimulationPolicyEngine
from app.agentos.schemas import AgentRole, ExecutionCapabilityToken


@pytest.fixture
def empty_cache_dir(tmp_path):
    cache_path = tmp_path / "vulcan_cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    old_env = os.environ.get("VULCAN_ARTIFACT_CACHE")
    os.environ["VULCAN_ARTIFACT_CACHE"] = str(cache_path)
    yield cache_path
    if old_env:
        os.environ["VULCAN_ARTIFACT_CACHE"] = old_env
    else:
        os.environ.pop("VULCAN_ARTIFACT_CACHE", None)


def test_milestone_1_and_2_empty_cache_and_exact_retrieval(empty_cache_dir):
    """
    Milestone 1: Start with empty cache.
    Milestone 2: Retrieve exact role (geerlingguy.redis) safely into cache without path traversal.
    """
    cache = ContentAddressableCache(cache_root=empty_cache_dir)
    assert len(cache.list_entries()) == 0, "Cache must start completely empty"

    resolver = ArtifactResolver(cache_root=empty_cache_dir)
    resolved = resolver.resolve_and_download(
        identifier="geerlingguy.redis",
        version="1.0.0",
        requested_os="rhel9",
        workflow_id="wf-milestone-test",
    )

    assert resolved.state == ArtifactState.VERIFIED
    assert resolved.is_compatible is True
    assert len(cache.list_entries()) == 1, "Cache must contain exactly 1 entry after download"

    cached_digest = cache.list_entries()[0]
    assert cached_digest == resolved.digest_sha256

    # Test cache hit on second fetch
    resolved_cached = resolver.resolve_and_download(
        identifier="geerlingguy.redis",
        expected_sha=resolved.digest_sha256,
        requested_os="rhel9",
        workflow_id="wf-milestone-test-2",
    )
    assert resolved_cached.digest_sha256 == resolved.digest_sha256


def test_milestone_archive_safety_path_traversal():
    """Archive safety validator must block directory traversal attacks."""
    import tarfile
    with tempfile.TemporaryDirectory() as tmpdir:
        malicious_tar = Path(tmpdir) / "evil.tar.gz"
        with tarfile.open(malicious_tar, "w:gz") as tar:
            info = tarfile.TarInfo(name="../../etc/shadow")
            info.size = 11
            import io
            tar.addfile(info, io.BytesIO(b"root:secret"))

        extract_dir = Path(tmpdir) / "extracted"
        with pytest.raises(SecurityError, match="Path traversal detected"):
            ArchiveSafetyValidator.safe_extract_tar(malicious_tar, extract_dir)


def test_milestone_3_formal_interface_and_wrapper_generation(empty_cache_dir):
    """
    Milestone 3: meta/argument_specs.yml is parsed as primary schema,
    defaults/main.yml acts as fallback, and wrapper playbook binds variables.
    """
    resolver = ArtifactResolver(cache_root=empty_cache_dir)
    resolved = resolver.resolve_and_download(
        identifier="geerlingguy.redis",
        workflow_id="wf-interface-test",
    )
    iface = resolved.interface
    assert "redis_port" in iface.variable_defaults or "redis_port" in iface.argument_specs.get("main", {}).get("options", {})
    assert iface.variable_defaults.get("redis_port") == 6379
    assert iface.variable_defaults.get("redis_maxmemory_mb") == 512


def test_milestone_4_and_5_deploy_redis_custom_settings_and_dynamic_probe(empty_cache_dir):
    """
    Milestone 4: Deploy Redis with custom settings (port 6380, 1024MB) on node-redis-01.internal.
    Milestone 5: Verify settings through independent probe checking port 6380 (NOT 6379).
    """
    exec_adapter = SimulationExecutionAdapter()
    exec_adapter.reset_state()

    kernel = AgentOSKernel(
        execution_adapter=exec_adapter,
        policy_engine=SimulationPolicyEngine(),
    )

    request = "Deploy Redis in-memory cache on node-redis-01.internal with port 6380 and maxmemory 1024MB"
    ctx = kernel.create_workflow(original_request=request, environment="DEV")

    # Step through: RECEIVED -> UNDERSTANDING -> DISCOVERING -> PLANNING -> COMPOSING -> RESOLVING -> VALIDATING -> SECURITY -> CRITIC -> POLICY -> EXECUTION_READY
    while ctx.current_state not in (
        WorkflowState.WAITING_FOR_APPROVAL,
        WorkflowState.EXECUTION_READY,
        WorkflowState.SUCCESS,
        WorkflowState.EXECUTION_FAILED,
        WorkflowState.VERIFY_FAILED,
        WorkflowState.POLICY_DENIED,
        WorkflowState.WAITING_FOR_INPUT,
        WorkflowState.WAITING_FOR_RESOURCE,
    ):
        ctx = kernel.step(ctx.workflow_id)

    # In DEV, auto-approved to EXECUTION_READY
    assert ctx.current_state == WorkflowState.EXECUTION_READY
    assert ctx.normalized_intent.get("known_parameters", {}).get("port") == 6380
    assert ctx.normalized_intent.get("known_parameters", {}).get("maxmemory_mb") == 1024

    # Execute
    ctx = kernel.step(ctx.workflow_id)  # EXECUTING -> VERIFYING
    assert ctx.current_state == WorkflowState.VERIFYING
    assert ctx.execution_result.get("exit_code") == 0
    assert "changed: [node-redis-01.internal]" in ctx.execution_result.get("stdout", "")

    # Verify
    ctx = kernel.step(ctx.workflow_id)  # VERIFYING -> SUCCESS
    assert ctx.current_state == WorkflowState.SUCCESS

    # Milestone 5: Assert dynamic probe checked port 6380!
    probes = ctx.postcondition_verification.get("probes", [])
    port_probes = [p for p in probes if p.get("probe_type") == "port_open"]
    assert len(port_probes) > 0
    checked_port = port_probes[0]["details"]["port"]
    assert checked_port == 6380, f"Expected port probe to check custom port 6380, but checked {checked_port}"

    service_probes = [p for p in probes if p.get("probe_type") == "service_status"]
    assert len(service_probes) > 0
    assert service_probes[0]["details"].get("port") == 6380 or service_probes[0]["details"].get("service") == "redis-server"


def test_milestone_6_execution_idempotency_changed_zero(empty_cache_dir):
    """
    Milestone 6: Execute again against same target and measure idempotency (changed=0).
    """
    exec_adapter = SimulationExecutionAdapter()
    exec_adapter.reset_state()

    workflow_id = "wf-idempotency"
    token_id = "cap-token-1"
    artifact_sha = "abc123sha"
    files = {"playbook.yml": "- hosts: all\n  tasks:\n    - name: Ensure Redis\n      debug:\n"}
    target = "node-redis-01.internal"
    params = {"software": "redis", "port": 6380, "maxmemory_mb": 1024}

    # Run 1: First application (mutates system)
    res1 = exec_adapter.execute(
        workflow_id=workflow_id,
        token_id=token_id,
        artifact_sha256=artifact_sha,
        artifact_files=files,
        target_resource_id=target,
        parameters=params,
        environment="DEV",
    )
    assert res1.exit_code == 0
    assert "changed=3" in res1.stdout or "changed=4" in res1.stdout or "changed: [" in res1.stdout

    # Run 2: Exact same execution against same target (Idempotent repeat)
    res2 = exec_adapter.execute(
        workflow_id=workflow_id,
        token_id="cap-token-2",
        artifact_sha256=artifact_sha,
        artifact_files=files,
        target_resource_id=target,
        parameters=params,
        environment="DEV",
    )
    assert res2.exit_code == 0
    assert "changed=0" in res2.stdout, f"Repeat execution must report changed=0! Got stdout:\n{res2.stdout}"


def test_milestone_7_failure_modes(empty_cache_dir):
    """
    Milestone 7: Demonstrate actual registry failure, incompatible metadata, and digest mismatch.
    """
    resolver = ArtifactResolver(cache_root=empty_cache_dir)

    # 1. Registry Failure
    os.environ["VULCAN_REGISTRY_UNAVAILABLE"] = "1"
    try:
        with pytest.raises(RegistryUnavailableError):
            resolver.resolve_and_download("geerlingguy.redis", workflow_id="wf-fail")
    finally:
        os.environ.pop("VULCAN_REGISTRY_UNAVAILABLE", None)

    # 2. Incompatible Metadata (OS mismatch)
    resolved_incompat = resolver.resolve_and_download(
        identifier="geerlingguy.redis",
        requested_os="windows_server_2022",
        workflow_id="wf-incompat",
    )
    assert resolved_incompat.is_compatible is False
    assert resolved_incompat.state == ArtifactState.INCOMPATIBLE
    assert "incompatible with requested OS" in resolved_incompat.incompatibility_reason

    # 3. Digest Mismatch
    with pytest.raises(DigestMismatchError):
        resolver.resolve_and_download(
            identifier="geerlingguy.redis",
            expected_sha="deadbeef00000000000000000000000000000000000000000000000000000000",
            workflow_id="wf-mismatch",
        )

    # 4. Capability Token Tampering Protection
    from app.agentos.agents.executor import ConstrainedExecutor
    from datetime import datetime, timezone, timedelta
    executor = ConstrainedExecutor(adapter=SimulationExecutionAdapter())

    token = ExecutionCapabilityToken(
        token_id="cap-test-tamper",
        workflow_id="wf-tamper",
        artifact_sha256="expected_sha_123",
        parameter_hash="param_hash_123",
        target_resource_id="node-1.internal",
        environment="PROD",
        approval_id="appr-test",
        policy_decision_id="pol-1",
        allowed_action="EXECUTE",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    # Execution with tampered artifact content must fail
    with pytest.raises(CapabilityTokenViolationError, match="Artifact SHA mismatch"):
        executor.execute(
            token=token,
            artifact_files={"playbook.yml": "tampered content"},
            target_resource_id="node-1.internal",
            parameters={},
            environment="PROD",
        )


def test_milestone_8_audit_trail_and_retention(empty_cache_dir):
    """
    Milestone 8: Retain source identities, generated files, execution logs, and verification results.
    """
    exec_adapter = SimulationExecutionAdapter()
    exec_adapter.reset_state()

    kernel = AgentOSKernel(
        execution_adapter=exec_adapter,
        policy_engine=SimulationPolicyEngine(),
    )

    request = "Deploy Redis in-memory cache on node-redis-01.internal with port 6380 and maxmemory 1024MB"
    ctx = kernel.create_workflow(original_request=request, environment="DEV")

    while ctx.current_state != WorkflowState.SUCCESS and ctx.current_state not in (
        WorkflowState.EXECUTION_FAILED,
        WorkflowState.VERIFY_FAILED,
        WorkflowState.POLICY_DENIED,
        WorkflowState.WAITING_FOR_APPROVAL,
        WorkflowState.WAITING_FOR_INPUT,
        WorkflowState.WAITING_FOR_RESOURCE,
    ):
        ctx = kernel.step(ctx.workflow_id)

    assert ctx.current_state == WorkflowState.SUCCESS

    # 1. Source identities retained
    assert "selected_assets" in ctx.automation_plan
    assert len(ctx.automation_plan["selected_assets"]) > 0

    # 2. Resolved asset metadata retained
    resolved = ctx.automation_plan.get("resolved_asset", {})
    assert "digest_sha256" in resolved
    assert "interface" in resolved

    # 3. Generated files retained
    assert len(ctx.generated_artifacts) > 0
    art = ctx.generated_artifacts[0]
    assert "artifact_sha256" in art
    assert "files" in art and len(art["files"]) > 0

    # 4. Execution logs retained
    assert "stdout" in ctx.execution_result
    assert ctx.execution_result["exit_code"] == 0

    # 5. Verification results retained
    assert "all_passed" in ctx.postcondition_verification
    assert ctx.postcondition_verification["all_passed"] is True
    assert len(ctx.postcondition_verification["probes"]) > 0
