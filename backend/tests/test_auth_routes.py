"""
Project Vulcan: Tests for Auth & Identity Routes
Verifies session check, token verification, and fail-closed RBAC permissions.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_session_unauthenticated(client):
    """Calling /api/v1/auth/session without a token returns unauthenticated state without 401."""
    res = client.get("/api/v1/auth/session")
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is False
    assert data["user_id"] is None
    assert data["role"] is None
    assert data["permissions"] == []
    assert data["status"] == "unauthenticated"


def test_session_authenticated_admin(client):
    """Calling /api/v1/auth/session with Dave's token returns PLATFORM_ADMIN profile and permissions."""
    headers = {"Authorization": "Bearer vlc_test_dave_ci_token"}
    res = client.get("/api/v1/auth/session", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["user_id"] == "admin.dave"
    assert data["role"] == "PLATFORM_ADMIN"
    assert data["role_badge"] == "PLATFORM ADMIN"
    assert "workflow:create" in data["permissions"]


def test_session_authenticated_operator(client):
    """Calling /api/v1/auth/session with Alice's token returns OPERATOR profile."""
    headers = {"Authorization": "Bearer vlc_test_alice_ci_token"}
    res = client.get("/api/v1/auth/session", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["user_id"] == "eng.alice"
    assert data["role"] == "OPERATOR"
    assert data["role_badge"] == "OPERATOR"


def test_me_unauthenticated_returns_401(client):
    """Calling /api/v1/auth/me without token returns 401 Unauthorized."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_me_authenticated_returns_user(client):
    """Calling /api/v1/auth/me with valid token returns user details."""
    headers = {"Authorization": "Bearer vlc_test_dave_ci_token"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["user_id"] == "admin.dave"


def test_verify_token_valid(client):
    """POST /api/v1/auth/verify-token validates a known token and returns identity."""
    res = client.post("/api/v1/auth/verify-token", json={"token": "vlc_test_bob_ci_token"})
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["user_id"] == "lead.bob"
    assert data["role"] == "APPROVING_LEAD"


def test_verify_token_invalid_returns_401(client):
    """POST /api/v1/auth/verify-token rejects invalid token with 401."""
    res = client.post("/api/v1/auth/verify-token", json={"token": "totally-fake-token-12345"})
    assert res.status_code == 401
