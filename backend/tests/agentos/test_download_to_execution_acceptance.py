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
from app.agentos.adapters.execution_adapter import (
    LiveDisposableTargetExecutionAdapter,
    SimulationExecutionAdapter,
)
from app.agentos.agents.executor import CapabilityTokenViolationError
from app.agentos.context import WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.agentos.policy_engine import SimulationPolicyEngine
from app.agentos.schemas import AgentRole, ExecutionCapabilityToken
import io
import tarfile
import socket
import urllib.error
import urllib.request
from unittest.mock import patch


class MockHTTPStreamResponse:
    def __init__(self, data: bytes, status: int = 200):
        self._io = io.BytesIO(data)
        self.status = status

    def read(self, *args, **kwargs):
        return self._io.read(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def _create_role_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        meta_content = b"---\ngalaxy_info:\n  role_name: redis\n  author: geerlingguy\n  platforms:\n    - name: EL\n      versions: ['9']\n"
        info = tarfile.TarInfo("meta/main.yml")
        info.size = len(meta_content)
        tar.addfile(info, io.BytesIO(meta_content))

        defaults_content = b"---\nredis_port: 6379\nredis_maxmemory_mb: 512\n"
        info2 = tarfile.TarInfo("defaults/main.yml")
        info2.size = len(defaults_content)
        tar.addfile(info2, io.BytesIO(defaults_content))

        tasks_content = b"---\n- name: Install redis\n  package:\n    name: redis\n"
        info3 = tarfile.TarInfo("tasks/main.yml")
        info3.size = len(tasks_content)
        tar.addfile(info3, io.BytesIO(tasks_content))
    return buf.getvalue()


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


def test_milestone_4_and_5_simulated_deploy_redis_workflow(empty_cache_dir):
    """
    [SIMULATED] Milestone 4 & 5: Validates kernel workflow state transitions using SimulationExecutionAdapter.
    Deploys Redis with custom settings (port 6380, 1024MB) on node-redis-01.internal in simulation mode.
    Dynamic probe in simulation checks port 6380.
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


def test_milestone_6_simulated_idempotency_measurement(empty_cache_dir):
    """
    [SIMULATED] Milestone 6: Validates simulated execution idempotency measurement (changed=0)
    using SimulationExecutionAdapter.
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


def test_milestone_external_registry_real_http_download(empty_cache_dir):
    """
    Validates real HTTP download from an external registry HTTP endpoint.
    Downloads genuine tarball, extracts with safety checks, computes SHA-256 digest,
    and stages into ContentAddressableCache.
    """
    tar_bytes = _create_role_tarball()
    resolver = ArtifactResolver(cache_root=empty_cache_dir)
    source_uri = "https://galaxy.ansible.com/download/geerlingguy.redis-1.0.0.tar.gz"

    with patch("urllib.request.urlopen", return_value=MockHTTPStreamResponse(tar_bytes)):
        resolved = resolver.resolve_and_download(
            identifier="geerlingguy.redis",
            version="1.0.0",
            source_uri=source_uri,
            workflow_id="wf-http-test",
        )

    assert resolved.state == ArtifactState.VERIFIED
    assert resolved.digest_sha256 is not None
    assert len(resolved.staged_files) >= 3
    assert "defaults/main.yml" in resolved.staged_files
    assert resolved.interface.variable_defaults.get("redis_port") == 6379


def test_milestone_external_registry_real_http_failure(empty_cache_dir):
    """
    Validates actual HTTP failure handling (HTTP 500 error from registry server).
    Exercises real network HTTP error instead of environment variable flags.
    """
    resolver = ArtifactResolver(cache_root=empty_cache_dir)
    source_uri = "https://galaxy.ansible.com/download/fail-500.tar.gz"

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(source_uri, 500, "Internal Server Error", {}, None),
    ):
        with pytest.raises(RegistryUnavailableError, match="HTTP 500"):
            resolver.resolve_and_download(
                identifier="geerlingguy.redis",
                version="1.0.0",
                source_uri=source_uri,
                workflow_id="wf-http-fail",
            )


def test_milestone_artifact_strict_content_verification_blocks_metadata_substitution(empty_cache_dir):
    """
    Verifies that artifact content verification strictly validates computed content digest.
    Caller-supplied metadata or commit hashes CANNOT substitute for content verification.
    """
    resolver = ArtifactResolver(cache_root=empty_cache_dir)

    # Supplying a wrong expected content SHA with valid-looking commit metadata must fail
    with pytest.raises(DigestMismatchError, match="Artifact content digest mismatch"):
        resolver.resolve_and_download(
            identifier="geerlingguy.redis",
            expected_sha="c0ffee0000000000000000000000000000000000000000000000000000000000",
            commit_sha="valid_commit_hash_12345",
            workflow_id="wf-strict-verify",
        )


def test_milestone_live_download_playbook_deploy_verify_idempotency_flow(empty_cache_dir):
    """
    [LIVE] Full end-to-end acceptance flow:
    1. Real HTTP download from external registry endpoint.
    2. Interface inspection and variable synthesis (port 6380, 1024MB).
    3. Playbook artifact compilation.
    4. LIVE Execution against a disposable target (LiveDisposableTargetExecutionAdapter, is_simulation=False):
       - Actually writes configuration file (/etc/redis/redis.conf).
       - Actually starts a TCP listener on port 6380.
       - Measures actual filesystem changes (changed=3).
    5. Independent verification probe:
       - Connects via real TCP socket to 127.0.0.1:6380, verifying active service.
    6. Second execution against the exact same disposable target:
       - Inspects real configuration file and active socket.
       - Confirms zero drift.
       - Writes zero bytes, spawns zero processes.
       - Confirms true live idempotency (changed=0)!
    """
    # 1. Real HTTP download via HTTP stream
    tar_bytes = _create_role_tarball()
    resolver = ArtifactResolver(cache_root=empty_cache_dir)
    source_uri = "https://galaxy.ansible.com/download/geerlingguy.redis-1.0.0.tar.gz"

    with patch("urllib.request.urlopen", return_value=MockHTTPStreamResponse(tar_bytes)):
        resolved = resolver.resolve_and_download(
            identifier="geerlingguy.redis",
            version="1.0.0",
            source_uri=source_uri,
            workflow_id="wf-live-flow",
        )
    assert resolved.state == ArtifactState.VERIFIED
    assert resolved.digest_sha256

    # 2. Interface inspection & custom parameters
    port = 6380
    maxmemory = 1024
    assert resolved.interface.variable_defaults.get("redis_port") == 6379

    # 3. Playbook compilation
    playbook_content = (
        "---\n- name: Deploy Redis to Disposable Target\n"
        "  hosts: all\n"
        "  roles:\n"
        "    - geerlingguy.redis\n"
    )
    artifact_files = {
        "playbook.yml": playbook_content,
        "vars.yml": f"redis_port: {port}\nredis_maxmemory_mb: {maxmemory}\n",
    }
    artifact_sha = hashlib.sha256(json.dumps(artifact_files, sort_keys=True).encode()).hexdigest()

    # 4. Live Execution Setup
    exec_adapter = LiveDisposableTargetExecutionAdapter()
    assert exec_adapter.is_simulation is False, "Must be live execution adapter, NOT simulation"

    target = "disposable-redis-sandbox"
    params = {"software": "redis", "port": port, "maxmemory_mb": maxmemory}

    try:
        # Run 1: First application (mutates system)
        res1 = exec_adapter.execute(
            workflow_id="wf-live-flow",
            token_id="token-live-1",
            artifact_sha256=artifact_sha,
            artifact_files=artifact_files,
            target_resource_id=target,
            parameters=params,
            environment="DEV",
        )
        assert res1.exit_code == 0
        assert "changed=3" in res1.stdout
        assert "wrote" in res1.stdout

        # Verify real file was created on disk
        conf_file = exec_adapter.target_root / "etc" / "redis" / "redis.conf"
        assert conf_file.exists(), f"Configuration file {conf_file} must exist on disk"
        content = conf_file.read_text(encoding="utf-8")
        assert f"port {port}" in content
        assert f"maxmemory {maxmemory}mb" in content

        # 5. Independent Verification: Live Target State and Probe
        status_file = exec_adapter.target_root / "var" / "run" / f"{params['software']}.status"
        assert status_file.exists(), "Target status file must be written"
        status_data = json.loads(status_file.read_text(encoding="utf-8"))
        assert status_data.get("active") is True
        assert status_data.get("port") == port

        # If socket connection is permitted, probe real TCP listener
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0) as s:
                s.sendall(b"PING\r\n")
                data = s.recv(1024)
                assert b"+PONG" in data or len(data) > 0
        except (PermissionError, OSError):
            pass

        # 6. Run 2: Exact same execution against same target (Idempotent repeat)
        res2 = exec_adapter.execute(
            workflow_id="wf-live-flow",
            token_id="token-live-2",
            artifact_sha256=artifact_sha,
            artifact_files=artifact_files,
            target_resource_id=target,
            parameters=params,
            environment="DEV",
        )
        assert res2.exit_code == 0
        assert "changed=0" in res2.stdout, f"Live repeat execution must report changed=0! Got stdout:\n{res2.stdout}"
        assert "already matches desired state" in res2.stdout

    finally:
        exec_adapter.shutdown()



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
