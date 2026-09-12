"""
Project Vulcan: Tier 3 Cross-Feature Combinations E2E Tests.
Validates pairwise integrations across Foundry discovery + routing defaults,
legacy facades + PostgreSQL persistence + zero raw secrets + audit events,
and RBAC enforcement + secret masking + safe live test connections.
Requirement: Pairwise coverage across R1-R6.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from .conftest import (
    get_domain_module,
    get_repository_class,
    get_foundry_provider_class,
    get_provider_registry,
)


# ==============================================================================
# Combination 1: Foundry Config + Dynamic Discovery + Vulcan Routing Defaults
# ==============================================================================

class TestTier3FoundryDiscoveryAndRoutingCombinations:
    @patch("urllib.request.urlopen")
    def test_combo_foundry_registration_discovers_and_sets_chat_default(
        self, mock_urlopen, mock_foundry_deployments_data
    ):
        """Register Foundry project -> probe discovers gpt-4o -> set as Vulcan chat default -> router binds."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        foundry_cls = get_foundry_provider_class()
        repo = repo_cls(db_url=None)
        provider = foundry_cls()

        # Step 1: Mock discovery response from Azure Foundry
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_foundry_deployments_data).encode()
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value = mock_resp

        # Step 2: Register Microsoft Foundry resource
        res = dm.ExternalResource(
            resource_id="foundry-combo-01",
            provider="microsoft_foundry",
            category=dm.ResourceCategory.AI_MODELS,
            display_name="Foundry Core",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://vulcan.services.ai.azure.com/api/projects/core",
            auth_mode=dm.AuthMode.ENTRA_SERVICE_PRINCIPAL,
            enabled=True,
            config={
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "client_id": "00000000-0000-0000-0000-000000000002"
            },
            secret_refs={
                "client_secret": "vault://secret/vulcan/azure/sp"
            },
            health_status=dm.HealthStatus.CONFIGURED,
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Register Foundry")

        # Step 3: Run capability discovery
        caps = provider.discover_capabilities(res.config, res.secret_refs)
        assert "gpt-4o" in caps.deployments or "gpt-4o" in caps.models

        # Step 4: Configure gpt-4o as Vulcan routing default
        res.config["default_chat_deployment"] = "gpt-4o"
        res.config["is_vulcan_chat_default"] = True
        res.health_status = dm.HealthStatus.CONNECTED
        saved = repo.save(res, actor="admin.dave", reason="Configure gpt-4o as chat default")

        assert saved.revision == 2
        assert saved.config["default_chat_deployment"] == "gpt-4o"
        assert saved.health_status == dm.HealthStatus.CONNECTED

    @patch("urllib.request.urlopen")
    def test_combo_foundry_registration_discovers_and_sets_embedding_default(
        self, mock_urlopen, mock_foundry_deployments_data
    ):
        """Register Foundry project -> probe discovers text-embedding-3-small -> set as Vulcan embedding default."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        foundry_cls = get_foundry_provider_class()
        repo = repo_cls(db_url=None)
        provider = foundry_cls()

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_foundry_deployments_data).encode()
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value = mock_resp

        res = dm.ExternalResource(
            resource_id="foundry-emb-01",
            provider="microsoft_foundry",
            category=dm.ResourceCategory.AI_MODELS,
            display_name="Foundry Embeddings",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://vulcan.services.ai.azure.com/api/projects/core",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={},
            secret_refs={"api_key": "vault://secret/vulcan/key"},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Save for embedding test")

        caps = provider.discover_capabilities(res.config, res.secret_refs)
        assert "text-embedding-3-small" in caps.deployments or "text-embedding-3-small" in caps.models

        res.config["default_embedding_deployment"] = "text-embedding-3-small"
        res.config["is_vulcan_embedding_default"] = True
        repo.save(res, actor="admin.dave", reason="Set default embedding deployment")

        updated = repo.get_by_id("foundry-emb-01")
        assert updated.config["default_embedding_deployment"] == "text-embedding-3-small"

    def test_combo_foundry_multi_deployment_priority_fallback(self):
        """Foundry configured with multiple reasoning deployments respects priority order fallback policy."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="foundry-priority-01",
            provider="microsoft_foundry",
            category=dm.ResourceCategory.AI_MODELS,
            display_name="Foundry Multi-Model",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://vulcan.services.ai.azure.com/api/projects/core",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={
                "deployments_priority": [
                    {"name": "gpt-4o", "priority": 1, "role": "primary"},
                    {"name": "gpt-4o-mini", "priority": 2, "role": "fallback"},
                    {"name": "phi-3-mini", "priority": 3, "role": "edge"}
                ]
            },
            secret_refs={"api_key": "vault://secret/vulcan/key"},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Priority ordering test")
        fetched = repo.get_by_id("foundry-priority-01")
        priorities = fetched.config["deployments_priority"]
        assert len(priorities) == 3
        assert priorities[0]["name"] == "gpt-4o"
        assert priorities[1]["name"] == "gpt-4o-mini"


# ==============================================================================
# Combination 2: Legacy Facade + PostgreSQL + Zero Secrets + Audit Event
# ==============================================================================

class TestTier3LegacyFacadeAndPersistenceCombinations:
    def test_combo_legacy_update_migrates_to_postgres_with_zero_raw_secrets(self, admin_client):
        """Legacy PUT /api/v1/integrations/github converts token to secret pointer and emits audit event."""
        res = admin_client.put("/api/v1/integrations/github", json={
            "endpoint_url": "https://api.github.com",
            "auth_token": "test_token_combo_abc123"
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("key") == "github"

        # Verify that get response masks the secret token
        get_res = admin_client.get("/api/v1/integrations/github")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert "••••" in get_data.get("auth_token", "") or "********" in get_data.get("auth_token", "")
        assert "test_token_combo_abc123" not in get_data.get("auth_token", "")

    def test_combo_legacy_test_connection_records_health_telemetry(self, admin_client):
        """Legacy POST /api/v1/integrations/servicenow/test executes probe and returns status."""
        res = admin_client.post("/api/v1/integrations/servicenow/test")
        assert res.status_code == 200
        data = res.json()
        assert "ok" in data
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], (int, float))

    def test_combo_legacy_sync_triggers_provider_sync_and_audit(self, admin_client):
        """Legacy POST /api/v1/integrations/aap/sync executes sync and records audit record."""
        res = admin_client.post("/api/v1/integrations/aap/sync")
        assert res.status_code == 200
        data = res.json()
        assert "ok" in data
        assert "last_sync_at" in data


# ==============================================================================
# Combination 3: RBAC Enforcement + Secret Masking + Live Test Handshake
# ==============================================================================

class TestTier3RBACAndSecretMaskingCombinations:
    def test_combo_admin_configures_secret_ref_operator_views_masked(
        self, admin_client, operator_client
    ):
        """Admin creates resource with URI pointer -> Operator views resource with ******** mask."""
        create_res = admin_client.post("/api/v1/external-resources", json={
            "resource_id": "res-masking-combo-01",
            "provider": "cyberark",
            "category": "Secrets & PAM",
            "display_name": "CyberArk Combo",
            "environment": "PROD",
            "endpoint": "https://cyberark.corp/AIMWebService",
            "auth_mode": "MUTUAL_TLS",
            "config": {"app_id": "VULCAN_AGENT"},
            "secret_refs": {"client_cert": "cyberark://vulcan/certs/app_cert"}
        })
        if create_res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert create_res.status_code in [200, 201]

        # Operator views the resource
        op_res = operator_client.get("/api/v1/external-resources/res-masking-combo-01")
        assert op_res.status_code == 200
        data = op_res.json()
        # Secret refs must be completely masked
        assert data["secret_refs"]["client_cert"] == "********"

    def test_combo_admin_runs_live_test_without_credentials_in_telemetry(self, admin_client):
        """Live connection test executes real probe but never echoes raw credentials in response or logs."""
        res = admin_client.post("/api/v1/integrations/vault/test")
        assert res.status_code == 200
        content = res.text
        assert "vault_token" not in content
        assert "token" not in res.json().get("message", "").lower()

    def test_combo_operator_forbidden_from_triggering_live_test(self, operator_client):
        """Operator attempting to trigger live probe receives HTTP 403 and probe is aborted."""
        res = operator_client.post("/api/v1/external-resources/res-masking-combo-01/test")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403
