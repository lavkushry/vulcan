"""
Project Vulcan: External Resource Domain Entities & Value Objects (M1 / R1)
Pure Python 3.10+. Zero external framework dependencies (standard library only).
Enforces Zero-Raw-Secrets Invariant and Clean Architecture boundaries.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Union

from app.domain.exceptions import ParameterValidationError, SecretLintError


# =====================================================================
# DOMAIN ENUMS
# =====================================================================

class ResourceCategory(str, enum.Enum):
    """Categorized external systems and provider domains."""
    AI_MODELS = "AI & Models"
    ITSM_CMDB = "ITSM & CMDB"
    SECRETS_PAM = "Secrets & PAM"
    SOURCE_CONTROL = "Source Control"
    EXECUTION = "Execution"
    OBSERVABILITY = "Observability"
    STORAGE_DATA = "Storage & Data"

    @classmethod
    def from_string(cls, val: str) -> ResourceCategory:
        """Resilient parser accommodating legacy connector aliases."""
        if not val or not isinstance(val, str):
            raise ParameterValidationError(f"Invalid category: {val}")

        normalized = val.strip()
        # Direct value or name lookup
        for member in cls:
            if member.value.lower() == normalized.lower() or member.name.lower() == normalized.lower():
                return member

        # Legacy alias map
        alias_map = {
            "gitops & source control": cls.SOURCE_CONTROL,
            "source control": cls.SOURCE_CONTROL,
            "gitops": cls.SOURCE_CONTROL,
            "change management": cls.ITSM_CMDB,
            "itsm": cls.ITSM_CMDB,
            "cmdb": cls.ITSM_CMDB,
            "secrets & pam": cls.SECRETS_PAM,
            "secrets management": cls.SECRETS_PAM,
            "pam": cls.SECRETS_PAM,
            "execution engine": cls.EXECUTION,
            "execution": cls.EXECUTION,
            "observability": cls.OBSERVABILITY,
            "monitoring": cls.OBSERVABILITY,
            "storage & data": cls.STORAGE_DATA,
            "database": cls.STORAGE_DATA,
            "ai & models": cls.AI_MODELS,
            "ai": cls.AI_MODELS,
            "models": cls.AI_MODELS,
        }
        mapped = alias_map.get(normalized.lower())
        if mapped:
            return mapped

        raise ParameterValidationError(
            f"Invalid ResourceCategory '{val}'. Must be one of: {[m.value for m in cls]}"
        )


class AuthMode(str, enum.Enum):
    """Supported authentication strategies across external providers."""
    ENTRA_SERVICE_PRINCIPAL = "ENTRA_SERVICE_PRINCIPAL"
    MANAGED_IDENTITY = "MANAGED_IDENTITY"
    API_KEY = "API_KEY"
    OAUTH2 = "OAUTH2"
    BASIC = "BASIC"
    MUTUAL_TLS = "MUTUAL_TLS"
    NONE = "NONE"

    @classmethod
    def from_string(cls, val: str) -> AuthMode:
        """Parses authentication mode string."""
        if not val or not isinstance(val, str):
            raise ParameterValidationError(f"Invalid auth_mode: {val}")
        normalized = val.strip().upper().replace(" ", "_").replace("-", "_")
        for member in cls:
            if member.name == normalized or member.value == normalized:
                return member
        # Alias map for legacy connector auth_types
        legacy_map = {
            "BASIC_AUTH": cls.BASIC,
            "BEARER_TOKEN": cls.API_KEY,
            "TOKEN": cls.API_KEY,
            "SERVICE_PRINCIPAL": cls.ENTRA_SERVICE_PRINCIPAL,
            "MTLS": cls.MUTUAL_TLS,
            "NO_AUTH": cls.NONE,
        }
        mapped = legacy_map.get(normalized)
        if mapped:
            return mapped
        raise ParameterValidationError(
            f"Invalid AuthMode '{val}'. Must be one of: {[m.value for m in cls]}"
        )


class HealthStatus(str, enum.Enum):
    """Telemetry and reachability state of the external resource."""
    CONFIGURED = "CONFIGURED"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    AUTH_FAILED = "AUTH_FAILED"
    DISABLED = "DISABLED"

    @classmethod
    def from_string(cls, val: str) -> HealthStatus:
        if not val or not isinstance(val, str):
            raise ParameterValidationError(f"Invalid health_status: {val}")
        normalized = val.strip().upper()
        for member in cls:
            if member.name == normalized or member.value == normalized:
                return member
        # Alias map
        alias_map = {
            "UNREACHABLE": cls.DEGRADED,
            "UNKNOWN": cls.CONFIGURED,
        }
        mapped = alias_map.get(normalized)
        if mapped:
            return mapped
        raise ParameterValidationError(
            f"Invalid HealthStatus '{val}'. Must be one of: {[m.value for m in cls]}"
        )


class ResourceEnvironment(str, enum.Enum):
    """Deployment tier boundary for the target resource."""
    PROD = "PROD"
    STAGE = "STAGE"
    DEV = "DEV"

    @classmethod
    def from_string(cls, val: str) -> ResourceEnvironment:
        if not val or not isinstance(val, str):
            raise ParameterValidationError(f"Invalid environment: {val}")
        normalized = val.strip().upper()
        for member in cls:
            if member.name == normalized or member.value == normalized:
                return member
        raise ParameterValidationError(
            f"Invalid ResourceEnvironment '{val}'. Must be one of: {[m.value for m in cls]}"
        )


# =====================================================================
# VALUE OBJECTS
# =====================================================================

@dataclass
class ValidationResult:
    """Outcome of provider configuration and secret-reference schema validation."""
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    is_valid: Optional[bool] = None

    def __post_init__(self):
        if self.is_valid is not None:
            self.valid = bool(self.is_valid)
        else:
            self.is_valid = bool(self.valid)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "is_valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "details": copy.deepcopy(self.details),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationResult:
        valid_val = data.get("valid")
        if valid_val is None:
            valid_val = data.get("is_valid", False)
        return cls(
            valid=bool(valid_val),
            errors=list(data.get("errors", [])),
            warnings=list(data.get("warnings", [])),
            details=dict(data.get("details", {})),
        )


@dataclass
class ConnectionTestResult:
    """Outcome of live reachability, TLS handshake, and authentication probe."""
    ok: bool = True
    status: Union[HealthStatus, str] = HealthStatus.CONFIGURED
    latency_ms: float = 0.0
    message: str = ""
    http_status: Optional[int] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    tested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success: Optional[bool] = None
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.success is not None:
            self.ok = bool(self.success)
        else:
            self.success = bool(self.ok)

        if self.details is not None:
            self.diagnostics = self.details
        else:
            self.details = self.diagnostics

        if isinstance(self.status, str):
            try:
                self.status = HealthStatus.from_string(self.status)
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        return bool(self.ok)

    def to_dict(self) -> Dict[str, Any]:
        status_val = self.status.value if isinstance(self.status, HealthStatus) else str(self.status)
        return {
            "ok": self.ok,
            "success": self.ok,
            "status": status_val,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "http_status": self.http_status,
            "diagnostics": copy.deepcopy(self.diagnostics),
            "details": copy.deepcopy(self.diagnostics),
            "tested_at": self.tested_at.isoformat() if isinstance(self.tested_at, datetime) else str(self.tested_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConnectionTestResult:
        raw_status = data.get("status", HealthStatus.CONFIGURED)
        status = HealthStatus.from_string(raw_status) if isinstance(raw_status, str) else raw_status
        raw_tested_at = data.get("tested_at")
        if isinstance(raw_tested_at, str):
            try:
                tested_at = datetime.fromisoformat(raw_tested_at)
            except Exception:
                tested_at = datetime.now(timezone.utc)
        elif isinstance(raw_tested_at, datetime):
            tested_at = raw_tested_at
        else:
            tested_at = datetime.now(timezone.utc)

        ok_val = data.get("ok")
        if ok_val is None:
            ok_val = data.get("success", False)

        diagnostics = dict(data.get("diagnostics") or data.get("details") or {})

        return cls(
            ok=bool(ok_val),
            status=status,
            latency_ms=float(data.get("latency_ms", 0.0)),
            message=str(data.get("message", "")),
            http_status=data.get("http_status"),
            diagnostics=diagnostics,
            tested_at=tested_at,
        )


@dataclass
class ProviderCapabilities:
    """Capabilities discovered dynamically from the external provider."""
    provider: str = ""
    models: List[Any] = field(default_factory=list)
    deployments: List[Dict[str, Any]] = field(default_factory=list)
    tools: List[Any] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    features: Dict[str, bool] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "models": list(self.models),
            "deployments": copy.deepcopy(self.deployments),
            "tools": list(self.tools),
            "agents": list(self.agents),
            "features": dict(self.features),
            "capabilities": list(self.capabilities),
            "metadata": copy.deepcopy(self.metadata),
            "discovered_at": self.discovered_at.isoformat() if isinstance(self.discovered_at, datetime) else str(self.discovered_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProviderCapabilities:
        raw_disc_at = data.get("discovered_at")
        if isinstance(raw_disc_at, str):
            try:
                disc_at = datetime.fromisoformat(raw_disc_at)
            except Exception:
                disc_at = datetime.now(timezone.utc)
        elif isinstance(raw_disc_at, datetime):
            disc_at = raw_disc_at
        else:
            disc_at = datetime.now(timezone.utc)

        return cls(
            provider=str(data.get("provider", "")),
            models=list(data.get("models", [])),
            deployments=list(data.get("deployments", [])),
            tools=list(data.get("tools", [])),
            agents=list(data.get("agents", [])),
            features=dict(data.get("features", {})),
            capabilities=list(data.get("capabilities", [])),
            metadata=dict(data.get("metadata", {})),
            discovered_at=disc_at,
        )


@dataclass
class SyncResult:
    """Outcome of an external catalog, deployment, or configuration sync."""
    resource_id: str = ""
    success: bool = True
    status: str = "SUCCESS"
    synced_items_count: int = 0
    synced_items: Optional[int] = None
    message: str = ""
    errors: List[str] = field(default_factory=list)
    synced_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.synced_items is not None:
            self.synced_items_count = int(self.synced_items)
        else:
            self.synced_items = int(self.synced_items_count)

        if not self.success and self.status == "SUCCESS":
            self.status = "FAILED"
        elif self.status != "SUCCESS" and self.success:
            if self.status.upper() in ("FAILED", "ERROR"):
                self.success = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "success": self.success,
            "status": self.status,
            "synced_items_count": self.synced_items_count,
            "synced_items": self.synced_items_count,
            "message": self.message,
            "errors": list(self.errors),
            "synced_at": self.synced_at.isoformat() if isinstance(self.synced_at, datetime) else str(self.synced_at),
            "details": copy.deepcopy(self.details),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SyncResult:
        raw_synced_at = data.get("synced_at")
        if isinstance(raw_synced_at, str):
            try:
                synced_at = datetime.fromisoformat(raw_synced_at)
            except Exception:
                synced_at = datetime.now(timezone.utc)
        elif isinstance(raw_synced_at, datetime):
            synced_at = raw_synced_at
        else:
            synced_at = datetime.now(timezone.utc)

        success_val = data.get("success")
        status_val = str(data.get("status", "SUCCESS"))
        if success_val is None:
            success_val = (status_val.upper() in ("SUCCESS", "OK"))

        count_val = data.get("synced_items_count")
        if count_val is None:
            count_val = data.get("synced_items", 0)

        return cls(
            resource_id=str(data.get("resource_id", "")),
            success=bool(success_val),
            status=status_val,
            synced_items_count=int(count_val),
            synced_items=int(count_val),
            message=str(data.get("message", "")),
            errors=list(data.get("errors", [])),
            synced_at=synced_at,
            details=dict(data.get("details", {})),
        )


# =====================================================================
# ZERO-RAW-SECRETS VALIDATION HELPERS
# =====================================================================

ALLOWED_SECRET_REF_SCHEMES = ("cyberark://", "vault://", "env://")
SECRET_URI_REGEX = re.compile(r"^(cyberark|vault|env)://[a-zA-Z0-9_\-\./#:@?=]+$")

SECRET_LINT_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
    re.compile(r"(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}"),
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
]

SENSITIVE_KEY_REGEX = re.compile(
    r"(?i)^(password|secret|client_secret|api_key|auth_token|access_token|private_key)$"
)


def validate_secret_refs(secret_refs: Dict[str, str]) -> None:
    """Enforces that all secret_refs match authorized vault pointer schemes."""
    if not isinstance(secret_refs, dict):
        raise ParameterValidationError("secret_refs must be a dictionary")

    for key, val in secret_refs.items():
        if not isinstance(val, str):
            raise SecretLintError(
                f"Security Invariant Triggered: Secret reference value for '{key}' must be a string URI pointer."
            )
        val_clean = val.strip()
        if not any(val_clean.startswith(prefix) for prefix in ALLOWED_SECRET_REF_SCHEMES):
            raise SecretLintError(
                f"Security Invariant Triggered: Secret reference for '{key}' has invalid scheme. "
                f"Value '{val}' must start with one of: {ALLOWED_SECRET_REF_SCHEMES}"
            )
        if not SECRET_URI_REGEX.match(val_clean):
            raise SecretLintError(
                f"Security Invariant Triggered: Secret reference for '{key}' failed URI pointer syntax check: '{val}'"
            )


def lint_config_secrets(config: Dict[str, Any], path: str = "") -> None:
    """Recursively audits config dictionary to guarantee zero raw credentials are present."""
    if not isinstance(config, dict):
        raise ParameterValidationError("config must be a dictionary")

    for k, v in config.items():
        current_path = f"{path}.{k}" if path else k

        # Check for forbidden sensitive credential keys
        if SENSITIVE_KEY_REGEX.match(k):
            if isinstance(v, str) and v.strip():
                # Allow only if it is explicitly an allowed URI pointer or empty placeholder
                if not any(v.strip().startswith(prefix) for prefix in ALLOWED_SECRET_REF_SCHEMES):
                    raise SecretLintError(
                        f"Security Invariant Triggered: Raw credential key '{current_path}' detected in config. "
                        f"Plaintext secrets are forbidden in config; reference credentials via secret_refs "
                        f"using cyberark://, vault://, or env:// pointers."
                    )

        # Value inspection
        if isinstance(v, str):
            for pat in SECRET_LINT_PATTERNS:
                if pat.search(v):
                    raise SecretLintError(
                        f"Security Invariant Triggered: High-entropy secret pattern detected in config at '{current_path}'."
                    )
        elif isinstance(v, dict):
            lint_config_secrets(v, current_path)
        elif isinstance(v, list):
            for idx, item in enumerate(v):
                item_path = f"{current_path}[{idx}]"
                if isinstance(item, str):
                    for pat in SECRET_LINT_PATTERNS:
                        if pat.search(item):
                            raise SecretLintError(
                                f"Security Invariant Triggered: High-entropy secret pattern detected in config at '{item_path}'."
                            )
                elif isinstance(item, dict):
                    lint_config_secrets(item, item_path)


# =====================================================================
# CORE AGGREGATE ENTITY
# =====================================================================

@dataclass
class ExternalResource:
    """
    Core Domain Aggregate Root representing an external system, API, or AI provider.
    Zero framework dependencies. Enforces Zero-Raw-Secrets Invariant.
    """
    resource_id: str
    provider: str
    category: ResourceCategory
    display_name: str
    endpoint: str
    environment: ResourceEnvironment = ResourceEnvironment.PROD
    auth_mode: AuthMode = AuthMode.API_KEY
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    secret_refs: Dict[str, str] = field(default_factory=dict)
    health_status: HealthStatus = HealthStatus.CONFIGURED
    latency_ms: float = 0.0
    last_tested_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    created_by: str = "system"
    updated_by: str = "system"
    revision: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        # 1. Resource ID validation
        if not self.resource_id or not isinstance(self.resource_id, str):
            raise ParameterValidationError("resource_id must be a non-empty string")
        if not re.match(r"^[a-zA-Z0-9_\-\.:]+$", self.resource_id):
            raise ParameterValidationError(
                f"resource_id '{self.resource_id}' contains invalid characters (alphanumeric, -, _, ., : only)"
            )

        # 2. Provider validation
        if not self.provider or not isinstance(self.provider, str):
            raise ParameterValidationError("provider must be a non-empty string")

        # 3. Enum normalization & type coercion
        if isinstance(self.category, str):
            self.category = ResourceCategory.from_string(self.category)
        elif not isinstance(self.category, ResourceCategory):
            raise ParameterValidationError(f"Invalid category type: {type(self.category)}")

        if isinstance(self.environment, str):
            self.environment = ResourceEnvironment.from_string(self.environment)
        elif not isinstance(self.environment, ResourceEnvironment):
            raise ParameterValidationError(f"Invalid environment type: {type(self.environment)}")

        if isinstance(self.auth_mode, str):
            self.auth_mode = AuthMode.from_string(self.auth_mode)
        elif not isinstance(self.auth_mode, AuthMode):
            raise ParameterValidationError(f"Invalid auth_mode type: {type(self.auth_mode)}")

        if isinstance(self.health_status, str):
            self.health_status = HealthStatus.from_string(self.health_status)
        elif not isinstance(self.health_status, HealthStatus):
            raise ParameterValidationError(f"Invalid health_status type: {type(self.health_status)}")

        # 4. Numerics and bounds checks
        if self.revision < 1:
            raise ParameterValidationError(f"revision must be >= 1, got {self.revision}")
        if self.latency_ms < 0:
            raise ParameterValidationError(f"latency_ms cannot be negative, got {self.latency_ms}")

        # 5. Zero-Raw-Secrets Invariant Enforcement
        validate_secret_refs(self.secret_refs)
        lint_config_secrets(self.config)

    # -----------------------------------------------------------------
    # SERIALIZATION & MASKING
    # -----------------------------------------------------------------

    def to_dict(self, mask_secrets: bool = True, is_admin: bool = False) -> Dict[str, Any]:
        """
        Serializes ExternalResource to dictionary.
        Enforces secret reference masking: masks secret refs as '********' for non-admin.
        Admin users (is_admin=True) or explicit unmasked (mask_secrets=False) receive raw URI pointers.
        """
        if mask_secrets and not is_admin:
            masked_refs = {k: "********" for k in self.secret_refs}
        else:
            masked_refs = copy.deepcopy(self.secret_refs)

        return {
            "resource_id": self.resource_id,
            "provider": self.provider,
            "category": self.category.value,
            "display_name": self.display_name,
            "environment": self.environment.value,
            "endpoint": self.endpoint,
            "auth_mode": self.auth_mode.value,
            "enabled": self.enabled,
            "config": copy.deepcopy(self.config),
            "secret_refs": masked_refs,
            "health_status": self.health_status.value,
            "latency_ms": self.latency_ms,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "revision": self.revision,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else str(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExternalResource:
        """Constructs and validates an ExternalResource from dictionary."""
        def _parse_dt(val: Any) -> Optional[datetime]:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val)
                except Exception:
                    return None
            return None

        created_at = _parse_dt(data.get("created_at")) or datetime.now(timezone.utc)
        updated_at = _parse_dt(data.get("updated_at")) or datetime.now(timezone.utc)
        last_tested_at = _parse_dt(data.get("last_tested_at"))
        last_success_at = _parse_dt(data.get("last_success_at"))

        return cls(
            resource_id=str(data.get("resource_id", "")),
            provider=str(data.get("provider", "")),
            category=ResourceCategory.from_string(data.get("category", ResourceCategory.AI_MODELS.value)),
            display_name=str(data.get("display_name", "")),
            endpoint=str(data.get("endpoint", "")),
            environment=ResourceEnvironment.from_string(data.get("environment", ResourceEnvironment.PROD.value)),
            auth_mode=AuthMode.from_string(data.get("auth_mode", AuthMode.API_KEY.value)),
            enabled=bool(data.get("enabled", True)),
            config=dict(data.get("config") or {}),
            secret_refs=dict(data.get("secret_refs") or {}),
            health_status=HealthStatus.from_string(data.get("health_status", HealthStatus.CONFIGURED.value)),
            latency_ms=float(data.get("latency_ms", 0.0)),
            last_tested_at=last_tested_at,
            last_success_at=last_success_at,
            created_by=str(data.get("created_by", "system")),
            updated_by=str(data.get("updated_by", "system")),
            revision=int(data.get("revision", 1)),
            created_at=created_at,
            updated_at=updated_at,
        )

    # -----------------------------------------------------------------
    # DOMAIN LIFECYCLE & STATE TRANSITIONS
    # -----------------------------------------------------------------

    def record_health(self, status: HealthStatus, latency_ms: float, tested_at: Optional[datetime] = None) -> None:
        """Updates health status and records latency telemetry."""
        now = tested_at or datetime.now(timezone.utc)
        if isinstance(status, str):
            status = HealthStatus.from_string(status)
        self.health_status = status
        self.latency_ms = max(0.0, float(latency_ms))
        self.last_tested_at = now
        if status == HealthStatus.CONNECTED:
            self.last_success_at = now
        self.updated_at = now

    def update_configuration(
        self,
        config: Dict[str, Any],
        secret_refs: Optional[Dict[str, str]] = None,
        actor: str = "system",
        endpoint: Optional[str] = None,
        display_name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Mutates configuration, bumps revision, and validates zero raw secrets."""
        lint_config_secrets(config)
        if secret_refs is not None:
            validate_secret_refs(secret_refs)
            self.secret_refs = dict(secret_refs)

        self.config = dict(config)
        if endpoint is not None:
            self.endpoint = endpoint
        if display_name is not None:
            self.display_name = display_name
        if enabled is not None:
            self.enabled = enabled

        self.revision += 1
        self.updated_by = actor
        self.updated_at = datetime.now(timezone.utc)

    def is_connected(self) -> bool:
        """Returns True if resource is enabled and actively connected."""
        return self.enabled and self.health_status == HealthStatus.CONNECTED


# =====================================================================
# SUPPORTING REPOSITORY & AUDIT ENTITIES
# =====================================================================

@dataclass(frozen=True)
class ExternalResourceVersion:
    """Historical snapshot tracking configuration changes and authorship."""
    id: Optional[int]
    resource_id: str
    revision: int
    snapshot: Dict[str, Any]
    actor: str
    reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "revision": self.revision,
            "snapshot": copy.deepcopy(self.snapshot),
            "actor": self.actor,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
        }


@dataclass(frozen=True)
class ExternalResourceHealth:
    """Time-series health check telemetry record."""
    resource_id: str
    status: HealthStatus
    latency_ms: float
    id: Optional[int] = None
    http_status: Optional[int] = None
    message: str = ""
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if isinstance(self.status, str):
            object.__setattr__(self, "status", HealthStatus.from_string(self.status))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "status": self.status.value if isinstance(self.status, HealthStatus) else str(self.status),
            "latency_ms": self.latency_ms,
            "http_status": self.http_status,
            "message": self.message,
            "diagnostics": copy.deepcopy(self.diagnostics),
            "checked_at": self.checked_at.isoformat() if isinstance(self.checked_at, datetime) else str(self.checked_at),
        }


@dataclass(frozen=True)
class ExternalResourceAuditRecord:
    """Merkle-compatible tamper-evident ledger audit record."""
    resource_id: str
    timestamp: str
    actor: str
    action: str  # "CREATE", "UPDATE", "DELETE", "TEST", "SYNC"
    payload: Dict[str, Any]
    prev_hash: str
    current_hash: str
    id: Optional[int] = None

    @staticmethod
    def compute_hash(
        resource_id: str,
        timestamp: str,
        actor: str,
        action: str,
        payload: Dict[str, Any],
        prev_hash: str,
    ) -> str:
        """Calculates deterministic SHA-256 Merkle hash."""
        data = {
            "resource_id": resource_id,
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "action": self.action,
            "actor": self.actor,
            "payload": copy.deepcopy(self.payload),
            "prev_hash": self.prev_hash,
            "current_hash": self.current_hash,
            "timestamp": self.timestamp,
        }
