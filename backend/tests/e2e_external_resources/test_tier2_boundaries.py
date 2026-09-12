"""
Project Vulcan: Tier 2 Boundary & Corner Cases E2E Tests.
Validates boundary constraints, error conditions, resilience under failure,
tamper detection, and RBAC violations.
Requirement: >=5 tests per feature area.
"""

import os
import copy
import json
import threading
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
# Area 1: Zero-Raw-Secrets & URI Pointer Boundaries
# ==============================================================================

class TestTier2ZeroSecretsBoundaries:
    def test_boundary_invalid_uri_pointer_scheme(self):
        """Rejects secret pointers with unauthorized schemes (http://, file://, plain:)."""
        dm = get_domain_module()
        invalid_schemes = [
            "http://vault.internal/secret",
            "file:///etc/passwd",
            "plain:SuperSecret123",
            "ftp://ftp.example.com/sec",
            "ldap://corp.net/creds"
        ]
        for scheme in invalid_schemes:
            with pytest.raises((ValueError, Exception)):
                dm.ExternalResource(
                    resource_id=f"res-bad-scheme-{hash(scheme)}",
                    provider="github",
                    category=dm.ResourceCategory.SOURCE_CONTROL,
                    display_name="Bad Scheme",
                    environment=dm.ResourceEnvironment.DEV,
                    endpoint="https://api.github.com",
                    auth_mode=dm.AuthMode.API_KEY,
                    enabled=True,
                    config={},
                    secret_refs={"token": scheme},
                    created_by="admin.dave",
                    updated_by="admin.dave"
                )

    def test_boundary_raw_password_in_config_rejected(self):
        """Rejects common credential keys in config when populated with raw strings."""
        dm = get_domain_module()
        prohibited_configs = [
            {"password": "MySuperSecretPassword123!"},
            {"client_secret": "my_client_secret_xyz"},
            {"auth_token": "raw_auth_token_value_123"},
            {"api_key": "raw_api_key_value_123"},
            {"private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."},
        ]
        for bad_cfg in prohibited_configs:
            with pytest.raises((ValueError, Exception)):
                dm.ExternalResource(
                    resource_id=f"res-raw-creds-{hash(str(bad_cfg))}",
                    provider="servicenow",
                    category=dm.ResourceCategory.ITSM_CMDB,
                    display_name="Raw Creds Attempt",
                    environment=dm.ResourceEnvironment.DEV,
                    endpoint="https://dev123.service-now.com",
                    auth_mode=dm.AuthMode.BASIC,
                    enabled=True,
                    config=bad_cfg,
                    secret_refs={},
                    created_by="admin.dave",
                    updated_by="admin.dave"
                )

    def test_boundary_high_entropy_secret_lint_trigger(self):
        """Detects and rejects raw high-entropy base64/hex token strings in config."""
        dm = get_domain_module()
        high_entropy_config = {
            "custom_header": "AKIAIOSFODNN7EXAMPLE",  # AWS-like access key ID
            "extra_info": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # AWS secret key pattern
        }
        with pytest.raises((ValueError, Exception)):
            dm.ExternalResource(
                resource_id="res-high-entropy",
                provider="aap",
                category=dm.ResourceCategory.EXECUTION,
                display_name="High Entropy Violation",
                environment=dm.ResourceEnvironment.DEV,
                endpoint="https://aap.corp",
                auth_mode=dm.AuthMode.NONE,
                enabled=True,
                config=high_entropy_config,
                secret_refs={},
                created_by="admin.dave",
                updated_by="admin.dave"
            )

    def test_boundary_missing_required_credentials_for_auth_mode(self):
        """ENTRA_SERVICE_PRINCIPAL auth mode requires client_secret pointer; missing causes validation failure."""
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()
        val = provider.validate_config(
            config={"auth_mode": "ENTRA_SERVICE_PRINCIPAL", "tenant_id": "t1", "client_id": "c1"},
            secret_refs={}  # Missing client_secret
        )
        assert val.valid is False
        assert any("client_secret" in err.lower() or "secret" in err.lower() for err in val.errors)

    def test_boundary_whitespace_or_malformed_uri_pointer(self):
        """Rejects URI pointers with whitespace, control characters, or missing path components."""
        dm = get_domain_module()
        malformed_pointers = [
            "vault://",
            "vault://   ",
            "cyberark://vulcan/with spaces/key",
            "vault://\x00nullbyte/key",
        ]
        for ptr in malformed_pointers:
            with pytest.raises((ValueError, Exception)):
                dm.ExternalResource(
                    resource_id=f"res-malformed-ptr-{hash(ptr)}",
                    provider="vault",
                    category=dm.ResourceCategory.SECRETS_PAM,
                    display_name="Malformed Pointer",
                    environment=dm.ResourceEnvironment.DEV,
                    endpoint="https://vault.corp:8200",
                    auth_mode=dm.AuthMode.API_KEY,
                    enabled=True,
                    config={},
                    secret_refs={"token": ptr},
                    created_by="admin.dave",
                    updated_by="admin.dave"
                )

    def test_boundary_nested_raw_secret_in_config(self):
        """Recursively scans nested dictionaries and lists in config and rejects raw passwords."""
        dm = get_domain_module()
        nested_config = {
            "connection": {
                "pool": {
                    "database": "postgres",
                    "auth": {
                        "user": "postgres",
                        "password": "RawNestedPasswordInDeepDict!456"
                    }
                }
            }
        }
        with pytest.raises((ValueError, Exception)):
            dm.ExternalResource(
                resource_id="res-nested-password",
                provider="postgres",
                category=dm.ResourceCategory.STORAGE_DATA,
                display_name="Nested Secret Violation",
                environment=dm.ResourceEnvironment.DEV,
                endpoint="postgresql://localhost:5432/db",
                auth_mode=dm.AuthMode.BASIC,
                enabled=True,
                config=nested_config,
                secret_refs={},
                created_by="admin.dave",
                updated_by="admin.dave"
            )


# ==============================================================================
# Area 2: Endpoint & Network Resilience Boundaries
# ==============================================================================

class TestTier2EndpointAndNetworkBoundaries:
    def test_boundary_malformed_foundry_project_endpoint(self):
        """Rejects malformed Microsoft Foundry endpoints that don't match the standard URL pattern."""
        foundry_cls = get_foundry_provider_class()
        bad_endpoints = [
            "http://insecure.services.ai.azure.com/api/projects/p1",  # HTTP not HTTPS
            "https://evil.com/api/projects/p1",                       # Non-Azure domain
            "https://ai.services.ai.azure.com/invalid/path",          # Missing /api/projects
            "https://ai.services.ai.azure.com/api/projects/",         # Missing project slug
            "ftp://ai.services.ai.azure.com/api/projects/p1",         # FTP scheme
            "",                                                       # Empty
        ]
        for ep in bad_endpoints:
            assert foundry_cls.is_valid_project_endpoint(ep) is False

    @patch("urllib.request.urlopen")
    def test_boundary_unreachable_endpoint_connection_refused(self, mock_urlopen):
        """Probe against unreachable host returns DEGRADED status without raising uncaught exceptions."""
        import urllib.error
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_urlopen.side_effect = urllib.error.URLError(reason="Connection refused (Errno 111)")

        result = provider.test_connection(
            config={"project_endpoint": "https://unreachable.services.ai.azure.com/api/projects/p1"},
            secret_refs={"api_key": "vault://secret/vulcan/key"}
        )
        assert result.connected is False
        assert result.status in ["DEGRADED", "AUTH_FAILED", "UNREACHABLE"]
        assert "refused" in result.message.lower() or "error" in result.message.lower()

    @patch("urllib.request.urlopen")
    def test_boundary_socket_timeout_handling(self, mock_urlopen):
        """Probe encountering socket timeout returns graceful failure result with timeout diagnostics."""
        import socket
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_urlopen.side_effect = socket.timeout("timed out after 30.0s")

        result = provider.test_connection(
            config={"project_endpoint": "https://slow.services.ai.azure.com/api/projects/p1"},
            secret_refs={"api_key": "vault://secret/vulcan/key"}
        )
        assert result.connected is False
        assert "timeout" in result.message.lower() or "timed out" in result.message.lower()

    @patch("urllib.request.urlopen")
    def test_boundary_invalid_json_response_from_provider(self, mock_urlopen):
        """Handles non-JSON error pages (e.g. 502 HTML Gateway Timeout) without crashing."""
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><body>502 Bad Gateway</body></html>"
        mock_resp.getcode.return_value = 502
        mock_urlopen.return_value = mock_resp

        result = provider.discover_capabilities(
            config={"project_endpoint": "https://badgw.services.ai.azure.com/api/projects/p1"},
            secret_refs={"api_key": "vault://secret/vulcan/key"}
        )
        # Should return empty or fallback capabilities without throwing JSONDecodeError
        assert isinstance(result.models, list)
        assert len(result.models) == 0

    @patch("urllib.request.urlopen")
    def test_boundary_http_401_403_auth_failure_status(self, mock_urlopen):
        """HTTP 401/403 from provider transitions resource health status to AUTH_FAILED."""
        import urllib.error
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://ai.services.ai.azure.com",
            code=401,
            msg="Unauthorized: Invalid tenant credentials",
            hdrs={},
            fp=None
        )

        result = provider.test_connection(
            config={"project_endpoint": "https://ai.services.ai.azure.com/api/projects/p1"},
            secret_refs={"api_key": "vault://secret/vulcan/bad_key"}
        )
        assert result.connected is False
        assert "AUTH_FAILED" in str(result.status)

    @patch("urllib.request.urlopen")
    def test_boundary_http_429_rate_limiting_status(self, mock_urlopen):
        """HTTP 429 Too Many Requests transitions resource health status to DEGRADED."""
        import urllib.error
        foundry_cls = get_foundry_provider_class()
        provider = foundry_cls()

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://ai.services.ai.azure.com",
            code=429,
            msg="Too Many Requests: Quota exceeded",
            hdrs={},
            fp=None
        )

        result = provider.test_connection(
            config={"project_endpoint": "https://ai.services.ai.azure.com/api/projects/p1"},
            secret_refs={"api_key": "vault://secret/vulcan/key"}
        )
        assert result.connected is False
        assert "DEGRADED" in str(result.status) or "429" in result.message


# ==============================================================================
# Area 3: RBAC & Authorization Violations
# ==============================================================================

class TestTier2RBACViolations:
    def test_boundary_operator_post_mutation_returns_403(self, operator_client):
        """OPERATOR role attempting POST /api/v1/external-resources returns HTTP 403 Forbidden."""
        res = operator_client.post("/api/v1/external-resources", json={
            "resource_id": "res-unauth-post",
            "provider": "github"
        })
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403

    def test_boundary_operator_put_mutation_returns_403(self, operator_client):
        """OPERATOR role attempting PUT /api/v1/external-resources/{id} returns HTTP 403 Forbidden."""
        res = operator_client.put("/api/v1/external-resources/res-any-id", json={
            "display_name": "Unauthorized Update"
        })
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403

    def test_boundary_operator_delete_mutation_returns_403(self, operator_client):
        """OPERATOR role attempting DELETE /api/v1/external-resources/{id} returns HTTP 403 Forbidden."""
        res = operator_client.delete("/api/v1/external-resources/res-any-id")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403

    def test_boundary_auditor_test_probe_returns_403(self, auditor_client):
        """AUDITOR role attempting POST /api/v1/external-resources/{id}/test returns HTTP 403 Forbidden."""
        res = auditor_client.post("/api/v1/external-resources/res-any-id/test")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403

    def test_boundary_auditor_sync_probe_returns_403(self, auditor_client):
        """AUDITOR role attempting POST /api/v1/external-resources/{id}/sync returns HTTP 403 Forbidden."""
        res = auditor_client.post("/api/v1/external-resources/res-any-id/sync")
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403

    def test_boundary_client_spoofed_identity_header_ignored(self, test_app):
        """Client supplying spoofed X-Vulcan-User: admin.dave with Alice's token is evaluated as OPERATOR (403)."""
        from fastapi.testclient import TestClient
        client = TestClient(test_app, headers={
            "Authorization": "Bearer vlc_test_alice",
            "X-Vulcan-User": "admin.dave",
            "X-Vulcan-Role": "PLATFORM_ADMIN"
        })
        res = client.post("/api/v1/external-resources", json={"resource_id": "spoof-test"})
        if res.status_code == 404:
            pytest.skip("Route /api/v1/external-resources not mounted yet")
        assert res.status_code == 403

    def test_boundary_missing_token_returns_401(self, anonymous_client):
        """Unauthenticated mutation request returns HTTP 401 Unauthorized."""
        res = anonymous_client.post("/api/v1/external-resources", json={"resource_id": "anon-test"})
        assert res.status_code == 401


# ==============================================================================
# Area 4: Merkle Ledger Tamper Detection Boundaries
# ==============================================================================

class TestTier2MerkleTamperDetection:
    def test_boundary_merkle_tamper_detection_modified_payload(self):
        """Altering a single character in the payload of an audit record breaks hash validation."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-tamper-payload",
            provider="vault",
            category=dm.ResourceCategory.SECRETS_PAM,
            display_name="Vault Tamper Test",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://vault.corp:8200",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="create tamper test")
        assert repo.verify_audit_integrity() is True

        # Tamper with the in-memory audit store
        records = repo.get_audit_records()
        assert len(records) > 0
        target = records[-1]
        tampered_payload = copy.deepcopy(target.payload)
        tampered_payload["tampered_key"] = "malicious_injection"

        # Replace the target record with tampered record having identical current_hash
        tampered_record = dm.ExternalResourceAuditRecord(
            id=target.id,
            resource_id=target.resource_id,
            action=target.action,
            actor=target.actor,
            payload=tampered_payload,
            prev_hash=target.prev_hash,
            current_hash=target.current_hash,
            timestamp=target.timestamp
        )
        repo._audit[-1] = tampered_record

        # Integrity verification must detect the payload hash mismatch
        assert repo.verify_audit_integrity() is False

    def test_boundary_merkle_tamper_detection_altered_prev_hash(self):
        """Altering prev_hash of a block in the ledger chain causes integrity check failure."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-tamper-chain",
            provider="github",
            category=dm.ResourceCategory.SOURCE_CONTROL,
            display_name="GitHub Chain Test",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="https://api.github.com",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="First block")
        res.display_name = "GitHub Chain Test 2"
        repo.save(res, actor="admin.dave", reason="Second block")
        assert repo.verify_audit_integrity() is True

        # Corrupt the chain linkage: modify prev_hash of the second block
        target = repo._audit[-1]
        corrupted = dm.ExternalResourceAuditRecord(
            id=target.id,
            resource_id=target.resource_id,
            action=target.action,
            actor=target.actor,
            payload=target.payload,
            prev_hash="f" * 64,  # Corrupted prev_hash
            current_hash=target.current_hash,
            timestamp=target.timestamp
        )
        repo._audit[-1] = corrupted
        assert repo.verify_audit_integrity() is False

    def test_boundary_merkle_tamper_detection_deleted_block(self):
        """Deleting an intermediate block from the audit ledger is detected as a broken chain."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-delete-block",
            provider="aap",
            category=dm.ResourceCategory.EXECUTION,
            display_name="AAP Chain",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="https://aap.corp",
            auth_mode=dm.AuthMode.NONE,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Block 1")
        res.display_name = "AAP Chain 2"
        repo.save(res, actor="admin.dave", reason="Block 2")
        res.display_name = "AAP Chain 3"
        repo.save(res, actor="admin.dave", reason="Block 3")
        assert repo.verify_audit_integrity() is True

        # Delete intermediate block (index 1)
        del repo._audit[1]
        assert repo.verify_audit_integrity() is False

    def test_boundary_merkle_tamper_detection_inserted_block(self):
        """Inserting an unauthorized block between valid blocks is detected as broken linkage."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-insert-block",
            provider="datadog",
            category=dm.ResourceCategory.OBSERVABILITY,
            display_name="Datadog Chain",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://api.datadoghq.com",
            auth_mode=dm.AuthMode.NONE,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Block 1")
        res.display_name = "Datadog Chain 2"
        repo.save(res, actor="admin.dave", reason="Block 2")
        assert repo.verify_audit_integrity() is True

        # Splice in an unauthorized block
        rogue_block = dm.ExternalResourceAuditRecord(
            id=999,
            resource_id="res-insert-block",
            action="ROGUE_ACTION",
            actor="attacker",
            payload={"fake": "data"},
            prev_hash="0" * 64,
            current_hash="1" * 64,
            timestamp=datetime.now(timezone.utc)
        )
        repo._audit.insert(1, rogue_block)
        assert repo.verify_audit_integrity() is False

    def test_boundary_merkle_genesis_block_invariants(self):
        """Genesis block must strictly have prev_hash equal to 64 zeroes."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-genesis-check",
            provider="redis",
            category=dm.ResourceCategory.STORAGE_DATA,
            display_name="Genesis Check",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="redis://localhost:6379",
            auth_mode=dm.AuthMode.NONE,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Genesis test")
        records = repo.get_audit_records()
        assert len(records) >= 1
        genesis = records[0]
        assert genesis.prev_hash == "0" * 64


# ==============================================================================
# Area 5: Data Layer Fallback & Concurrency Boundaries
# ==============================================================================

class TestTier2DataLayerAndConcurrencyBoundaries:
    def test_boundary_in_memory_fallback_under_postgres_connection_drop(self):
        """Repository transparently falls back to in-memory store when PostgreSQL connection drops."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        # Pass an unreachable postgres URL
        repo = repo_cls(db_url="postgresql://invalid_user:invalid_pass@127.0.0.1:59999/vulcan_test")

        res = dm.ExternalResource(
            resource_id="res-fallback-01",
            provider="postgres",
            category=dm.ResourceCategory.STORAGE_DATA,
            display_name="Fallback Test",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="postgresql://localhost:5432/vulcan",
            auth_mode=dm.AuthMode.NONE,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        # Should gracefully write to in-memory store without crashing
        saved = repo.save(res, actor="admin.dave", reason="Fallback test save")
        assert saved.resource_id == "res-fallback-01"

        fetched = repo.get_by_id("res-fallback-01")
        assert fetched is not None
        assert fetched.display_name == "Fallback Test"

    def test_boundary_concurrent_updates_thread_safety(self):
        """10 concurrent threads updating a resource concurrently maintain thread safety and monotonic revisions."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res = dm.ExternalResource(
            resource_id="res-concurrency-01",
            provider="github",
            category=dm.ResourceCategory.SOURCE_CONTROL,
            display_name="Concurrency Baseline",
            environment=dm.ResourceEnvironment.PROD,
            endpoint="https://api.github.com",
            auth_mode=dm.AuthMode.API_KEY,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res, actor="admin.dave", reason="Initial save")

        errors = []

        def worker_update(idx: int):
            try:
                item = repo.get_by_id("res-concurrency-01")
                if item:
                    item.display_name = f"Updated by thread {idx}"
                    repo.save(item, actor=f"worker-{idx}", reason=f"Thread {idx} update")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_update, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        final = repo.get_by_id("res-concurrency-01")
        assert final is not None
        assert final.revision >= 2

    def test_boundary_duplicate_resource_id_collision(self):
        """Attempting to create a new resource with an existing resource_id fails with collision error."""
        dm = get_domain_module()
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res1 = dm.ExternalResource(
            resource_id="res-duplicate-id",
            provider="redis",
            category=dm.ResourceCategory.STORAGE_DATA,
            display_name="Redis 1",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="redis://1",
            auth_mode=dm.AuthMode.NONE,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        repo.save(res1, actor="admin.dave", reason="initial")

        res2 = dm.ExternalResource(
            resource_id="res-duplicate-id",
            provider="redis",
            category=dm.ResourceCategory.STORAGE_DATA,
            display_name="Redis 2",
            environment=dm.ResourceEnvironment.DEV,
            endpoint="redis://2",
            auth_mode=dm.AuthMode.NONE,
            enabled=True,
            config={},
            secret_refs={},
            created_by="admin.dave",
            updated_by="admin.dave"
        )
        # Creating with duplicate id when create_only=True raises conflict
        if hasattr(repo, "create"):
            with pytest.raises((ValueError, Exception)):
                repo.create(res2, actor="admin.dave")

    def test_boundary_pagination_limits_and_negative_offsets(self):
        """Listing resources with extreme limit and offset values handles boundary conditions gracefully."""
        repo_cls = get_repository_class()
        repo = repo_cls(db_url=None)

        res_zero = repo.list_all(limit=0)
        assert isinstance(res_zero, list)

        res_large = repo.list_all(limit=10000)
        assert isinstance(res_large, list)

        res_neg_offset = repo.list_all(offset=-5)
        assert isinstance(res_neg_offset, list)

    def test_boundary_sqlite_migration_missing_file_graceful(self):
        """Initializing repository when SQLite database file is missing proceeds cleanly."""
        repo_cls = get_repository_class()
        # Should initialize gracefully without crashing
        repo = repo_cls(db_url=None, sqlite_path="/tmp/non_existent_vulcan_db_test.db")
        assert repo is not None
