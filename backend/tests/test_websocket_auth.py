"""
Project Vulcan: WebSocket Authentication Tests
Verifies query-parameter token authentication, close code 4401 on rejection, and live streaming when authenticated.
"""
import json
import os
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.server import create_app
from app.api.websockets import ws_hub


@pytest.fixture
def auth_client():
    old_disabled = os.environ.get("VULCAN_AUTH_DISABLED")
    old_tokens = os.environ.get("VULCAN_API_TOKENS")

    os.environ["VULCAN_AUTH_DISABLED"] = "0"
    os.environ["VULCAN_API_TOKENS"] = json.dumps({
        "vlc_test_alice_ws": "eng.alice",
        "vlc_test_bob_ws": "lead.bob"
    })

    app = create_app()
    client = TestClient(app)

    yield client

    if old_disabled is not None:
        os.environ["VULCAN_AUTH_DISABLED"] = old_disabled
    else:
        os.environ.pop("VULCAN_AUTH_DISABLED", None)

    if old_tokens is not None:
        os.environ["VULCAN_API_TOKENS"] = old_tokens
    else:
        os.environ.pop("VULCAN_API_TOKENS", None)


def test_websocket_missing_token_closes_with_4401(auth_client):
    """Connecting to WebSocket without a token must close with code 4401."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with auth_client.websocket_connect("/api/v1/ws/jobs/test-corr-001"):
            pass
    assert exc_info.value.code == 4401


def test_websocket_invalid_token_closes_with_4401(auth_client):
    """Connecting to WebSocket with an invalid token must close with code 4401."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with auth_client.websocket_connect("/api/v1/ws/jobs/test-corr-002?token=invalid_token_123"):
            pass
    assert exc_info.value.code == 4401


def test_websocket_valid_token_connects_and_replays(auth_client):
    """Connecting to WebSocket with a valid token succeeds and receives replayed events."""
    corr_id = "test-corr-valid-003"
    ws_hub.publish(corr_id, "status", {"status": "QUEUED", "message": "Initial state"})
    ws_hub.emit_log(corr_id, "Executing playbook task [1/3]...")

    with auth_client.websocket_connect(f"/api/v1/ws/jobs/{corr_id}?token=vlc_test_alice_ws") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "status"
        assert msg1["data"]["status"] == "QUEUED"

        msg2 = ws.receive_json()
        assert msg2["type"] == "stdout"
        assert "Executing playbook task" in msg2["data"]["line"]

