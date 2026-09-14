"""
Project Vulcan: Tests for Autonomous Assistant Preparation & Outcome Reporting
Verifies auto_prepare, missing information clarification, in-place resumption,
plan summaries, and verified execution outcomes.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app


@pytest.fixture
def admin_client():
    app = create_app()
    return TestClient(app, headers={"Authorization": "Bearer vlc_test_dave_ci_token"})


def test_auto_prepare_redis_workflow(admin_client):
    """
    Submitting an outcome request with auto_prepare=True automatically runs preparation
    and returns a plain-English plan summary.
    """
    res = admin_client.post(
        "/api/v1/agentos/workflows",
        json={
            "original_request": "Deploy Redis on node-redis-01.internal with port 6380 and maxmemory 1024MB",
            "environment": "DEV",
            "auto_prepare": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    wf_id = data["workflow_id"]
    # In DEV, auto-prepared all the way to EXECUTION_READY (or WAITING_FOR_APPROVAL)
    assert data["current_state"] in ("EXECUTION_READY", "WAITING_FOR_APPROVAL")
    
    # Check plan summary
    summary = data.get("plan_summary")
    assert summary is not None
    assert "Redis" in summary["synopsis"]
    assert "node-redis-01.internal" in summary["synopsis"]
    assert summary["target_host"] == "node-redis-01.internal"
    assert summary["parameters"]["port"] == 6380
    assert summary["parameters"]["maxmemory_mb"] == 1024


def test_missing_target_pauses_with_clarification_and_auto_resumes(admin_client):
    """
    Vague target triggers WAITING_FOR_INPUT. Supplying the server auto-resumes to decision state.
    """
    # 1. Request without explicit target server
    res = admin_client.post(
        "/api/v1/agentos/workflows",
        json={
            "original_request": "Deploy Redis on my development server with 1 GB memory",
            "environment": "DEV",
            "auto_prepare": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    wf_id = data["workflow_id"]
    assert data["current_state"] == "WAITING_FOR_INPUT"
    assert "Which development server should I use" in data["plan_summary"]["next_action"]

    # 2. Operator supplies server
    input_res = admin_client.post(
        f"/api/v1/agentos/workflows/{wf_id}/input",
        json={"operator_input": {"server": "dev-cache-01.internal"}},
    )
    assert input_res.status_code == 200
    resumed_data = input_res.json()
    # Auto-advanced to EXECUTION_READY / WAITING_FOR_APPROVAL
    assert resumed_data["current_state"] in ("EXECUTION_READY", "WAITING_FOR_APPROVAL")
    assert "dev-cache-01.internal" in resumed_data["plan_summary"]["synopsis"]


def test_deploy_workflow_executes_and_honestly_verifies(admin_client):
    """
    Deploying an authorized workflow executes tasks, probes target port 6380, and reports honest outcome.
    """
    create_res = admin_client.post(
        "/api/v1/agentos/workflows",
        json={
            "original_request": "Deploy Redis on cache-02.internal with port 6380 and maxmemory 512MB",
            "environment": "DEV",
            "auto_prepare": True,
        },
    )
    wf_id = create_res.json()["workflow_id"]

    # Deploy
    deploy_res = admin_client.post(f"/api/v1/agentos/workflows/{wf_id}/deploy")
    assert deploy_res.status_code == 200
    data = deploy_res.json()
    assert data["current_state"] == "SUCCESS"

    # Verify honest execution summary
    summary = data.get("plan_summary", {})
    exec_summary = summary.get("execution_summary", {})
    assert exec_summary["exit_code"] == 0
    assert "Host configuration applied successfully" in exec_summary["what_changed"]
    assert "All dynamic probes passed" in exec_summary["verification_established"]
