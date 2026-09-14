"""
Project Vulcan: Tests for Flagship Governed PostgreSQL Demo & Production Adapters
"""
import os
import pytest
from app.agentos.kernel import AgentOSKernel
from app.agentos.context import WorkflowState
from app.agentos.schemas import AgentRole, IntentOutput
from app.agentos.adapters.execution_adapter import AnsibleRunnerExecutionAdapter
from app.agentos.adapters.foundry_adapter import FoundryAgentRuntime
from app.agentos.agents.verifier import ProductionProbeRunner
from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository
from app.catalog_data import DB_SHA


def test_real_postgres_demo_end_to_end(tmp_path):
    """Verifies complete governed demo flow through production adapters."""
    os.environ["VULCAN_CAPABILITY_HMAC_KEY"] = "test-hmac-key-32-chars-long-ok"
    ext_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=True)
    exec_adapter = AnsibleRunnerExecutionAdapter(base_dir=str(tmp_path / "runner"))
    probe_runner = ProductionProbeRunner()

    kernel = AgentOSKernel(
        execution_adapter=exec_adapter,
        probe_runner=probe_runner,
        external_resource_repo=ext_repo,
    )

    # 1. Inception
    ctx = kernel.create_workflow(
        original_request="Deploy hardened PostgreSQL 16 database for production application with primary user and port 5432",
        requester_id="operator-alice@corp.internal",
        environment="PROD",
    )
    assert ctx.current_state == WorkflowState.RECEIVED

    # 2. Understanding & Clarification Gate
    ctx = kernel.step(ctx.workflow_id)
    if ctx.current_state == WorkflowState.WAITING_FOR_INPUT:
        ctx = kernel.supply_input(ctx.workflow_id, {"target_inventory": "db-cluster.internal"})
        assert ctx.current_state == WorkflowState.UNDERSTANDING
        ctx = kernel.step(ctx.workflow_id)

    # 3. Discovery with verified commit identities
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.discovered_assets, "Should discover curated assets"
    assert ctx.discovered_assets[0].get("commit_sha") == DB_SHA
    assert ctx.discovered_assets[0].get("trust_state") == "CURATED"

    # 4. Plan & Validation & Security Review
    while ctx.current_state != WorkflowState.WAITING_FOR_APPROVAL:
        prev_state = ctx.current_state
        ctx = kernel.step(ctx.workflow_id)
        assert prev_state != ctx.current_state, f"Stuck in state {prev_state}"

    # 5. Maker-Checker Enforcement
    with pytest.raises(PermissionError):
        kernel.approve_workflow(ctx.workflow_id, approver_id="operator-alice@corp.internal", reason="Self approve")

    ctx = kernel.approve_workflow(ctx.workflow_id, approver_id="secops-bob@corp.internal", reason="Valid sign-off")
    assert ctx.current_state == WorkflowState.EXECUTION_READY

    # 6. Real Execution via AnsibleRunnerExecutionAdapter (mocking external ansible CLI at process boundary)
    from unittest.mock import patch, MagicMock
    mock_ansible_proc = MagicMock()
    mock_ansible_proc.returncode = 0
    mock_ansible_proc.stdout = "PLAY [deploy_postgres.yml] ********************\nchanged: [db-cluster.internal]\nPLAY RECAP: db-cluster.internal : ok=4 changed=3 unreachable=0 failed=0"
    mock_ansible_proc.stderr = ""
    with (
        patch("shutil.which", return_value="/usr/bin/ansible-playbook"),
        patch("os.path.isfile", return_value=True),
        patch("os.access", return_value=True),
        patch("subprocess.run", return_value=mock_ansible_proc),
    ):
        ctx = kernel.step(ctx.workflow_id)
        assert ctx.current_state == WorkflowState.VERIFYING
        assert ctx.execution_result.get("exit_code") == 0
        assert ctx.execution_result.get("runner") == "ansible_runner_adapter"

    # 7. Independent Verification via ProductionProbeRunner (mocked at test boundary)
    # Mock network I/O (socket, psycopg) and resolve the target to localhost so
    # disk_capacity runs against the local filesystem. Mock disk_usage to provide
    # enough capacity for the 500GB requirement.
    mock_disk = (600 * 1024**3, 100 * 1024**3, 500 * 1024**3)  # total=600GB, used=100GB, free=500GB
    with (
        patch("socket.create_connection"),
        patch("psycopg.connect") as mock_conn,
        patch.dict(os.environ, {"AGENTOS_TARGET_HOST": "127.0.0.1"}),
        patch("shutil.disk_usage", return_value=mock_disk),
    ):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("PostgreSQL 16.2 on x86_64-pc-linux-gnu",)
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        ctx = kernel.step(ctx.workflow_id)
        assert ctx.current_state == WorkflowState.SUCCESS
        probes = ctx.postcondition_verification.get("probes", [])
        assert len(probes) >= 4
        # The 4 core probes (port_open, service_status, disk_capacity, db_query) must pass
        core_types = {"port_open", "service_status", "disk_capacity", "db_query"}
        core_probes = [p for p in probes if p["probe_type"] in core_types]
        assert len(core_probes) == 4
        assert all(p["passed"] for p in core_probes)


def test_ansible_runner_execution_adapter_executes_artifact(tmp_path):
    from unittest.mock import patch, MagicMock
    adapter = AnsibleRunnerExecutionAdapter(base_dir=str(tmp_path / "runner"))
    assert adapter.is_simulation is False
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "PLAY [playbook.yml] ********************\nok: [db-test.internal]\nPLAY RECAP: db-test.internal : ok=1 changed=1 unreachable=0 failed=0"
    mock_proc.stderr = ""
    with (
        patch("shutil.which", return_value="/usr/bin/ansible-playbook"),
        patch("os.path.isfile", return_value=True),
        patch("os.access", return_value=True),
        patch("subprocess.run", return_value=mock_proc),
    ):
        res = adapter.execute(
            workflow_id="wf-test-exec",
            token_id="cap-test-1234",
            artifact_sha256="sha256-test-hash",
            artifact_files={"playbook.yml": "---\n- hosts: all\n  tasks:\n    - ping:\n"},
            target_resource_id="db-test.internal",
            parameters={"db_name": "test_db"},
            environment="PROD",
        )
        assert res.exit_code == 0
        assert res.runner == "ansible_runner_adapter"
        assert "PLAY [playbook.yml]" in res.stdout


def test_production_probe_runner_probes():
    runner = ProductionProbeRunner()
    assert runner.is_simulation is False
    probe = runner.run_probe("disk_capacity", "localhost", {"min_gb": 1.0})
    assert probe.passed is True
    assert probe.probe_type == "disk_capacity"
    assert probe.details.get("simulation") is False


def test_production_probe_runner_fails_on_unreachable():
    runner = ProductionProbeRunner()
    assert runner.is_simulation is False
    # Port probe against non-listening port must fail
    port_probe = runner.run_probe("port_open", "127.0.0.1", {"port": 59999, "timeout": 0.2})
    assert port_probe.passed is False
    assert port_probe.details.get("status") == "closed"
    assert port_probe.details.get("simulation") is False

    # Service status against non-listening port must fail
    svc_probe = runner.run_probe("service_status", "127.0.0.1", {"port": 59999, "service": "fake-service-xyz", "timeout": 0.2})
    assert svc_probe.passed is False
    assert svc_probe.details.get("status") == "inactive"
    assert svc_probe.details.get("simulation") is False

    # Database query probe against non-listening port must fail
    db_probe = runner.run_probe("db_query", "127.0.0.1", {"port": 59999, "query": "SELECT 1;"})
    assert db_probe.passed is False
    assert "error" in db_probe.details
    assert db_probe.details.get("simulation") is False


def test_foundry_agent_runtime_invoke():
    from unittest.mock import MagicMock
    from app.ports.interfaces import ChatCompletionResponse
    mock_provider = MagicMock()
    json_str = '{"desired_outcome": "Deploy PostgreSQL 16", "automation_domain": "database", "proposed_next_state": "DISCOVERING"}'
    mock_provider.complete_structured.return_value = ChatCompletionResponse(
        content=json_str,
        raw_content=json_str,
        parsed_json={"desired_outcome": "Deploy PostgreSQL 16", "automation_domain": "database", "proposed_next_state": "DISCOVERING"},
        provider_latency_ms=1.0,
    )
    runtime = FoundryAgentRuntime(chat_provider=mock_provider)
    assert runtime.is_deterministic is False
    assert runtime.is_simulation is False
    out = runtime.invoke(
        agent_role=AgentRole.INTENT,
        system_prompt="Extract normalized intent",
        context={"workflow_id": "wf-foundry-test", "request": "Deploy PostgreSQL"},
        output_schema=IntentOutput,
    )
    assert isinstance(out, IntentOutput)
    assert out.agent == AgentRole.INTENT
    assert out.desired_outcome == "Deploy PostgreSQL 16"
    assert out.automation_domain == "database"
    assert out.execution_mode.value == "live"


def test_foundry_agent_runtime_raises_provider_unavailable():
    from app.agentos.adapters.foundry_adapter import ProviderUnavailableError
    # Without keys in environment and without injected provider, FoundryAgentRuntime must reject fake provider
    runtime = FoundryAgentRuntime(max_retries=1)
    with pytest.raises(ProviderUnavailableError):
        runtime.invoke(
            agent_role=AgentRole.INTENT,
            system_prompt="Extract intent",
            context={"workflow_id": "wf-err", "request": "Deploy"},
            output_schema=IntentOutput,
        )


def test_foundry_agent_runtime_raises_invalid_agent_output():
    from unittest.mock import MagicMock
    from app.agentos.adapters.foundry_adapter import InvalidAgentOutputError
    from app.ports.interfaces import ChatCompletionResponse

    mock_provider = MagicMock()
    mock_provider.complete_structured.return_value = ChatCompletionResponse(
        content="This is not json at all! {invalid syntax",
        raw_content="This is not json at all! {invalid syntax",
        parsed_json=None,
        provider_latency_ms=1.0,
    )

    runtime = FoundryAgentRuntime(chat_provider=mock_provider, max_repair_attempts=1)
    with pytest.raises(InvalidAgentOutputError):
        runtime.invoke(
            agent_role=AgentRole.INTENT,
            system_prompt="Extract intent",
            context={"workflow_id": "wf-fail", "request": "Deploy"},
            output_schema=IntentOutput,
        )


def test_backup_probe_fails_without_credentials():
    """Backup probe must fail honestly when AWS credentials are not configured or bucket unreachable."""
    runner = ProductionProbeRunner()
    probe = runner.run_probe("backup_accessible", "db-cluster.internal", {"bucket": "vulcan-backups"})
    assert probe.passed is False
    assert probe.details.get("status") in ("credentials_missing", "unconfigured", "empty", "client_error", "error")
    assert probe.details.get("simulation") is False


def test_backup_probe_succeeds_with_mocked_recent_snapshot():
    """Backup probe must pass when bucket exists and has a recent snapshot."""
    from unittest.mock import patch, MagicMock
    from datetime import datetime, timezone, timedelta

    runner = ProductionProbeRunner()
    mock_s3 = MagicMock()
    now = datetime.now(timezone.utc)
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "backups/pg_dump_20260914.tar.gz", "LastModified": now - timedelta(hours=2)}
        ]
    }
    with patch("boto3.client", return_value=mock_s3):
        probe = runner.run_probe("backup_accessible", "db-cluster.internal", {"bucket": "vulcan-backups", "max_age_hours": 24})
        assert probe.passed is True
        assert probe.details.get("status") == "accessible_and_recent"
        assert probe.details.get("latest_snapshot_key") == "backups/pg_dump_20260914.tar.gz"


def test_telemetry_probe_fails_when_unconfigured_or_unreachable():
    """Telemetry probe must return passed=False when endpoint is unconfigured or unreachable."""
    runner = ProductionProbeRunner()
    probe = runner.run_probe("telemetry_active", "db-cluster.internal", {"agent": "datadog"})
    assert probe.passed is False
    assert probe.details.get("status") in ("unconfigured", "unreachable", "inactive")
    assert probe.details.get("simulation") is False


def test_telemetry_probe_succeeds_on_200():
    """Telemetry probe must return passed=True when health check endpoint returns 200."""
    from unittest.mock import patch, MagicMock
    runner = ProductionProbeRunner()
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.__enter__.return_value = mock_resp
    with patch("urllib.request.urlopen", return_value=mock_resp):
        probe = runner.run_probe("telemetry_active", "db-cluster.internal", {"endpoint": "http://127.0.0.1:5555/status"})
        assert probe.passed is True
        assert probe.details.get("status") == "active"
        assert probe.details.get("status_code") == 200


def test_unknown_probe_returns_unsupported():
    """Unknown probe type must return passed=False with unsupported status."""
    runner = ProductionProbeRunner()
    probe = runner.run_probe("magic_unicorn_check", "db-cluster.internal", {})
    assert probe.passed is False
    assert probe.details.get("status") == "unsupported_probe_type"
    assert probe.details.get("simulation") is False


def test_disk_capacity_fails_when_insufficient():
    """A 500GB requirement must fail against a disk with less capacity."""
    runner = ProductionProbeRunner()
    # Set AGENTOS_TARGET_HOST to localhost so we test the local path
    os.environ["AGENTOS_TARGET_HOST"] = "127.0.0.1"
    try:
        probe = runner.run_probe("disk_capacity", "127.0.0.1", {"mount": "/", "min_gb": 999999})
        assert probe.passed is False, "Disk probe should fail when min_gb exceeds actual capacity"
        assert probe.details.get("simulation") is False
        assert probe.details.get("min_gb") == 999999
    finally:
        del os.environ["AGENTOS_TARGET_HOST"]


def test_disk_capacity_remote_returns_unverified():
    """Disk capacity for a remote (non-local) host must return unverified."""
    runner = ProductionProbeRunner()
    os.environ["AGENTOS_TARGET_HOST"] = "10.0.0.99"
    try:
        probe = runner.run_probe("disk_capacity", "remote-db.internal", {"mount": "/var/lib/pgsql", "min_gb": 500})
        assert probe.passed is False
        assert probe.details.get("status") == "unverified"
        assert probe.details.get("simulation") is False
    finally:
        del os.environ["AGENTOS_TARGET_HOST"]


def test_service_status_no_local_systemctl_fallback():
    """Service status probe must NOT fall back to local systemctl when remote TCP fails."""
    runner = ProductionProbeRunner()
    # Use a non-listening port on localhost — should fail without systemctl rescue
    probe = runner.run_probe("service_status", "127.0.0.1", {
        "service": "postgresql-16",
        "port": 59999,
        "timeout": 0.2,
    })
    assert probe.passed is False
    assert probe.details.get("status") == "inactive"
    assert probe.details.get("simulation") is False
