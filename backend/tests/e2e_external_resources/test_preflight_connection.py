"""
Project Vulcan: Tests for Pre-flight Connection Testing (M5 / R5)
"""
import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app


@pytest.fixture
def admin_client():
    app = create_app()
    return TestClient(app, headers={"Authorization": "Bearer vlc_test_dave_ci_token"})


def test_preflight_connection_probe_success(admin_client):
    """Admin can execute pre-flight reachability probe on unpersisted parameters."""
    res = admin_client.post(
        "/api/v1/external-resources/test-connection",
        json={
            "provider": "docker",
            "endpoint": "unix:///var/run/docker.sock",
            "config": {},
            "secret_refs": {},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("HEALTHY", "CONFIGURED", "AVAILABLE")
    assert "latency_ms" in data


def test_preflight_connection_probe_unauthenticated(client=None):
    """Unauthenticated preflight request returns 401."""
    app = create_app()
    c = TestClient(app)
    res = c.post(
        "/api/v1/external-resources/test-connection",
        json={"provider": "docker"},
    )
    assert res.status_code == 401
