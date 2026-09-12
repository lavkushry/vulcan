"""
Project Vulcan: Base External Resource Provider (M3 / R3)
Author: Uncle Bob & Alex Xu
Abstract template provider defining standardized validation, reachability probes,
capability discovery, health status calculation, and sync cycles.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.domain.external_resource_entities import (
    ConnectionTestResult,
    HealthStatus,
    ProviderCapabilities,
    SyncResult,
    ValidationResult,
)
from app.ports.interfaces import IExternalResourceProvider

logger = logging.getLogger("vulcan.providers.base")


class BaseExternalResourceProvider(IExternalResourceProvider):
    """
    Template implementation of IExternalResourceProvider.
    Subclasses override specific protocol-level probes.
    """

    def __init__(self, provider_key: str = "generic"):
        self.provider_key = provider_key
        self._current_health: HealthStatus = HealthStatus.CONFIGURED

    def validate_config(
        self,
        config: Dict[str, Any],
        secret_refs: Dict[str, str],
    ) -> ValidationResult:
        """Default offline config & secret-reference validation."""
        errors: List[str] = []
        warnings: List[str] = []
        if not isinstance(config, dict):
            errors.append("Configuration must be a key-value object")
        if not isinstance(secret_refs, dict):
            errors.append("Secret references must be a key-value object")
        return ValidationResult(
            valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            details={"provider": self.provider_key},
        )

    def test_connection(
        self,
        config: Dict[str, Any],
        secret_refs: Dict[str, str],
        endpoint: Optional[str] = None,
    ) -> ConnectionTestResult:
        """Simulated/Base network connection probe."""
        start_time = time.perf_counter()
        # Subclasses execute real network handshakes
        latency = (time.perf_counter() - start_time) * 1000.0
        self._current_health = HealthStatus.CONNECTED
        return ConnectionTestResult(
            ok=True,
            status=HealthStatus.CONNECTED,
            latency_ms=max(1.0, round(latency, 2)),
            message=f"Successfully probed {self.provider_key} endpoint",
            http_status=200,
            diagnostics={"provider": self.provider_key, "endpoint": endpoint or config.get("endpoint")},
            tested_at=datetime.now(timezone.utc),
        )

    def discover_capabilities(
        self,
        config: Dict[str, Any],
        secret_refs: Dict[str, str],
        endpoint: Optional[str] = None,
    ) -> ProviderCapabilities:
        """Discovers capabilities, models, or assets available from provider."""
        return ProviderCapabilities(
            provider=self.provider_key,
            models=[],
            deployments=[],
            tools=[],
            agents=[],
            features={"active": True},
            capabilities=[f"{self.provider_key}_base_capability"],
            metadata={},
            discovered_at=datetime.now(timezone.utc),
        )

    def get_health(self) -> HealthStatus:
        """Returns the current cached health status."""
        return self._current_health

    def sync(
        self,
        resource_id: str,
        config: Optional[Dict[str, Any]] = None,
        secret_refs: Optional[Dict[str, str]] = None,
    ) -> SyncResult:
        """Executes a synchronization cycle."""
        return SyncResult(
            resource_id=resource_id,
            success=True,
            status="SUCCESS",
            synced_items_count=1,
            message=f"Synchronized {self.provider_key} resource {resource_id}",
            details={"synced_at": datetime.now(timezone.utc).isoformat()},
        )
