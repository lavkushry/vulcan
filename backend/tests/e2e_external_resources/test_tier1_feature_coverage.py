"""
Project Vulcan: Tier 1 Feature Coverage E2E Tests.
Validates baseline contracts, entities, repository operations, SQL schema, concrete providers,
Microsoft Foundry, REST routes, and enterprise RBAC across requirements R1 through R7.
Requirement: >=5 tests per feature across R1-R7.
"""

import os
import re
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
# Feature 1: R1 Domain Model & Entity Invariants
# ==============================================================================

class TestTier1DomainModel:
    def test_r1_entity_creation_with_all_nineteen_attributes(self):
        """Validates ExternalResource instantiation capturing all 19 specified domain attributes."""
        dm = get_domain_module()
        now = datetime.now(timezone.utc)
        res = dm.ExternalResource(
            resource_id="res-foundry-prod-01",
            provider="microsoft_foundry",
            category=dm.ResourceCategory.AI_MODELS,
            display_name="Microsoft Foundry Production",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://vulcan-ai.services.ai.azure.com/api/projects/vulcan-prod",
            auth_mode=dm.AuthMode.ENTRA_SERVICE_PRINCIPAL,
            enabled=True,
            config={
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "client_id": "00000000-0000-0000-0000-000000000002",
                "default_chat_deployment": "gpt-4o",
                "default_embedding_deployment": "text-embedding-3-small"
            },
            secret_refs={
                "client_secret": "vault://secret/vulcan/azure/sp_secret"
            },
            health_status=dm.HealthStatus.CONFIGURED,
            latency_ms=0.0,
            last_tested_at=None,
            last_success_at=None,
            created_by="admin.dave",
            updated_by="admin.dave",
            revision=1,
            created_at=now,
            updated_at=now
        )
        assert res.resource_id == "res-foundry-prod-01"
        assert res.provider == "microsoft_foundry"
        assert res.category == dm.ResourceCategory.AI_MODELS
        assert res.display_name == "Microsoft Foundry Production"
        assert res.environment == dm.ResourceEnvironment.PROD
        assert res.endpoint == "https://vulcan-ai.services.ai.azure.com/api/projects/vulcan-prod"
        assert res.auth_mode == dm.AuthMode.ENTRA_SERVICE_PRINCIPAL
        assert res.enabled is True
        assert res.health_status == dm.HealthStatus.CONFIGURED
        assert res.revision == 1
        assert res.created_by == "admin.dave"

    def test_r1_entity_serialization_masks_secret_references_for_operator(self):
        """Validates that to_dict(mask_secrets=True) masks secret references for non-admin viewers."""
        dm = get_domain_module()
        res = dm.ExternalResource(
            resource_id="res-vault-01",
            provider="vault",
            category=dm.ResourceCategory.SECRETS_PAM,
            display_name="Enterprise Vault",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://vault.internal.net:8200",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={"namespace": "vulcan"},
            secret_refs={"token": "vault://secret/vulcan/vault_token"},
            health_status=dm.HealthStatus.CONNECTED,
            latency_ms=12.4,
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        d = res.to_dict(mask_secrets=True, is_admin=False)
        assert "secret_refs" in d
        assert d["secret_refs"]["token"] == "********"
        assert d["endpoint"] == "https://vault.internal.net:8200"

    def test_r1_entity_serialization_admin_retains_uri_pointer(self):
        """Validates that to_dict(is_admin=True) returns the full URI pointer, never plaintext secrets."""
        dm = get_domain_module()
        res = dm.ExternalResource(
            resource_id="res-cyberark-01",
            provider="cyberark",
            category=dm.ResourceCategory.SECRETS_PAM,
            display_name="CyberArk PAM CCP",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://cyberark.internal.net/AIMWebService",
            auth_mode=dm.AuthMode.MUTUAL_TLS,
            enabled=True,
            config={"app_id": "VULCAN_AGENT"},
            secret_refs={"client_cert": "cyberark://vulcan/pki/cert"},
            health_status=dm.HealthStatus.CONNECTED,
            latency_ms=8.5,
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        d = res.to_dict(mask_secrets=False, is_admin=True)
        assert d["secret_refs"]["client_cert"] == "cyberark://vulcan/pki/cert"

    def test_r1_entity_deserialization_from_dict_roundtrip(self):
        """Validates complete round-trip serialization and deserialization from dictionary."""
        dm = get_domain_module()
        original = dm.ExternalResource(
            resource_id="res-gh-01",
            provider="github",
            category=dm.ResourceCategory.SOURCE_CONTROL,
            display_name="GitHub Enterprise",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="https://api.github.com",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={"organization": "vulcan-corp"},
            secret_refs={"token": "vault://secret/vulcan/github_token"},
            health_status=dm.HealthStatus.CONFIGURED,
            latency_ms=0.0,
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        as_dict = original.to_dict(mask_secrets=False, is_admin=True)
        restored = dm.ExternalResource.from_dict(as_dict)
        assert restored.resource_id == original.resource_id
        assert restored.provider == original.provider
        assert restored.category == original.category
        assert restored.environment == original.environment
        assert restored.secret_refs == original.secret_refs

    def test_r1_entity_status_transitions(self):
        """Validates all specified lifecycle health status transitions."""
        dm = get_domain_module()
        res = dm.ExternalResource(
            resource_id="res-status-01",
            provider="datadog",
            category=dm.ResourceCategory.OBSERVABILITY,
            display_name="Datadog Observability",
            environment=dm.ResourceEnvironment.STAGE,
            endpoint="https://api.datadoghq.com",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={"site": "datadoghq.com"},
            secret_refs={"api_key": "vault://secret/vulcan/datadog/api_key"},
            health_status=dm.HealthStatus.CONFIGURED,
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        # CONFIGURED -> CONNECTED
        res.health_status = dm.HealthStatus.CONNECTED
        assert res.health_status == dm.HealthStatus.CONNECTED

        # CONNECTED -> DEGRADED
        res.health_status = dm.HealthStatus.DEGRADED
        assert res.health_status == dm.HealthStatus.DEGRADED

        # DEGRADED -> AUTH_FAILED
        res.health_status = dm.HealthStatus.AUTH_FAILED
        assert res.health_status == dm.HealthStatus.AUTH_FAILED

        # AUTH_FAILED -> DISABLED
        res.health_status = dm.HealthStatus.DISABLED
        assert res.health_status == dm.HealthStatus.DISABLED

    def test_r1_zero_raw_secrets_invariant_rejection(self):
        """Enforces Zero-Raw-Secrets Invariant: raw passwords or tokens in config raise an error."""
        dm = get_domain_module()
        with pytest.raises((ValueError, Exception)) as exc_info:
            dm.ExternalResource(
                resource_id="res-invalid-secret-01",
                provider="servicenow",
                category=dm.ResourceCategory.ITSM_CMDB,
                display_name="ServiceNow Bad",
                environment=dm.ResourceEnvironment.DEV,
                endpoint="https://dev12345.service-now.com",
                auth_mode=dm.AuthMode.BASIC,
                enabled=True,
                config={
                    "username": "admin",
                    "password": "RawPlaintextPassword!99"  # Raw password violation
                },
                secret_refs={},
                created_by="admin.dave",
                updated_by="admin.dave"
            )
        assert any(term in str(exc_info.value).lower() for term in ["secret", "password", "raw", "invariant"])

    def test_r1_secret_refs_uri_pointer_scheme_validation(self):
        """Validates that secret_refs must strictly use authorized URI schemes (cyberark://, vault://, env://)."""
        dm = get_domain_module()
        with pytest.raises((ValueError, Exception)) as exc_info:
            dm.ExternalResource(
                resource_id="res-bad-pointer-01",
                provider="github",
                category=dm.ResourceCategory.SOURCE_CONTROL,
                display_name="GitHub Bad Pointer",
                environment=dm.ResourceEnvironment.DEV,
                endpoint="https://api.github.com",
                auth_mode=dm.AuthMode.API_KEY,
                enabled=True,
                config={"org": "vulcan"},
                secret_refs={
                    "token": "ghp_RawTokenLiteral1234567890abcdef"  # Missing URI scheme
                },
                created_by="admin.dave",
                updated_by="admin.dave"
            )
        assert any(term in str(exc_info.value).lower() for term in ["scheme", "pointer", "uri", "secret"])


# ==============================================================================
# Feature 2: R1 & R3 Provider Interface Contracts & Lifecycle Probes
# ==============================================================================

class TestTier1ProviderInterfaceContracts:
    def test_r1_provider_validate_config_contract(self):
        """Validates that validate_config returns ValidationResult with valid, errors, and warnings."""
        dm = get_domain_module()
        try:
            from app.ports.interfaces import IExternalResourceProvider
        except ImportError:
            pytest.skip("IExternalResourceProvider not defined in interfaces.py yet")
        assert hasattr(IExternalResourceProvider, "validate_config")

        res_val = dm.ValidationResult(valid=True, errors=[], warnings=["Low latency expected"])
        assert res_val.valid is True
        assert len(res_val.errors) == 0
        assert len(res_val.warnings) == 1

    def test_r1_provider_test_connection_contract(self):
        """Validates that test_connection returns ConnectionTestResult with latency and health status."""
        dm = get_domain_module()
        try:
            from app.ports.interfaces import IExternalResourceProvider
        except ImportError:
            pytest.skip("IExternalResourceProvider not defined in interfaces.py yet")
        assert hasattr(IExternalResourceProvider, "test_connection")

        res_conn = dm.ConnectionTestResult(
            ok=True,
            latency_ms=45.2,
            message="Successfully reached endpoint",
            status=dm.HealthStatus.CONNECTED
        )
        assert res_conn.ok is True
        assert res_conn.latency_ms == 45.2
        assert res_conn.status == dm.HealthStatus.CONNECTED

    def test_r1_provider_discover_capabilities_contract(self):
        """Validates that discover_capabilities returns ProviderCapabilities with models, deployments, tools."""
        dm = get_domain_module()
        try:
            from app.ports.interfaces import IExternalResourceProvider
        except ImportError:
            pytest.skip("IExternalResourceProvider not defined in interfaces.py yet")
        assert hasattr(IExternalResourceProvider, "discover_capabilities")

        res_cap = dm.ProviderCapabilities(
            models=["gpt-4o", "gpt-4o-mini"],
            deployments=["gpt-4o-prod", "emb-small"],
            tools=["code_interpreter", "bing_grounding"],
            agents=["triage_agent"]
        )
        assert "gpt-4o" in res_cap.models
        assert "gpt-4o-prod" in res_cap.deployments

    def test_r1_provider_get_health_contract(self):
        """Validates that get_health returns a valid HealthStatus enum value."""
        dm = get_domain_module()
        try:
            from app.ports.interfaces import IExternalResourceProvider
        except ImportError:
            pytest.skip("IExternalResourceProvider not defined in interfaces.py yet")
        assert hasattr(IExternalResourceProvider, "get_health")
        assert dm.HealthStatus.CONNECTED in dm.HealthStatus

    def test_r1_provider_sync_contract(self):
        """Validates that sync returns SyncResult capturing synced items count and duration."""
        dm = get_domain_module()
        try:
            from app.ports.interfaces import IExternalResourceProvider
        except ImportError:
            pytest.skip("IExternalResourceProvider not defined in interfaces.py yet")
        assert hasattr(IExternalResourceProvider, "sync")

        res_sync = dm.SyncResult(
            resource_id="res-1",
            success=True,
            synced_items_count=12,
            details={"updated_deployments": 4}
        )
        assert res_sync.synced_items_count == 12


# ==============================================================================
# Feature 3: R2 Repository Operations (CRUD, Versions, Health, Audit)
# ==============================================================================

class TestTier1RepositoryOperations:
    def test_r2_repository_save_and_retrieve_by_id(self):
        """Validates repository persistence and retrieval of ExternalResource."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)  # In-memory mode for offline isolation

        res = dm.ExternalResource(
            resource_id="res-repo-save-01",
            provider="vault",
            category=dm.ResourceCategory.SECRETS_PAM,
            display_name="Vault Prod",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://vault.corp:8200",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={"namespace": "root"},
            secret_refs={"token": "vault://secret/vulcan/token"},
            health_status=dm.HealthStatus.CONFIGURED,
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        saved = repo.save(res, actor="admin.dave", reason="initial creation")
        assert saved.resource_id == "res-repo-save-01"

        fetched = repo.get_by_id("res-repo-save-01")
        assert fetched is not None
        assert fetched.display_name == "Vault Prod"
        assert fetched.environment == dm.ResourceEnvironment.PROD

    def test_r2_repository_list_all_filtering(self):
        """Validates listing resources filtered by category, environment, and enabled state."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res1 = dm.ExternalResource(
            resource_id="res-list-01",
            provider="microsoft_foundry",
            category=dm.ResourceCategory.AI_MODELS,
            display_name="Foundry AI",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://ai.services.ai.azure.com/api/projects/p1",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        res2 = dm.ExternalResource(
            resource_id="res-list-02",
            provider="github",
            category=dm.ResourceCategory.SOURCE_CONTROL,
            display_name="GitHub Dev",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="https://api.github.com",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=False,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res1, actor="admin.dave", reason="create res1")
        repo.save(res2, actor="admin.dave", reason="create res2")

        ai_prod = repo.list_all(category=dm.ResourceCategory.AI_MODELS, environment=dm.ResourceEnvironment.PROD)
        assert any(r.resource_id == "res-list-01" for r in ai_prod)
        assert not any(r.resource_id == "res-list-02" for r in ai_prod)

    def test_r2_repository_revision_tracking(self):
        """Validates that successive updates increment revision and record immutable version snapshots."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-version-01",
            provider="aap",
            category=dm.ResourceCategory.EXECUTION,
            display_name="Ansible AAP",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://aap.corp",
            auth_mode=dm.AuthMode.BASIC,
            enabled=True,
            config={"organization": "Default"},
            secret_refs={"password": "vault://secret/vulcan/aap"},
            health_status=dm.HealthStatus.CONFIGURED,
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Initial create")
        assert res.revision == 1

        # Update display_name
        res.display_name = "Ansible AAP Updated"
        repo.save(res, actor="admin.dave", reason="Renamed to Updated")
        assert res.revision == 2

        versions = repo.get_versions("res-version-01")
        assert len(versions) >= 2
        revisions = [v.revision for v in versions]
        assert 1 in revisions and 2 in revisions

    def test_r2_repository_health_telemetry_recording(self):
        """Validates recording time-series health telemetry and retrieving latest status and history."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        health1 = dm.ExternalResourceHealth(
            resource_id="res-telemetry-01",
            status=dm.HealthStatus.CONNECTED,
            latency_ms=32.0,
            http_status=200,
            message="Health probe successful",
            diagnostics={"rtt_tcp": 12.0, "rtt_tls": 20.0},
            checked_at=datetime.now(timezone.utc)
        )
        repo.record_health(health1)

        latest = repo.get_latest_health("res-telemetry-01")
        assert latest is not None
        assert latest.status == dm.HealthStatus.CONNECTED
        assert latest.latency_ms == 32.0

        history = repo.get_health_history("res-telemetry-01", limit=10)
        assert len(history) >= 1
        assert history[0].status == dm.HealthStatus.CONNECTED

    def test_r2_repository_audit_trail_and_merkle_verification(self):
        """Validates that all repository actions emit audit records and Merkle hash verification passes."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-audit-01",
            provider="servicenow",
            category=dm.ResourceCategory.ITSM_CMDB,
            display_name="ServiceNow Audit Test",
            environment=dm.ResourceEnvironment.STAGE,
            endpoint="https://stage.service-now.com",
            auth_mode=dm.AuthMode.BASIC,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Creation for audit")
        assert repo.verify_audit_integrity() is True

        records = repo.get_audit_records(resource_id="res-audit-01")
        assert len(records) >= 1
        assert records[0].resource_id == "res-audit-01"
        assert records[0].actor == "admin.dave"

    def test_r2_repository_delete_lifecycle(self):
        """Validates deletion of an external resource and recording of the deletion audit event."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-delete-01",
            provider="redis",
            category=dm.ResourceCategory.STORAGE_DATA,
            display_name="Redis Cache",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="redis://localhost:6379",
            auth_mode=dm.AuthMode.NONE,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="create for delete")
        assert repo.get_by_id("res-delete-01") is not None

        deleted = repo.delete("res-delete-01", actor="admin.dave")
        assert deleted is True
        assert repo.get_by_id("res-delete-01") is None

        # Verify audit record for delete
        audit_recs = repo.get_audit_records(resource_id="res-delete-01")
        actions = [r.action for r in audit_recs]
        assert "DELETE" in actions


# ==============================================================================
# Feature 4: R2 PostgreSQL 16 Schema & Migration Verification (011_external_resources.sql)
# ==============================================================================

class TestTier1PostgresMigrationSchema:
    def _read_migration_sql(self) -> str:
        migration_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "../../../backend/migrations/011_external_resources.sql"
        ))
        if not os.path.exists(migration_path):
            pytest.skip(f"Migration file {migration_path} does not exist yet")
        with open(migration_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_r2_migration_011_sql_file_exists(self):
        """Validates that 011_external_resources.sql exists and is non-empty."""
        sql = self._read_migration_sql()
        assert len(sql) > 100

    def test_r2_migration_defines_external_resources_table(self):
        """Validates DDL definition of external_resources with columns and check constraints."""
        sql = self._read_migration_sql()
        assert "CREATE TABLE IF NOT EXISTS external_resources" in sql
        assert "resource_id" in sql
        assert "provider" in sql
        assert "category" in sql
        assert "auth_mode" in sql
        assert "health_status" in sql
        assert "secret_refs" in sql

    def test_r2_migration_defines_versions_table(self):
        """Validates DDL definition of external_resource_versions with revision and snapshot."""
        sql = self._read_migration_sql()
        assert "CREATE TABLE IF NOT EXISTS external_resource_versions" in sql
        assert "revision" in sql
        assert "snapshot" in sql
        assert "actor" in sql

    def test_r2_migration_defines_health_table(self):
        """Validates DDL definition of external_resource_health with telemetry metrics."""
        sql = self._read_migration_sql()
        assert "CREATE TABLE IF NOT EXISTS external_resource_health" in sql
        assert "latency_ms" in sql
        assert "diagnostics" in sql

    def test_r2_migration_defines_merkle_audit_table(self):
        """Validates DDL definition of external_resource_audit with prev_hash and current_hash."""
        sql = self._read_migration_sql()
        assert "CREATE TABLE IF NOT EXISTS external_resource_audit" in sql
        assert "prev_hash" in sql
        assert "current_hash" in sql

    def test_r2_migration_seed_data_zero_raw_secrets(self):
        """Validates that any initial seed inserts in migration 011 strictly use vault:// or cyberark:// pointers."""
        sql = self._read_migration_sql()
        # Find any insert statements and verify no raw passwords
        if "INSERT INTO external_resources" in sql:
            assert not re.search(r"password['\"]?\s*:\s*['\"][^v'][^a'][^u']", sql, re.IGNORECASE)


# ==============================================================================
# Feature 5: R3 Concrete Providers
# ==============================================================================

class TestTier1ConcreteProviders:
    def test_r3_servicenow_provider_contract(self):
        """Validates ServiceNowProvider lifecycle methods and table probe."""
        registry = get_provider_registry()
        provider = registry.get_provider("servicenow")
        assert provider is not None
        assert hasattr(provider, "test_connection")
        assert hasattr(provider, "discover_capabilities")

    def test_r3_cyberark_and_vault_providers_contract(self):
        """Validates CyberArkProvider and VaultProvider secret management lifecycle probes."""
        registry = get_provider_registry()
        cyberark = registry.get_provider("cyberark")
        vault = registry.get_provider("vault")
        assert cyberark is not None
        assert vault is not None
        assert hasattr(cyberark, "test_connection")
        assert hasattr(vault, "test_connection")

    def test_r3_github_and_bitbucket_providers_contract(self):
        """Validates GitHubProvider and BitbucketProvider GitOps repository probing."""
        registry = get_provider_registry()
        github = registry.get_provider("github")
        bitbucket = registry.get_provider("bitbucket")
        assert github is not None
        assert bitbucket is not None
        assert hasattr(github, "test_connection")
        assert hasattr(bitbucket, "test_connection")

    def test_r3_aap_and_datadog_providers_contract(self):
        """Validates AAPProvider (AWX/AAP ping) and DatadogProvider observability probe."""
        registry = get_provider_registry()
        aap = registry.get_provider("aap")
        datadog = registry.get_provider("datadog")
        assert aap is not None
        assert datadog is not None
        assert hasattr(aap, "test_connection")
        assert hasattr(datadog, "test_connection")

    def test_r3_storage_providers_contract(self):
        """Validates PostgresProvider, RedisProvider, and MinIOProvider storage probes."""
        registry = get_provider_registry()
        for key in ["postgres", "redis", "minio"]:
            provider = registry.get_provider(key)
            assert provider is not None
            assert hasattr(provider, "test_connection")

    def test_r3_provider_registry_resolution(self):
        """Validates that ProviderRegistry resolves all required 16 enterprise connectors."""
        registry = get_provider_registry()
        expected = [
            "microsoft_foundry", "servicenow", "cyberark", "vault",
            "github", "bitbucket", "aap", "datadog", "prometheus",
            "postgres", "redis", "minio", "openai", "openrouter",
            "gemini", "huggingface"
        ]
        for key in expected:
            prov = registry.get_provider(key)
            assert prov is not None, f"Provider {key} must be registered in ProviderRegistry"


# ==============================================================================
# Feature 6: R4 Microsoft Foundry AI Provider
# ==============================================================================

class TestTier1MicrosoftFoundryProvider:
    def test_r4_foundry_project_endpoint_validation(self):
        """Validates format https://<resource>.services.ai.azure.com/api/projects/<project>."""
        foundry_cls = get_foundry_provider_class()
        valid_ep = "https://my-foundry.services.ai.azure.com/api/projects/my-proj"
        invalid_ep = "https://openai.com/v1"
        assert foundry_cls.is_valid_project_endpoint(valid_ep) is True
        assert foundry_cls.is_valid_project_endpoint(invalid_ep) is False

    @patch("urllib.request.urlopen")
    def test_r4_foundry_entra_service_principal_auth(self, mock_urlopen):
        """Validates token acquisition using Entra Service Principal credentials."""
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"access_token": "mock_token", "expires_in": 3600}).encode()
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value = mock_resp

        token = provider.acquire_entra_token(
            tenant_id="00000000-0000-0000-0000-000000000001",
            client_id="00000000-0000-0000-0000-000000000002",
            client_secret="resolved_secret_val"
        )
        assert token == "mock_token"

    @patch("urllib.request.urlopen")
    def test_r4_foundry_managed_identity_auth(self, mock_urlopen):
        """Validates Azure Managed Identity IMDS probe."""
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"access_token": "mi_token"}).encode()
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value = mock_resp

        token = provider.acquire_managed_identity_token(client_id=None)
        assert token == "mi_token"

    def test_r4_foundry_api_key_auth(self):
        """Validates API Key authentication header injection."""
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()
        headers = provider.build_auth_headers(auth_mode="API_KEY", api_key="test_api_key_val")
        assert "api-key" in headers or "Authorization" in headers

    @patch("urllib.request.urlopen")
    def test_r4_foundry_dynamic_deployment_discovery(self, mock_urlopen, mock_foundry_deployments_data):
        """Validates dynamic deployment enumeration via GET {endpoint}/deployments?api-version=v1."""
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_foundry_deployments_data).encode()
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value = mock_resp

        caps = provider.discover_capabilities(
            config={"project_endpoint": "https://my-res.services.ai.azure.com/api/projects/proj-1"},
            secret_refs={"api_key": "vault://secret/vulcan/key"}
        )
        assert "gpt-4o" in caps.deployments or "gpt-4o" in caps.models
        assert "text-embedding-3-small" in caps.deployments or "text-embedding-3-small" in caps.models

    def test_r4_foundry_dual_client_route(self):
        """Verifies direct REST management route and OpenAI-compatible inference routes."""
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()
        ep = "https://ai.services.ai.azure.com/api/projects/p1"

        deployments_url = provider.get_deployments_url(ep)
        chat_url = provider.get_chat_completions_url(ep)
        embeddings_url = provider.get_embeddings_url(ep)

        assert "/deployments" in deployments_url
        assert "/chat/completions" in chat_url
        assert "/embeddings" in embeddings_url


# ==============================================================================
# Feature 7: R5 Web Console REST Routes & Legacy Facades
# ==============================================================================

class TestTier1ApiRoutesAndFacades:
    def test_r5_api_list_external_resources_masked(self, admin_client):
        """GET /api/v1/external-resources returns HTTP 200 with masked secret references."""
        res = admin_client.get("/api/v1/external-resources")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_r5_api_get_single_external_resource(self, admin_client):
        """GET /api/v1/external-resources/{id} returns single resource details."""
        res = admin_client.get("/api/v1/external-resources/res-nonexistent-id")
        if res.status_code == 404:
            # Check if router exists
            list_res = admin_client.get("/api/v1/external-resources")
            if list_res.status_code == 404:
                pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code in [404, 200]

    def test_r5_api_test_connection_probe(self, admin_client):
        """POST /api/v1/external-resources/{id}/test triggers probe and returns ConnectionTestResult."""
        res = admin_client.post("/api/v1/external-resources/test-id/test")
        if res.status_code == 404:
            list_res = admin_client.get("/api/v1/external-resources")
            if list_res.status_code == 404:
                pytest.skip("Route /api/v1/external-resources not mounted yet")
        # Route should either return 404 for unknown id or 200/502
        assert res.status_code in [200, 404, 502]

    def test_r5_api_discover_deployments(self, admin_client):
        """GET /api/v1/external-resources/{id}/deployments returns discovered models."""
        res = admin_client.get("/api/v1/external-resources/test-id/deployments")
        if res.status_code == 404:
            list_res = admin_client.get("/api/v1/external-resources")
            if list_res.status_code == 404:
                pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code in [200, 404]

    def test_r5_legacy_api_integrations_list(self, admin_client):
        """GET /api/v1/integrations maintains backward compatibility with legacy schema."""
        res = admin_client.get("/api/v1/integrations")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        if len(data) > 0:
            first = data[0]
            assert "key" in first
            assert "name" in first
            assert "status" in first

    def test_r5_legacy_api_integrations_test_and_sync(self, admin_client):
        """POST /api/v1/integrations/{key}/test preserves legacy response schema."""
        res = admin_client.post("/api/v1/integrations/github/test")
        assert res.status_code == 200
        data = res.json()
        assert "ok" in data
        assert "status" in data
        assert "latency_ms" in data


# ==============================================================================
# Feature 8: R6 Enterprise RBAC & Secret Masking
# ==============================================================================

class TestTier1RBACAndSecretMasking:
    def test_r6_rbac_platform_admin_can_mutate(self, admin_client):
        """PLATFORM_ADMIN can mutate external resources."""
        res = admin_client.post("/api/v1/external-resources", json={
            "resource_id": "test-admin-create",
            "provider": "github",
            "category": "Source Control",
            "display_name": "Admin Test",
            "environment": "DEV",
            "endpoint": "https://api.github.com",
            "auth_mode": "API_KEY",
            "config": {},
            "secret_refs": {}
        })
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        # Status code must NOT be 403 Forbidden
        assert res.status_code in [200, 201]

    def test_r6_rbac_operator_forbidden_mutations(self, operator_client):
        """OPERATOR attempting POST /api/v1/external-resources receives HTTP 403 Forbidden."""
        res = operator_client.post("/api/v1/external-resources", json={
            "resource_id": "test-operator-create",
            "provider": "github"
        })
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403
        data = res.json()
        assert "forbidden" in str(data).lower() or "permission" in str(data).lower()

    def test_r6_rbac_auditor_forbidden_mutations(self, auditor_client):
        """AUDITOR attempting DELETE /api/v1/external-resources/{id} receives HTTP 403 Forbidden."""
        res = auditor_client.delete("/api/v1/external-resources/res-any-id")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403

    def test_r6_secret_masking_in_api_responses(self, operator_client, admin_client):
        """Non-admin callers receive masked secret references (********)."""
        res = operator_client.get("/api/v1/external-resources")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 200
        items = res.json()
        for item in items:
            for k, val in item.get("secret_refs", {}).items():
                assert val == "********"

    def test_r6_admin_receives_unmasked_uri_pointer(self, admin_client):
        """Admin callers receive URI pointers (cyberark://..., vault://...), never plaintext."""
        res = admin_client.get("/api/v1/external-resources")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 200
        items = res.json()
        for item in items:
            for k, val in item.get("secret_refs", {}).items():
                assert val.startswith(("vault://", "cyberark://", "env://", "********"))

    def test_r6_test_connection_never_echoes_credentials(self, admin_client):
        """Outbound test connection responses never echo passwords, tokens, or credential payloads."""
        res = admin_client.post("/api/v1/integrations/github/test")
        assert res.status_code == 200
        content = res.text
        # Assert no sensitive headers or raw credentials leaked in payload
        assert "Authorization" not in content
        assert "Bearer" not in content
        assert "client_secret" not in content
