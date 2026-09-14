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
    assert data["status"] in ("HEALTHY", "CONFIGURED", "AVAILABLE", "CONNECTED")
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


def test_preflight_unknown_provider_rejected_with_400(admin_client):
    """Unknown provider must return HTTP 400 and 'Unsupported provider', NOT fabricated 200/HEALTHY."""
    res = admin_client.post(
        "/api/v1/external-resources/test-connection",
        json={
            "provider": "unknown_hypervisor_fabric",
            "endpoint": "https://unknown.internal",
            "config": {},
            "secret_refs": {},
        },
    )
    assert res.status_code == 400
    data = res.json()
    assert "Unsupported provider" in data["detail"]


def test_e2e_bot_has_platform_admin_in_connection_authorization():
    """e2e.bot must have Platform Admin privileges in external resources API."""
    app = create_app()
    c = TestClient(app, headers={"Authorization": "Bearer vlc_test_bot_ci_token"})
    res = c.post(
        "/api/v1/external-resources/test-connection",
        json={
            "provider": "redis",
            "endpoint": "redis://127.0.0.1:6379",
            "config": {},
            "secret_refs": {},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("HEALTHY", "CONFIGURED", "CONNECTED")

