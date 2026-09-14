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

    # 6. Real Execution via AnsibleRunnerExecutionAdapter
    ctx = kernel.step(ctx.workflow_id)
    assert ctx.current_state == WorkflowState.VERIFYING
    assert ctx.execution_result.get("exit_code") == 0
    assert ctx.execution_result.get("runner") == "ansible_runner_adapter"

    # 7. Independent Verification via ProductionProbeRunner (mocked at test boundary)
    from unittest.mock import patch, MagicMock
    with patch("socket.create_connection"), patch("psycopg.connect") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("PostgreSQL 16.2 on x86_64-pc-linux-gnu",)
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        ctx = kernel.step(ctx.workflow_id)
        assert ctx.current_state == WorkflowState.SUCCESS
        probes = ctx.postcondition_verification.get("probes", [])
        assert len(probes) >= 4
        assert all(p["passed"] for p in probes)


def test_ansible_runner_execution_adapter_executes_artifact(tmp_path):
    adapter = AnsibleRunnerExecutionAdapter(base_dir=str(tmp_path / "runner"))
    assert adapter.is_simulation is False
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
    runtime = FoundryAgentRuntime()
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
