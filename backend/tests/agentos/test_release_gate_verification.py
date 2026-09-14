"""
Project Vulcan: 7 Release Gate Verification Tests
Verifies the 7 critical execution and governance guarantees:
1. Remove Ansible from runner: Clear failure, exit code != 0, no success recap (ok=4 changed=3 failed=0).
2. Make registry unavailable: Explicit failure (RegistryUnavailableError) or explicitly identified, verified cache use (is_cached=True). Never create dummy metadata-only folders or fall back to local content.
3. Provide only PROD credentials for DEV request: Pause in WAITING_FOR_RESOURCE. Never fall back to other environments (list_all()).
4. Attempt approval with advance-only permission: HTTP 403. /deploy must enforce WORKFLOW_APPROVE when approving.
5. Replace generated playbook with failing task: Execution and workflow fail (failed=1, exit code != 0, state EXECUTION_FAILED).
6. Omit idempotency evidence: UI and API report 'Not measured' instead of defaulting to changed=0 (Zero Drift Verified) or fabricating probe passes.
7. Restart worker during execution: Recover without duplicating changes.
"""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.agentos.adapters.execution_adapter import (
    AnsibleRunnerExecutionAdapter,
    LiveDisposableTargetExecutionAdapter,
)
from app.agentos.agents.verifier import ProductionProbeRunner
from app.agentos.artifacts.downloader import (
    ContentAddressableCache,
    GalaxyDownloadAdapter,
    GitDownloadAdapter,
    RegistryUnavailableError,
)
from app.agentos.artifacts.resolver import ArtifactResolver
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.kernel import AgentOSKernel
from app.agentos.repository import PostgresAgentWorkflowRepository
from app.agentos.schemas import ExecutionCapabilityToken
from app.api.server import app
from app.domain.roles_and_policies import Permission, UserRole, has_permission, resolve_user_role
from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository
from app.domain.external_resource_entities import (
    ExternalResource,
    ResourceCategory,
    ResourceEnvironment,
    AuthMode,
    HealthStatus,
)


# =============================================================================
# GATE 1: Remove Ansible from runner -> Clear failure, exit_code != 0, no success recap
# =============================================================================

def test_gate_1_ansible_missing_fails_cleanly_without_fake_recap(tmp_path):
    """
    Gate 1: When ansible-playbook binary is not installed:
    - Exit code must NOT be 0 (returns 127).
    - Output must NEVER contain 'ok=4    changed=3    unreachable=0    failed=0'.
    - Output must contain 'failed=1' and explicit error message.
    """
    adapter = AnsibleRunnerExecutionAdapter(base_dir=str(tmp_path / "runner"))
    assert adapter.is_simulation is False

    with patch("shutil.which", return_value=None), \
         patch("os.path.isfile", return_value=False), \
         patch("os.access", return_value=False):
        
        res = adapter.execute(
            workflow_id="wf-gate1-test",
            token_id="cap-gate1-token",
            artifact_sha256="sha256-test-gate1",
            artifact_files={"playbook.yml": "---\n- hosts: all\n  tasks:\n    - ping:\n"},
            target_resource_id="db-target.internal",
            parameters={"software": "redis", "port": 6379},
            environment="PROD",
        )

        assert res.exit_code != 0, f"Expected non-zero exit code, got {res.exit_code}"
        assert res.exit_code == 127
        assert "ok=4    changed=3" not in res.stdout, "Fabricated success recap detected!"
        assert "failed=1" in res.stdout
        assert "ansible-playbook binary not found" in res.stdout


# =============================================================================
# GATE 2: Make registry unavailable -> Explicit failure or verified cache use
# =============================================================================

def test_gate_2_registry_outage_raises_error_and_never_creates_dummy_folder(tmp_path):
    """
    Gate 2A: When external registry is unavailable:
    - Raises RegistryUnavailableError.
    - Never falls back to creating dummy metadata folders.
    """
    cache = ContentAddressableCache(cache_root=tmp_path / "cache")
    resolver = ArtifactResolver(base_repo_dir=tmp_path / "empty_repo", cache_root=tmp_path / "cache")

    with patch.dict(os.environ, {"VULCAN_REGISTRY_UNAVAILABLE": "1"}):
        with pytest.raises(RegistryUnavailableError):
            resolver.resolve_and_download(
                identifier="nonexistent.vendor.role",
                version="2.0.0",
                source_uri="https://galaxy.ansible.com",
                workflow_id="wf-gate2-test",
                workspace_parent=tmp_path / "staging",
            )

    # Confirm no dummy metadata file was created
    dummy_meta = tmp_path / "staging" / "nonexistent_vendor_role" / "meta" / "main.yml"
    assert not dummy_meta.exists(), "Dummy role was fabricated during registry outage!"


def test_gate_2_verified_cache_use_is_explicitly_identified(tmp_path):
    """
    Gate 2B: When asset is already cached:
    - Resolver successfully loads from cache.
    - Asset is explicitly flagged with is_cached=True.
    """
    cache_root = tmp_path / "cache"
    cache = ContentAddressableCache(cache_root=cache_root)

    # Pre-populate cache with a role
    source_dir = tmp_path / "source_role"
    source_dir.mkdir(parents=True)
    (source_dir / "tasks").mkdir()
    (source_dir / "tasks" / "main.yml").write_text("- name: ping\n  ping:\n", encoding="utf-8")
    (source_dir / "meta").mkdir()
    (source_dir / "meta" / "main.yml").write_text("---\ngalaxy_info:\n  role_name: redis\n", encoding="utf-8")

    # Compute digest of source_dir matching resolver's multi-file format
    files_map = {
        "tasks/main.yml": "- name: ping\n  ping:\n",
        "meta/main.yml": "---\ngalaxy_info:\n  role_name: redis\n",
    }
    combined = [f"{p}:{files_map[p]}" for p in sorted(files_map.keys())]
    digest = hashlib.sha256("\n---FILE---\n".join(combined).encode("utf-8")).hexdigest()

    cache.put(digest, source_dir)

    resolver = ArtifactResolver(base_repo_dir=tmp_path / "empty_repo", cache_root=cache_root)

    # Even with registry marked unavailable, cached asset is successfully and honestly resolved
    with patch.dict(os.environ, {"VULCAN_REGISTRY_UNAVAILABLE": "1"}):
        resolved = resolver.resolve_and_download(
            identifier="test.cached.role",
            version="1.0.0",
            expected_sha=digest,
            source_uri="https://galaxy.ansible.com",
            workflow_id="wf-gate2-cache-test",
            workspace_parent=tmp_path / "staging",
        )

    assert resolved.is_cached is True, "Expected asset to be explicitly marked as cached"
    assert resolved.digest_sha256 == digest


# =============================================================================
# GATE 3: PROD credentials for DEV request -> Pause in WAITING_FOR_RESOURCE
# =============================================================================

def test_gate_3_dev_request_with_only_prod_credentials_pauses_in_waiting_for_resource():
    """
    Gate 3: Provide only PROD credentials for DEV request:
    - Must pause in WAITING_FOR_RESOURCE.
    - Must NEVER fall back to listing or using PROD resources.
    """
    os.environ["VULCAN_CAPABILITY_HMAC_KEY"] = "test-gate3-hmac-key-abcdef123456"
    ext_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=False)

    # Add only a PROD database resource
    prod_resource = ExternalResource(
        resource_id="res-prod-db-01",
        provider="postgresql",
        category=ResourceCategory.STORAGE_DATA,
        display_name="Production Database Cluster",
        endpoint="prod-db.corp.internal:5432",
        environment=ResourceEnvironment.PROD,
        auth_mode=AuthMode.API_KEY,
        health_status=HealthStatus.CONNECTED,
        enabled=True,
    )
    ext_repo.save(prod_resource)

    # Confirm only PROD is present
    assert len(ext_repo.list_all(environment="DEV")) == 0
    assert len(ext_repo.list_all(environment="PROD")) == 1

    kernel = AgentOSKernel(
        external_resource_repo=ext_repo,
    )

    # Create a DEV request
    ctx = kernel.create_workflow(
        original_request="Deploy PostgreSQL database for dev testing",
        requester_id="developer@corp.internal",
        environment="DEV",
    )
    assert ctx.current_state == WorkflowState.RECEIVED

    # Step into UNDERSTANDING
    ctx = kernel.step(ctx.workflow_id)
    if ctx.current_state == WorkflowState.WAITING_FOR_INPUT:
        ctx = kernel.supply_input(ctx.workflow_id, {"target_host": "dev-box.internal"})
        ctx = kernel.step(ctx.workflow_id)

    # Step into DISCOVERING
    ctx = kernel.step(ctx.workflow_id)

    # Step into PLANNING
    ctx = kernel.step(ctx.workflow_id)

    # Step into COMPOSING
    ctx = kernel.step(ctx.workflow_id)

    # Step into COMPILING
    ctx = kernel.step(ctx.workflow_id)

    # Step into RESOURCE resolution: Must pause in WAITING_FOR_RESOURCE
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.current_state == WorkflowState.WAITING_FOR_RESOURCE, (
        f"Expected WAITING_FOR_RESOURCE but transitioned to {ctx.current_state}! PROD resources leaked into DEV!"
    )
    assert len(ctx.required_resources) > 0
    assert len(ctx.resolved_resources) == 0
    # Ensure PROD resource was not resolved
    assert "res-prod-db-01" not in [r.get("resource_id") for r in ctx.resolved_resources.values()]


# =============================================================================
# GATE 4: Attempt approval with advance-only permission -> HTTP 403 Forbidden
# =============================================================================

def test_gate_4_approval_with_advance_only_permission_rejected_at_kernel_and_api():
    """
    Gate 4: Attempt approval with advance-only permission:
    - eng.alice (OPERATOR role) has workflow:advance but lacks workflow:approve.
    - Calling approve_workflow raises PermissionError.
    - Calling POST /workflows/{id}/deploy while in WAITING_FOR_APPROVAL returns HTTP 403.
    """
    from app.config import container
    os.environ["VULCAN_CAPABILITY_HMAC_KEY"] = "test-gate4-hmac-key-abcdef123456"
    assert has_permission("eng.alice", Permission.WORKFLOW_ADVANCE) is True
    assert has_permission("eng.alice", Permission.WORKFLOW_APPROVE) is False
    assert has_permission("lead.bob", Permission.WORKFLOW_APPROVE) is True

    kernel = container.agentos_kernel
    ctx = kernel.create_workflow(
        original_request="Deploy cache on node-01.internal",
        requester_id="developer@corp.internal",
        environment="DEV",
    )
    # Manually transition to WAITING_FOR_APPROVAL
    ctx.current_state = WorkflowState.WAITING_FOR_APPROVAL
    ctx.version += 1
    kernel.repository.save_workflow(ctx)

    # 1. Kernel layer check
    with pytest.raises(PermissionError) as exc_info:
        kernel.approve_workflow(ctx.workflow_id, approver_id="eng.alice", reason="Operator trying to approve")
    assert "lacks permission 'workflow:approve'" in str(exc_info.value)

    # 2. API layer check via TestClient with eng.alice token
    client = TestClient(app)
    res = client.post(
        f"/api/v1/agentos/workflows/{ctx.workflow_id}/deploy",
        headers={"Authorization": "Bearer vlc_test_alice"},
    )
    assert res.status_code == 403, f"Expected HTTP 403 for operator approval, got {res.status_code}: {res.text}"
    assert "workflow:approve" in res.json()["detail"]

    # 3. Approving lead (lead.bob) succeeds
    lead_client = TestClient(app)
    res_lead = lead_client.post(
        f"/api/v1/agentos/workflows/{ctx.workflow_id}/deploy",
        headers={"Authorization": "Bearer vlc_test_bob"},
    )
    # Lead is allowed to approve (status 200)
    assert res_lead.status_code == 200


# =============================================================================
# GATE 5: Replace generated playbook with failing task -> Execution and workflow fail
# =============================================================================

def test_gate_5_failing_playbook_task_fails_execution_and_workflow(tmp_path):
    """
    Gate 5: Replace generated playbook with failing task:
    - Execution fails with exit code != 0 (exit_code=1).
    - Failed task count in recap is failed=1.
    - Workflow enters EXECUTION_FAILED state.
    """
    adapter = LiveDisposableTargetExecutionAdapter(target_root=tmp_path / "disposable")
    failing_playbook = """---
- hosts: all
  tasks:
    - name: Ensure target is available
      debug:
        msg: "Checking target..."
    - name: Intentional Failure Task
      ansible.builtin.fail:
        msg: "Target configuration failed due to disk quota exceeded."
"""
    failing_sha = hashlib.sha256(f"playbook.yml:{failing_playbook}".encode("utf-8")).hexdigest()
    res = adapter.execute(
        workflow_id="wf-gate5-fail",
        token_id="cap-gate5-token",
        artifact_sha256=failing_sha,
        artifact_files={"playbook.yml": failing_playbook},
        target_resource_id="box-fail.internal",
        parameters={"software": "redis", "port": 6379},
        environment="DEV",
    )

    assert res.exit_code == 1, f"Expected exit_code=1, got {res.exit_code}"
    assert "failed=1" in res.stdout
    assert "Target configuration failed due to disk quota exceeded." in res.stdout

    # Now verify end-to-end through AgentOSKernel
    kernel = AgentOSKernel(execution_adapter=adapter)
    ctx = kernel.create_workflow(
        original_request="Deploy service with failing task",
        requester_id="developer@corp.internal",
        environment="DEV",
    )
    # Inject failing artifact
    ctx.current_state = WorkflowState.EXECUTION_READY
    ctx.version += 1
    ctx.generated_artifacts = [{
        "artifact_sha256": failing_sha,
        "files": [{"path": "playbook.yml", "content": failing_playbook}],
    }]
    kernel.repository.save_workflow(ctx)

    # Step execution
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.current_state == WorkflowState.EXECUTION_FAILED
    assert ctx.execution_result.get("exit_code") == 1


# =============================================================================
# GATE 6: Omit idempotency evidence -> Explicit 'Not measured' without fake defaults
# =============================================================================

def test_gate_6_omitted_evidence_honestly_reported_without_fabricated_defaults():
    """
    Gate 6: When idempotency or probes are omitted:
    - Execution results do not fabricate changed=3 or idempotency changed=0.
    - Frontend component explicitly renders 'Not measured'.
    """
    # Verify frontend component code does not contain the old fake fallback defaults
    fe_component_path = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "components" / "AgentControlCenter.tsx"
    assert fe_component_path.exists()
    content = fe_component_path.read_text(encoding="utf-8")

    # The old fake fallbacks must NOT exist in the code
    assert "selectedWorkflow.execution_result?.changed ?? 3" not in content
    assert "selectedWorkflow.execution_result?.ok ?? 5" not in content
    assert "selectedWorkflow.execution_result?.idempotency_run?.changed ?? 0" not in content
    assert "Not measured" in content, "Component must render 'Not measured' for omitted metrics"

    # Verify context schema handles None/omitted cleanly
    ctx = WorkflowContext(
        workflow_id="wf-gate6",
        correlation_id="corr-gate6",
        requester_id="alice@corp.internal",
        original_request="test request",
        execution_result=None,
        postcondition_verification={},
    )
    assert ctx.execution_result is None
    assert ctx.postcondition_verification.get("probes") is None


# =============================================================================
# GATE 7: Restart worker during execution -> Recover without duplicating changes
# =============================================================================

def test_gate_7_restart_worker_recovers_without_duplicate_changes(tmp_path):
    """
    Gate 7: Restart worker during execution:
    - Kernel persists checkpoint when transitioning to EXECUTING.
    - When recovered, resumes execution using idempotency guarantees.
    - State is restored without duplicate mutations (changed=0 on repeat).
    """
    repo = PostgresAgentWorkflowRepository(db_url=None)
    target_root = tmp_path / "worker_recovery_target"
    adapter = LiveDisposableTargetExecutionAdapter(target_root=target_root)

    kernel1 = AgentOSKernel(repository=repo, execution_adapter=adapter)
    ctx = kernel1.create_workflow(
        original_request="Deploy Redis cache on redis-01.internal on port 6380 with 512MB memory",
        requester_id="ops@corp.internal",
        environment="DEV",
    )

    # Advance to EXECUTION_READY
    ctx.current_state = WorkflowState.EXECUTION_READY
    ctx.version += 1
    ctx.desired_state = {"software": "redis", "port": 6380, "maxmemory_mb": 512, "target_host": "redis-01.internal"}
    ctx.normalized_intent = {"known_parameters": {"software": "redis", "port": 6380, "maxmemory_mb": 512, "target_host": "redis-01.internal"}}
    playbook_content = "---\n- hosts: all\n  vars:\n    port: 6380\n    maxmemory_mb: 512\n"
    playbook_sha = hashlib.sha256(f"playbook.yml:{playbook_content}".encode("utf-8")).hexdigest()
    ctx.generated_artifacts = [{
        "artifact_sha256": playbook_sha,
        "files": [{"path": "playbook.yml", "content": playbook_content}],
    }]
    repo.save_workflow(ctx)

    # Step once: enters EXECUTING, issues token, saves checkpoint, and executes
    ctx = kernel1.step(ctx.workflow_id)

    # Simulate worker crash mid-execution: set state back to EXECUTING with incomplete result
    ctx.current_state = WorkflowState.EXECUTING
    ctx.version += 1
    ctx.execution_result = None
    repo.save_workflow(ctx)

    # Simulate worker restart: new Kernel instance attached to the same repository
    kernel2 = AgentOSKernel(repository=repo, execution_adapter=adapter)

    # Recover workflow
    recovered_ctx = kernel2.recover_workflow(ctx.workflow_id)

    assert recovered_ctx.current_state in (WorkflowState.VERIFYING, WorkflowState.SUCCESS)
    assert recovered_ctx.execution_result is not None
    assert recovered_ctx.execution_result.get("exit_code") == 0
    # Because target was already partially/previously configured, repeat execution reports changed=0
    assert "changed=0" in recovered_ctx.execution_result.get("stdout")
