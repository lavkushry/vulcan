"""
Project Vulcan: Provider Registry & Capability Factory (M3 / R3)
Author: Alex Xu & Uncle Bob
Provides centralized discovery, registration, and lifecycle resolution across
all 16 enterprise connectors and AI providers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.adapters.providers.base_provider import BaseExternalResourceProvider
from app.adapters.providers.concrete_providers import (
    AAPProvider,
    BitbucketProvider,
    CyberArkProvider,
    DatadogProvider,
    GeminiProvider,
    GitHubProvider,
    HuggingFaceProvider,
    MinIOProvider,
    OpenAIProvider,
    OpenRouterProvider,
    PostgresProvider,
    PrometheusProvider,
    RedisProvider,
    ServiceNowProvider,
    VaultProvider,
)
from app.adapters.providers.microsoft_foundry_provider import MicrosoftFoundryProvider
from app.ports.interfaces import IExternalResourceProvider

logger = logging.getLogger("vulcan.providers.registry")


class ProviderRegistry:
    """
    Centralized registry of IExternalResourceProvider instances.
    Supports both singleton class-level resolution and instance methods.
    """

    _instance: Optional[ProviderRegistry] = None

    def __init__(self):
        self._providers: Dict[str, IExternalResourceProvider] = {}
        self._register_default_providers()

    @classmethod
    def get_instance(cls) -> ProviderRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_default_providers(self) -> None:
        """Bootstraps all 16 enterprise connectors."""
        self._providers["microsoft_foundry"] = MicrosoftFoundryProvider()
        self._providers["servicenow"] = ServiceNowProvider()
        self._providers["cyberark"] = CyberArkProvider()
        self._providers["vault"] = VaultProvider()
        self._providers["github"] = GitHubProvider()
        self._providers["bitbucket"] = BitbucketProvider()
        self._providers["aap"] = AAPProvider()
        self._providers["datadog"] = DatadogProvider()
        self._providers["prometheus"] = PrometheusProvider()
        self._providers["postgres"] = PostgresProvider()
        self._providers["redis"] = RedisProvider()
        self._providers["minio"] = MinIOProvider()
        self._providers["openai"] = OpenAIProvider()
        self._providers["openrouter"] = OpenRouterProvider()
        self._providers["gemini"] = GeminiProvider()
        self._providers["huggingface"] = HuggingFaceProvider()

    @classmethod
    def get_provider(cls, key: str) -> Optional[IExternalResourceProvider]:
        """Resolves an external resource provider by key (class or instance)."""
        instance = cls.get_instance()
        if not key:
            return None
        return instance._providers.get(key.lower())

    @classmethod
    def register_provider(cls, key: str, provider: IExternalResourceProvider) -> None:
        """Registers a custom or updated provider."""
        instance = cls.get_instance()
        instance._providers[key.lower()] = provider

    @classmethod
    def list_registered_keys(cls) -> List[str]:
        """Returns all registered provider keys."""
        instance = cls.get_instance()
        return list(instance._providers.keys())

    @classmethod
    def list_providers(cls) -> List[Dict[str, Any]]:
        """Returns metadata descriptors for all registered providers."""
        descriptors = [
            {
                "key": "microsoft_foundry",
                "name": "Microsoft Foundry",
                "category": "AI & Models",
                "icon": "azure",
                "description": "Enterprise AI project deployments, Entra ID / Managed Identity auth, and model discovery.",
                "auth_modes": ["ENTRA_SERVICE_PRINCIPAL", "MANAGED_IDENTITY", "API_KEY"],
            },
            {
                "key": "servicenow",
                "name": "ServiceNow ITSM & CMDB",
                "category": "ITSM & CMDB",
                "icon": "shield",
                "description": "Change Request validation, maintenance windows, and CMDB CI synchronization.",
                "auth_modes": ["BASIC", "OAUTH2"],
            },
            {
                "key": "cyberark",
                "name": "CyberArk PAM CCP",
                "category": "Secrets & PAM",
                "icon": "lock",
                "description": "Central Credential Provider integration for zero-trust privileged account secrets.",
                "auth_modes": ["MUTUAL_TLS", "API_KEY"],
            },
            {
                "key": "vault",
                "name": "HashiCorp Vault",
                "category": "Secrets & PAM",
                "icon": "lock",
                "description": "Enterprise Vault secret storage and dynamic secret generation.",
                "auth_modes": ["API_KEY", "OAUTH2"],
            },
            {
                "key": "github",
                "name": "GitHub Enterprise",
                "category": "Source Control",
                "icon": "git",
                "description": "GitOps Single Source of Truth for playbooks and Terraform stacks.",
                "auth_modes": ["API_KEY", "OAUTH2"],
            },
            {
                "key": "bitbucket",
                "name": "Bitbucket Server",
                "category": "Source Control",
                "icon": "git",
                "description": "Enterprise Git repository management and commit verification.",
                "auth_modes": ["BASIC", "API_KEY"],
            },
            {
                "key": "aap",
                "name": "Red Hat AAP",
                "category": "Execution",
                "icon": "cpu",
                "description": "Ansible Automation Platform execution cluster dispatch.",
                "auth_modes": ["BASIC", "OAUTH2"],
            },
            {
                "key": "datadog",
                "name": "Datadog",
                "category": "Observability",
                "icon": "activity",
                "description": "Real-time metrics, telemetry, and distributed tracing.",
                "auth_modes": ["API_KEY"],
            },
            {
                "key": "prometheus",
                "name": "Prometheus",
                "category": "Observability",
                "icon": "activity",
                "description": "Time-series metrics and monitoring scrape target.",
                "auth_modes": ["NONE", "BASIC"],
            },
            {
                "key": "postgres",
                "name": "PostgreSQL 16",
                "category": "Storage & Data",
                "icon": "database",
                "description": "Relational control plane persistence and pgvector vector search.",
                "auth_modes": ["BASIC", "MUTUAL_TLS"],
            },
            {
                "key": "redis",
                "name": "Redis",
                "category": "Storage & Data",
                "icon": "database",
                "description": "Redlock distributed mutex and real-time event pub/sub backplane.",
                "auth_modes": ["BASIC", "NONE"],
            },
            {
                "key": "minio",
                "name": "MinIO / S3",
                "category": "Storage & Data",
                "icon": "cloud",
                "description": "10GB multipart binary artifact and execution logs storage.",
                "auth_modes": ["API_KEY"],
            },
            {
                "key": "openai",
                "name": "OpenAI",
                "category": "AI & Models",
                "icon": "cpu",
                "description": "Direct OpenAI chat completions and dense embeddings.",
                "auth_modes": ["API_KEY"],
            },
            {
                "key": "openrouter",
                "name": "OpenRouter",
                "category": "AI & Models",
                "icon": "cpu",
                "description": "Multi-provider AI routing gateway and fallbacks.",
                "auth_modes": ["API_KEY"],
            },
            {
                "key": "gemini",
                "name": "Google Gemini",
                "category": "AI & Models",
                "icon": "sparkles",
                "description": "Google Gemini multimodal reasoning and embeddings.",
                "auth_modes": ["API_KEY"],
            },
            {
                "key": "huggingface",
                "name": "Hugging Face",
                "category": "AI & Models",
                "icon": "smile",
                "description": "Open-source model hosting and specialized transformers.",
                "auth_modes": ["API_KEY"],
            },
        ]
        return descriptors
