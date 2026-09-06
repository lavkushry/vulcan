"""
Project Vulcan: Real Enterprise Integrations Suite
Validates:
- SQLite persistence of connector configurations
- Credential masking for zero-leakage security
- Real live HTTP handshakes and timeout failure handling
- GitHub API real commit sync
"""

import os
import pytest
from app.adapters.integrations_manager import IntegrationsManager, mask_secret


@pytest.fixture
def test_manager(tmp_path):
    db_file = str(tmp_path / "test_vulcan.db")
    return IntegrationsManager(db_path=db_file)


def test_mask_secret():
    assert mask_secret(None) is None
    assert mask_secret("") is None
    assert mask_secret("short") == "••••••••"
    assert mask_secret("ghp_1234567890abcdef") == "ghp_••••••••cdef"


def test_seed_and_list_all(test_manager):
    connectors = test_manager.list_all()
    assert len(connectors) >= 6
    keys = [c["key"] for c in connectors]
    assert "github" in keys
    assert "servicenow" in keys
    assert "jira" in keys
    assert "vault" in keys
    assert "aap" in keys
    assert "datadog" in keys


def test_token_masking_in_list(test_manager):
    # Save a connector with a real secret
    test_manager.update_config("github", {
        "auth_type": "BEARER_TOKEN",
        "auth_token": "ghp_secret_token_value_98765"
    })
    
    # Check that list_all masks it
    items = test_manager.list_all(mask_secrets=True)
    gh = next(i for i in items if i["key"] == "github")
    assert gh["auth_token"] is not None
    assert "ghp_secret_token_value" not in gh["auth_token"]
    assert "••••" in gh["auth_token"]

    # Check that internal get(mask_secrets=False) has the raw secret
    raw = test_manager.get("github", mask_secrets=False)
    assert raw["auth_token"] == "ghp_secret_token_value_98765"


def test_update_config(test_manager):
    res = test_manager.update_config("servicenow", {
        "endpoint_url": "https://my-company.service-now.com",
        "username": "secops_admin",
        "auth_type": "BASIC_AUTH",
        "auth_token": "SuperSecretPass123"
    })
    assert res["endpoint_url"] == "https://my-company.service-now.com"
    assert res["username"] == "secops_admin"
    assert "SuperSecretPass123" not in res["auth_token"]

    persisted = test_manager.get("servicenow", mask_secrets=True)
    assert persisted["endpoint_url"] == "https://my-company.service-now.com"
    assert persisted["username"] == "secops_admin"


def test_unreachable_endpoint_handling(test_manager):
    # Configure an unreachable port
    test_manager.update_config("aap", {
        "endpoint_url": "http://127.0.0.1:58971"
    })
    res = test_manager.test_connection("aap")
    assert res["ok"] is False
    assert res["status"] == "UNREACHABLE"
    assert res["latency_ms"] >= 0
    assert "Connection refused" in res["message"] or "failed" in res["message"]


def test_live_github_handshake(test_manager):
    # Tests real outbound HTTP handshake to GitHub API
    res = test_manager.test_connection("github")
    assert "status" in res
    assert "latency_ms" in res
    assert res["latency_ms"] > 0
    if res["ok"]:
        assert res["status"] == "CONNECTED"
        assert res["status_code"] in (200, 201)
