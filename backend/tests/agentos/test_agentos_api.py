"""
Project Vulcan: Tests for AgentOS Ultra REST Endpoints (AGENT-13)
"""
import pytest
from fastapi.testclient import TestClient
from app.api.server import app


@pytest.fixture
def client():
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer vlc_test_alice"})
    return c


def test_api_create_and_get_workflow(client):
    res = client.post(
        "/api/v1/agentos/workflows",
        json={
            "original_request": "Build PostgreSQL 16 cluster with Datadog",
            "requester_id": "alice@corp.internal",
            "environment": "PROD",
        },
    )
    assert res.status_code == 200
    data = res.json()
    wf_id = data["workflow_id"]
    assert data["current_state"] == "RECEIVED"
    assert data["requester_id"] == "alice@corp.internal"

    # Get workflow
    get_res = client.get(f"/api/v1/agentos/workflows/{wf_id}")
    assert get_res.status_code == 200
    assert get_res.json()["workflow_id"] == wf_id


def test_api_step_and_auto_run(client):
    create_res = client.post(
        "/api/v1/agentos/workflows",
        json={
            "original_request": "Deploy PostgreSQL 16 on 3 RHEL 9 nodes",
            "requester_id": "bob@corp.internal",
            "environment": "DEV",
        },
    )
    wf_id = create_res.json()["workflow_id"]

    # Advance 1 step
    step_res = client.post(f"/api/v1/agentos/workflows/{wf_id}/step")
    assert step_res.status_code == 200
    assert step_res.json()["current_state"] == "DISCOVERING"

    # Auto-run until paused or terminal
    auto_res = client.post(f"/api/v1/agentos/workflows/{wf_id}/auto-run")
    assert auto_res.status_code == 200
    auto_data = auto_res.json()
    assert auto_data["steps_taken"] >= 1


def test_api_list_agents_and_evals(client):
    res_agents = client.get("/api/v1/agentos/agents")
    assert res_agents.status_code == 200
    agents = res_agents.json()
    assert len(agents) >= 10
    agent_names = [a["agent_name"] for a in agents]
    assert "supervisor" in agent_names
    assert "builder" in agent_names
    assert "critic" in agent_names

    # Run eval tier 0
    eval_res = client.post("/api/v1/agentos/evals/run", json={"tier": 0})
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["tier"] == 0
    assert eval_data["pass_rate_pct"] >= 80.0

    # List evals
    list_res = client.get("/api/v1/agentos/evals")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
