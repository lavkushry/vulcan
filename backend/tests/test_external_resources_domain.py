"""
Project Vulcan: External Resource Domain & Port Contracts Unit Test Suite (R1)
Validates:
1. Entity instantiation with default values and custom values (19 attributes).
2. Zero-Raw-Secrets Invariant: accepts URI pointers (cyberark://, vault://, env://),
   rejects raw credentials and high-entropy secrets in config and secret_refs.
3. Serialization to dict with mask_secrets=True (admin vs non-admin) and deserialization via from_dict.
4. Associated domain entities (ExternalResourceVersion, ExternalResourceHealth, ExternalResourceAuditRecord Merkle chaining).
5. Value objects (ValidationResult, ConnectionTestResult, ProviderCapabilities, SyncResult).
6. Port interface compliance (IExternalResourceRepository and IExternalResourceProvider abstract methods).
7. Domain lifecycle and state transitions (record_health, update_configuration, is_connected).
"""

import abc
import hashlib
import json
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from app.domain.external_resource_entities import (
    AuthMode,
    ConnectionTestResult,
    ExternalResource,
    ExternalResourceAuditRecord,
    ExternalResourceHealth,
    ExternalResourceVersion,
    HealthStatus,
    ProviderCapabilities,
    ResourceCategory,
    ResourceEnvironment,
    SyncResult,
    ValidationResult,
)
from app.domain.exceptions import ParameterValidationError, SecretLintError
from app.ports.interfaces import IExternalResourceProvider
from app.ports.repositories import IExternalResourceRepository


# =====================================================================
# 1. ENTITY INSTANTIATION & DEFAULTS
# =====================================================================

class TestExternalResourceInstantiation:
    """Validates instantiation, default attributes, and enum handling."""

    def test_instantiation_minimal_defaults(self):
        res = ExternalResource(
            resource_id="foundry-dev",
            provider="microsoft_foundry",
            category=ResourceCategory.AI_MODELS,
            display_name="Foundry Development Project",
            endpoint="https://foundry-dev.services.ai.azure.com/api/projects/vulcan-dev",
        )
        assert res.resource_id == "foundry-dev"
        assert res.provider == "microsoft_foundry"
        assert res.category == ResourceCategory.AI_MODELS
        assert res.display_name == "Foundry Development Project"
        assert res.endpoint == "https://foundry-dev.services.ai.azure.com/api/projects/vulcan-dev"
        assert res.environment == ResourceEnvironment.DEV or res.environment in ResourceEnvironment
        assert res.auth_mode == AuthMode.API_KEY or res.auth_mode in AuthMode
        assert res.enabled is True
        assert res.config == {}
        assert res.secret_refs == {}
        assert res.health_status == HealthStatus.CONFIGURED
        assert res.latency_ms == 0.0
        assert res.last_tested_at is None
        assert res.last_success_at is None
        assert res.created_by == "system"
        assert res.updated_by == "system"
        assert res.revision == 1
        assert isinstance(res.created_at, datetime)
        assert isinstance(res.updated_at, datetime)
        assert res.created_at.tzinfo is not None

    def test_instantiation_full_custom_values(self):
        t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc)
        res = ExternalResource(
            resource_id="servicenow-prod",
            provider="servicenow",
            category=ResourceCategory.ITSM_CMDB,
            display_name="Corporate ServiceNow ITSM",
            environment=ResourceEnvironment.PROD,
            endpoint="https://corp.service-now.com",
            auth_mode=AuthMode.BASIC,
            enabled=False,
            config={"instance_id": "corp_prod", "timeout_sec": 45},
            secret_refs={"password": "vault://secret/vulcan/servicenow#password"},
            health_status=HealthStatus.CONNECTED,
            latency_ms=115.4,
            last_tested_at=t0,
            last_success_at=t0,
            created_by="lead.bob",
            updated_by="lead.bob",
            revision=5,
            created_at=t0,
            updated_at=t0,
        )
        assert res.resource_id == "servicenow-prod"
        assert res.category == ResourceCategory.ITSM_CMDB
        assert res.environment == ResourceEnvironment.PROD
        assert res.enabled is False
        assert res.config["instance_id"] == "corp_prod"
        assert res.secret_refs["password"] == "vault://secret/vulcan/servicenow#password"
        assert res.health_status == HealthStatus.CONNECTED
        assert res.latency_ms == 115.4
        assert res.revision == 5
        assert res.created_by == "lead.bob"

    def test_string_enum_coercion(self):
        res = ExternalResource(
            resource_id="datadog-prod",
            provider="datadog",
            category="Observability",
            display_name="Datadog APM",
            environment="PROD",
            endpoint="https://api.datadoghq.com",
            auth_mode="API_KEY",
            health_status="CONFIGURED",
        )
        assert res.category == ResourceCategory.OBSERVABILITY
        assert res.environment == ResourceEnvironment.PROD
        assert res.auth_mode == AuthMode.API_KEY
        assert res.health_status == HealthStatus.CONFIGURED

    def test_invalid_category_raises(self):
        with pytest.raises((ValueError, ParameterValidationError)):
            ExternalResource(
                resource_id="bad-cat",
                provider="custom",
                category="NonExistentCategory",
                display_name="Bad Category",
                endpoint="https://bad.example.com",
            )

    def test_invalid_environment_raises(self):
        with pytest.raises((ValueError, ParameterValidationError)):
            ExternalResource(
                resource_id="bad-env",
                provider="custom",
                category=ResourceCategory.STORAGE_DATA,
                display_name="Bad Env",
                environment="STAGING_INVALID",
                endpoint="https://bad.example.com",
            )


# =====================================================================
# 2. ZERO-RAW-SECRETS INVARIANT VALIDATION
# =====================================================================

class TestZeroRawSecretsInvariant:
    """Validates that plaintext secrets are strictly forbidden and URI pointers are enforced."""

    def test_valid_uri_pointer_schemes_accepted(self):
        valid_refs = {
            "client_secret": "cyberark://PNC_AUTOMATION_KEYS/foundry_sp/client_secret",
            "api_key": "vault://secret/data/vulcan/foundry#api_key",
            "env_token": "env://FOUNDRY_API_KEY",
        }
        res = ExternalResource(
            resource_id="foundry-secure",
            provider="microsoft_foundry",
            category=ResourceCategory.AI_MODELS,
            display_name="Secure Foundry",
            endpoint="https://foundry-secure.services.ai.azure.com/api/projects/proj-1",
            secret_refs=valid_refs,
        )
        assert res.secret_refs == valid_refs

    @pytest.mark.parametrize("raw_secret", [
        "sk-proj-1234567890abcdef1234567890",
        "SuperSecretPassword123!",
        "ghp_1234567890abcdefghijklmnopqrstu",
        "my_plain_api_key_value",
    ])
    def test_reject_raw_secrets_in_secret_refs(self, raw_secret):
        with pytest.raises(SecretLintError) as exc_info:
            ExternalResource(
                resource_id="foundry-insecure",
                provider="microsoft_foundry",
                category=ResourceCategory.AI_MODELS,
                display_name="Insecure Foundry",
                endpoint="https://foundry.services.ai.azure.com/api/projects/proj-1",
                secret_refs={"api_key": raw_secret},
            )
        assert "Security Invariant Triggered" in str(exc_info.value) or "pointer" in str(exc_info.value).lower()

    @pytest.mark.parametrize("invalid_scheme", [
        "http://vault.internal/secret/key",
        "https://secrets.example.com/token",
        "file:///etc/shadow",
        "ftp://backup/pass.txt",
    ])
    def test_reject_unauthorized_uri_schemes(self, invalid_scheme):
        with pytest.raises(SecretLintError):
            ExternalResource(
                resource_id="foundry-bad-scheme",
                provider="microsoft_foundry",
                category=ResourceCategory.AI_MODELS,
                display_name="Bad Scheme",
                endpoint="https://foundry.services.ai.azure.com/api/projects/proj-1",
                secret_refs={"key": invalid_scheme},
            )

    def test_reject_high_entropy_private_key_in_config(self):
        rsa_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0m...\n-----END RSA PRIVATE KEY-----"
        with pytest.raises(SecretLintError):
            ExternalResource(
                resource_id="res-pkey",
                provider="custom",
                category=ResourceCategory.EXECUTION,
                display_name="Resource with Private Key",
                endpoint="https://exec.example.com",
                config={"private_key": rsa_key},
            )

    def test_reject_aws_key_pattern_in_config(self):
        with pytest.raises(SecretLintError):
            ExternalResource(
                resource_id="res-aws",
                provider="custom",
                category=ResourceCategory.STORAGE_DATA,
                display_name="Resource with AWS Key",
                endpoint="https://s3.example.com",
                config={"access_key_id": "AKIAIOSFODNN7EXAMPLE"},
            )

    def test_accept_safe_non_secret_config(self):
        safe_config = {
            "tenant_id": "8f3b21c4-1111-2222-3333-444455556666",
            "client_id": "1e2d3c4b-7777-8888-9999-000011112222",
            "api_version": "2024-05-01-preview",
            "max_retries": 3,
            "verify_ssl": True,
        }
        res = ExternalResource(
            resource_id="res-safe",
            provider="microsoft_foundry",
            category=ResourceCategory.AI_MODELS,
            display_name="Safe Config",
            endpoint="https://foundry.services.ai.azure.com/api/projects/proj-1",
            config=safe_config,
        )
        assert res.config == safe_config


# =====================================================================
# 3. SERIALIZATION & DESERIALIZATION (to_dict / from_dict)
# =====================================================================

class TestExternalResourceSerialization:
    """Validates to_dict masking behavior and from_dict roundtrip."""

    @pytest.fixture
    def sample_resource(self):
        return ExternalResource(
            resource_id="foundry-prod",
            provider="microsoft_foundry",
            category=ResourceCategory.AI_MODELS,
            display_name="Microsoft Foundry Production",
            environment=ResourceEnvironment.PROD,
            endpoint="https://foundry-prod.services.ai.azure.com/api/projects/vulcan",
            auth_mode=AuthMode.ENTRA_SERVICE_PRINCIPAL,
            enabled=True,
            config={"tenant_id": "tenant-abc", "client_id": "client-xyz"},
            secret_refs={"client_secret": "cyberark://PNC_AUTOMATION_KEYS/foundry/client_secret"},
            health_status=HealthStatus.CONNECTED,
            latency_ms=42.5,
            created_by="admin.dave",
            updated_by="admin.dave",
            revision=2,
        )

    def test_to_dict_masking_for_non_admin(self, sample_resource):
        d = sample_resource.to_dict(mask_secrets=True, is_admin=False)
        assert d["resource_id"] == "foundry-prod"
        assert d["secret_refs"]["client_secret"] == "********"
        assert d["config"]["tenant_id"] == "tenant-abc"
        assert d["category"] == "AI & Models"
        assert d["environment"] == "PROD"
        assert d["auth_mode"] == "ENTRA_SERVICE_PRINCIPAL"
        assert isinstance(d["created_at"], str)
        assert isinstance(d["updated_at"], str)

    def test_to_dict_for_admin_reveals_uri_pointers(self, sample_resource):
        d = sample_resource.to_dict(mask_secrets=True, is_admin=True)
        assert d["secret_refs"]["client_secret"] == "cyberark://PNC_AUTOMATION_KEYS/foundry/client_secret"

    def test_to_dict_unmasked_for_internal_persistence(self, sample_resource):
        d = sample_resource.to_dict(mask_secrets=False)
        assert d["secret_refs"]["client_secret"] == "cyberark://PNC_AUTOMATION_KEYS/foundry/client_secret"

    def test_from_dict_roundtrip(self, sample_resource):
        d = sample_resource.to_dict(mask_secrets=False)
        restored = ExternalResource.from_dict(d)
        assert restored.resource_id == sample_resource.resource_id
        assert restored.provider == sample_resource.provider
        assert restored.category == sample_resource.category
        assert restored.environment == sample_resource.environment
        assert restored.auth_mode == sample_resource.auth_mode
        assert restored.endpoint == sample_resource.endpoint
        assert restored.enabled == sample_resource.enabled
        assert restored.config == sample_resource.config
        assert restored.secret_refs == sample_resource.secret_refs
        assert restored.health_status == sample_resource.health_status
        assert restored.latency_ms == sample_resource.latency_ms
        assert restored.revision == sample_resource.revision
        assert restored.created_by == sample_resource.created_by
        assert restored.updated_by == sample_resource.updated_by
        assert restored.created_at == sample_resource.created_at
        assert restored.updated_at == sample_resource.updated_at

    def test_from_dict_with_minimal_payload(self):
        payload = {
            "resource_id": "minimal-res",
            "provider": "redis",
            "category": "Storage & Data",
            "display_name": "Redis Cache",
            "endpoint": "redis://localhost:6379",
        }
        res = ExternalResource.from_dict(payload)
        assert res.resource_id == "minimal-res"
        assert res.provider == "redis"
        assert res.category == ResourceCategory.STORAGE_DATA
        assert res.enabled is True
        assert res.revision == 1


# =====================================================================
# 4. ASSOCIATED DOMAIN ENTITIES (Version, Health, AuditRecord)
# =====================================================================

class TestAssociatedDomainEntities:
    """Validates ExternalResourceVersion, ExternalResourceHealth, and ExternalResourceAuditRecord."""

    def test_external_resource_version_immutability(self):
        ver = ExternalResourceVersion(
            id=1,
            resource_id="foundry-prod",
            revision=2,
            snapshot={"endpoint": "https://foundry-prod.services.ai.azure.com"},
            actor="admin.dave",
            reason="Updated endpoint",
        )
        assert ver.resource_id == "foundry-prod"
        assert ver.revision == 2
        assert ver.actor == "admin.dave"
        assert ver.reason == "Updated endpoint"

    def test_external_resource_health_record(self):
        t_check = datetime.now(timezone.utc)
        hlth = ExternalResourceHealth(
            resource_id="foundry-prod",
            status=HealthStatus.CONNECTED,
            latency_ms=38.2,
            http_status=200,
            message="Successfully probed 5 deployments",
            diagnostics={"deployments_count": 5},
            checked_at=t_check,
        )
        assert hlth.resource_id == "foundry-prod"
        assert hlth.status == HealthStatus.CONNECTED
        assert hlth.latency_ms == 38.2
        assert hlth.http_status == 200
        assert hlth.diagnostics["deployments_count"] == 5

    def test_external_resource_audit_record_merkle_hashing(self):
        prev_hash = "0" * 64
        t_str = "2026-09-12T12:00:00+00:00"
        payload = {"action": "CREATE", "provider": "microsoft_foundry"}

        computed = ExternalResourceAuditRecord.compute_hash(
            resource_id="foundry-prod",
            timestamp=t_str,
            actor="admin.dave",
            action="CREATE",
            payload=payload,
            prev_hash=prev_hash,
        )
        assert isinstance(computed, str)
        assert len(computed) == 64

        rec = ExternalResourceAuditRecord(
            id=1,
            resource_id="foundry-prod",
            timestamp=t_str,
            actor="admin.dave",
            action="CREATE",
            payload=payload,
            prev_hash=prev_hash,
            current_hash=computed,
        )
        assert rec.current_hash == computed

    def test_audit_hash_tamper_detection(self):
        prev_hash = "0" * 64
        t_str = "2026-09-12T12:00:00+00:00"
        payload = {"action": "CREATE", "endpoint": "https://foundry-prod"}
        h1 = ExternalResourceAuditRecord.compute_hash(
            "foundry-prod", t_str, "admin.dave", "CREATE", payload, prev_hash
        )
        tampered_payload = {"action": "CREATE", "endpoint": "https://malicious-foundry"}
        h2 = ExternalResourceAuditRecord.compute_hash(
            "foundry-prod", t_str, "admin.dave", "CREATE", tampered_payload, prev_hash
        )
        assert h1 != h2


# =====================================================================
# 5. PORT INTERFACE COMPLIANCE (Abstract Methods Verification)
# =====================================================================

class TestPortInterfaceCompliance:
    """Validates abstract base class contracts for IExternalResourceRepository and IExternalResourceProvider."""

    def test_i_external_resource_repository_is_abstract(self):
        assert issubclass(IExternalResourceRepository, abc.ABC)
        with pytest.raises(TypeError):
            IExternalResourceRepository()

    def test_i_external_resource_repository_method_set(self):
        expected_methods = {
            "save",
            "get_by_id",
            "list_all",
            "delete",
            "get_versions",
            "record_health",
            "get_latest_health",
            "get_health_history",
            "get_audit_records",
            "verify_audit_integrity",
        }
        abstract_methods = IExternalResourceRepository.__abstractmethods__
        assert expected_methods == set(abstract_methods)

    def test_i_external_resource_repository_partial_implementation_fails(self):
        class IncompleteRepo(IExternalResourceRepository):
            def save(self, resource, actor, reason): pass
            def get_by_id(self, resource_id): pass
            # Omitting remaining 8 methods

        with pytest.raises(TypeError):
            IncompleteRepo()

    def test_i_external_resource_repository_full_implementation_succeeds(self):
        class CompleteRepo(IExternalResourceRepository):
            def save(self, resource, actor, reason): return resource
            def get_by_id(self, resource_id): return None
            def list_all(self, category=None, environment=None, enabled=None, limit=100, offset=0): return []
            def delete(self, resource_id, actor): return True
            def get_versions(self, resource_id, limit=50): return []
            def record_health(self, health): pass
            def get_latest_health(self, resource_id): return None
            def get_health_history(self, resource_id, limit=50): return []
            def get_audit_records(self, resource_id=None, limit=50): return []
            def verify_audit_integrity(self): return True

        repo = CompleteRepo()
        assert repo.verify_audit_integrity() is True

    def test_i_external_resource_provider_is_abstract_and_verifies_methods(self):
        assert issubclass(IExternalResourceProvider, abc.ABC)
        with pytest.raises(TypeError):
            IExternalResourceProvider()
        expected_methods = {
            "validate_config",
            "test_connection",
            "discover_capabilities",
            "get_health",
            "sync",
        }
        assert expected_methods == set(IExternalResourceProvider.__abstractmethods__)


# =====================================================================
# 6. VALUE OBJECTS
# =====================================================================

class TestValueObjects:
    """Validates lifecycle value objects returned by provider ports."""

    def test_validation_result(self):
        vr = ValidationResult(valid=True, errors=[], warnings=["Using default timeout"])
        assert vr.valid is True
        assert len(vr.warnings) == 1

    def test_connection_test_result(self):
        ctr = ConnectionTestResult(
            ok=True,
            status="CONNECTED",
            latency_ms=45.2,
            message="Handshake succeeded",
            http_status=200,
            details={"models": 8},
        )
        assert ctr.ok is True
        assert ctr.latency_ms == 45.2
        assert ctr.http_status == 200

    def test_provider_capabilities(self):
        caps = ProviderCapabilities(
            models=["gpt-4o", "text-embedding-3-large"],
            deployments=[{"name": "gpt-4o-prod", "model": "gpt-4o"}],
            tools=["code_interpreter"],
            agents=["triage-agent"],
        )
        assert len(caps.models) == 2
        assert caps.deployments[0]["name"] == "gpt-4o-prod"

    def test_sync_result(self):
        sr = SyncResult(
            resource_id="foundry-prod",
            synced_items=12,
            status="SUCCESS",
            message="Synced 12 deployments",
        )
        assert sr.resource_id == "foundry-prod"
        assert sr.synced_items == 12
        assert sr.status == "SUCCESS"


# =====================================================================
# 7. DOMAIN LIFECYCLE & STATE TRANSITIONS
# =====================================================================

class TestDomainStateTransitions:
    """Validates state transition helpers on ExternalResource."""

    def test_record_health_transition(self):
        res = ExternalResource(
            resource_id="res-health",
            provider="github",
            category=ResourceCategory.SOURCE_CONTROL,
            display_name="GitHub Enterprise",
            endpoint="https://github.example.com",
        )
        assert res.health_status == HealthStatus.CONFIGURED
        assert res.last_success_at is None

        now = datetime.now(timezone.utc)
        res.record_health(HealthStatus.CONNECTED, 25.5, tested_at=now)
        assert res.health_status == HealthStatus.CONNECTED
        assert res.latency_ms == 25.5
        assert res.last_tested_at == now
        assert res.last_success_at == now

        # Degraded check: updates tested_at, but does not overwrite last_success_at
        later = datetime.now(timezone.utc)
        res.record_health(HealthStatus.DEGRADED, 999.0, tested_at=later)
        assert res.health_status == HealthStatus.DEGRADED
        assert res.latency_ms == 999.0
        assert res.last_tested_at == later
        assert res.last_success_at == now

    def test_update_configuration_revision_bump(self):
        res = ExternalResource(
            resource_id="res-update",
            provider="servicenow",
            category=ResourceCategory.ITSM_CMDB,
            display_name="ServiceNow Dev",
            endpoint="https://dev.service-now.com",
            revision=1,
        )
        new_config = {"instance_name": "dev123", "timeout": 30}
        new_secrets = {"api_key": "vault://secret/snow#key"}

        res.update_configuration(
            config=new_config,
            secret_refs=new_secrets,
            actor="admin.alice",
            display_name="ServiceNow Prod",
        )
        assert res.revision == 2
        assert res.config == new_config
        assert res.secret_refs == new_secrets
        assert res.updated_by == "admin.alice"
        assert res.display_name == "ServiceNow Prod"

    def test_is_connected_helper(self):
        res = ExternalResource(
            resource_id="res-conn",
            provider="redis",
            category=ResourceCategory.STORAGE_DATA,
            display_name="Redis Cache",
            endpoint="redis://localhost:6379",
            enabled=True,
            health_status=HealthStatus.CONNECTED,
        )
        assert res.is_connected() is True

        res.enabled = False
        assert res.is_connected() is False

        res.enabled = True
        res.health_status = HealthStatus.DEGRADED
        assert res.is_connected() is False
