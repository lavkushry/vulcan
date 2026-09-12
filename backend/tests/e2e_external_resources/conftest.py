"""
Project Vulcan: E2E External Resources & Microsoft Foundry Test Fixtures.
Provides hermetic test tokens, role-specific HTTP clients, mock endpoints, and dynamic loaders.
"""

import os
import json
import pytest
from typing import Dict, Any, Generator
from fastapi.testclient import TestClient

# Hermetic Test Token Configuration
E2E_TOKENS = {
    "vlc_test_admin": "admin.dave",       # PLATFORM_ADMIN (full mutation permissions)
    "vlc_test_alice": "eng.alice",         # OPERATOR (read-only / forbidden from mutation)
    "vlc_test_auditor": "audit.emma",      # AUDITOR (read-only / forbidden from mutation)
    "vlc_test_bob": "lead.bob",            # APPROVING_LEAD
    "vlc_test_sec": "sec.carol",           # SECURITY_ADMIN
}

# Ensure tokens are registered in VULCAN_API_TOKENS env var
existing_raw = os.environ.get("VULCAN_API_TOKENS", "{}")
try:
    existing_tokens = json.loads(existing_raw)
except Exception:
    existing_tokens = {}
existing_tokens.update(E2E_TOKENS)
os.environ["VULCAN_API_TOKENS"] = json.dumps(existing_tokens)
os.environ["VULCAN_AUTH_DISABLED"] = "0"


def get_domain_module():
    """Lazily load domain entities or skip test if not yet implemented."""
    try:
        from app.domain import external_resource_entities
        return external_resource_entities
    except ImportError:
        pytest.skip("External resources domain module app.domain.external_resource_entities not implemented yet")


def get_repository_class():
    """Lazily load repository class or skip test if not yet implemented."""
    try:
        from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository
        return PostgresExternalResourceRepository
    except ImportError:
        pytest.skip("PostgresExternalResourceRepository not implemented yet")


def get_foundry_provider_class():
    """Lazily load MicrosoftFoundryProvider or skip test if not yet implemented."""
    try:
        from app.adapters.providers.microsoft_foundry_provider import MicrosoftFoundryProvider
        return MicrosoftFoundryProvider
    except ImportError:
        pytest.skip("MicrosoftFoundryProvider not implemented yet")


def get_provider_registry():
    """Lazily load ProviderRegistry or skip test if not yet implemented."""
    try:
        from app.adapters.providers.provider_registry import ProviderRegistry
        return ProviderRegistry
    except ImportError:
        pytest.skip("ProviderRegistry not implemented yet")


@pytest.fixture(scope="session")
def test_tokens() -> Dict[str, str]:
    return dict(E2E_TOKENS)


@pytest.fixture
def test_app():
    """Provides the FastAPI application instance."""
    from app.api.server import create_app
    return create_app()


@pytest.fixture
def admin_client(test_app) -> Generator[TestClient, None, None]:
    """TestClient authenticated as PLATFORM_ADMIN (admin.dave)."""
    client = TestClient(test_app, headers={"Authorization": "Bearer vlc_test_admin"})
    yield client


@pytest.fixture
def operator_client(test_app) -> Generator[TestClient, None, None]:
    """TestClient authenticated as OPERATOR (eng.alice)."""
    client = TestClient(test_app, headers={"Authorization": "Bearer vlc_test_alice"})
    yield client


@pytest.fixture
def auditor_client(test_app) -> Generator[TestClient, None, None]:
    """TestClient authenticated as AUDITOR (audit.emma)."""
    client = TestClient(test_app, headers={"Authorization": "Bearer vlc_test_auditor"})
    yield client


@pytest.fixture
def anonymous_client(test_app) -> Generator[TestClient, None, None]:
    """TestClient with no authentication headers."""
    client = TestClient(test_app)
    yield client


@pytest.fixture
def mock_foundry_deployments_data() -> Dict[str, Any]:
    """Standard dynamic deployment response payload from Microsoft Foundry."""
    return {
        "value": [
            {
                "name": "gpt-4o",
                "model": "gpt-4o",
                "version": "2024-05-13",
                "type": "chat",
                "status": "Running",
                "properties": {
                    "capabilities": ["chat", "vision", "function_calling"]
                }
            },
            {
                "name": "gpt-4o-mini",
                "model": "gpt-4o-mini",
                "version": "2024-07-18",
                "type": "chat",
                "status": "Running",
                "properties": {
                    "capabilities": ["chat", "function_calling"]
                }
            },
            {
                "name": "text-embedding-3-small",
                "model": "text-embedding-3-small",
                "version": "1",
                "type": "embeddings",
                "status": "Running",
                "properties": {
                    "dimensions": 1536
                }
            },
            {
                "name": "phi-3-mini",
                "model": "phi-3-mini-128k-instruct",
                "version": "1",
                "type": "reasoning",
                "status": "Running",
                "properties": {
                    "capabilities": ["chat", "code_generation"]
                }
            }
        ]
    }
