"""
Project Vulcan: Core Domain Entities & Value Objects
Pure Python 3.10+. Zero external framework dependencies.
"""
from __future__ import annotations
import enum
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.domain.exceptions import (
    ApprovalTimeoutError,
    AuditIntegrityError,
    MakerCheckerViolationError,
    ParameterValidationError,
    SecretLintError,
    StateTransitionError,
)


class JobStatus(str, enum.Enum):
    """Deterministic finite state machine states for execution lifecycle."""
    SUBMITTED = "SUBMITTED"
    PARSED = "PARSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    TIMEOUT_DENIED = "TIMEOUT_DENIED"
    REJECTED = "REJECTED"
    QUEUED = "QUEUED"
    LOCKED = "LOCKED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    REVERTING = "REVERTING"
    REVERTED = "REVERTED"


class RiskTier(str, enum.Enum):
    """PNC Bank Risk Classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExecutionEngineType(str, enum.Enum):
    """Supported execution runtimes."""
    ANSIBLE = "ansible"
    TERRAFORM = "terraform"
    SCRIPT = "script"


@dataclass(frozen=True)
class CatalogItem:
    """
    Immutable catalog specification bound to a specific Git commit SHA.
    Enforces Git immutability to prevent drift or tampering.
    """
    id: str
    identifier: str
    name: str
    engine: ExecutionEngineType
    git_repo: str
    git_commit_sha: str
    playbook_or_module_path: str
    risk_tier: RiskTier
    requires_maker_checker: bool
    requires_chg: bool
    input_schema: Dict[str, Any]
    rollback_path: Optional[str] = None
    category: str = "general"
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not re.match(r"^[0-9a-f]{40}$", self.git_commit_sha):
            raise ParameterValidationError(
                f"CatalogItem [{self.identifier}] must bind to a 40-character Git commit SHA."
            )


@dataclass(frozen=True)
class ApprovalDecision:
    """Immutable audit record of a human Maker-Checker sign-off."""
    decision: str  # "APPROVE" | "REJECT"
    approver_id: str
    decided_at: datetime
    reason: str
    chg_number: Optional[str] = None
    approval_token: Optional[str] = None


@dataclass(frozen=True)
class AuditRecord:
    """
    Cryptographically chained immutable ledger record.
    Hash_n = SHA256(Record_n + Hash_{n-1})
    """
    id: int
    correlation_id: str
    timestamp: str
    actor: str
    action: str
    payload: Dict[str, Any]
    prev_hash: str
    current_hash: str

    @staticmethod
    def compute_hash(
        correlation_id: str,
        timestamp: str,
        actor: str,
        action: str,
        payload: Dict[str, Any],
        prev_hash: str
    ) -> str:
        data = {
            "correlation_id": correlation_id,
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "payload": payload,
            "prev_hash": prev_hash
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EphemeralSecretLease:
    """In-memory JIT credentials checked out from PAM into RAM."""
    lease_id: str
    secrets: Dict[str, str]
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class EngineExecutionResult:
    """Outcome returned from an execution engine adapter."""
    status: str
    exit_code: int
    stdout: str
    diagnostics: Optional[str] = None


@dataclass(frozen=True)
class HealthCheckResult:
    """Synthetic post-flight probe verification metrics."""
    is_healthy: bool
    latency_ms: float
    error_rate: float
    details: Dict[str, Any]


class ExecutionJob:
    """
    Core Aggregate Root managing execution state and enforcing banking invariants.
    Zero external framework dependencies. Pure deterministic logic.
    """

    # Legal transitions matrix
    _TRANSITIONS: Dict[JobStatus, List[JobStatus]] = {
        JobStatus.SUBMITTED: [JobStatus.PARSED, JobStatus.FAILED],
        JobStatus.PARSED: [JobStatus.PENDING_APPROVAL, JobStatus.QUEUED, JobStatus.FAILED],
        JobStatus.PENDING_APPROVAL: [JobStatus.QUEUED, JobStatus.REJECTED, JobStatus.TIMEOUT_DENIED, JobStatus.FAILED],
        JobStatus.QUEUED: [JobStatus.LOCKED, JobStatus.FAILED],
        JobStatus.LOCKED: [JobStatus.RUNNING, JobStatus.FAILED],
        JobStatus.RUNNING: [JobStatus.VERIFYING, JobStatus.FAILED],
        JobStatus.VERIFYING: [JobStatus.SUCCESS, JobStatus.DEGRADED, JobStatus.FAILED],
        JobStatus.DEGRADED: [JobStatus.REVERTING, JobStatus.FAILED],
        JobStatus.REVERTING: [JobStatus.REVERTED, JobStatus.FAILED],
        JobStatus.SUCCESS: [],
        JobStatus.FAILED: [],
        JobStatus.TIMEOUT_DENIED: [],
        JobStatus.REJECTED: [],
        JobStatus.REVERTED: []
    }

    def __init__(
        self,
        job_id: str,
        correlation_id: str,
        catalog_item: CatalogItem,
        requester_id: str,
        target_resource_id: str,
        parameters: Dict[str, Any],
        servicenow_chg: Optional[str] = None,
        storage_artifact_uri: Optional[str] = None,
        storage_artifact_sha256: Optional[str] = None,
        environment: str = "PROD"
    ):
        self.id = job_id
        self.correlation_id = correlation_id
        self.catalog_item = catalog_item
        self.requester_id = requester_id
        self.target_resource_id = target_resource_id
        self.parameters = parameters
        self.servicenow_chg = servicenow_chg
        self.storage_artifact_uri = storage_artifact_uri
        self.storage_artifact_sha256 = storage_artifact_sha256
        self.environment = environment

        self.status = JobStatus.SUBMITTED
        self.approver_id: Optional[str] = None
        self.approval_decision: Optional[ApprovalDecision] = None
        self.approval_requested_at: Optional[datetime] = None
        self.exit_code: Optional[int] = None
        self.created_at: datetime = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error_message: Optional[str] = None

        # Validate inputs upon instantiation
        self._validate_parameters()

    def transition_to(self, new_status: JobStatus, reason: str = ""):
        """Enforces deterministic finite state machine transitions."""
        allowed = self._TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise StateTransitionError(
                f"Illegal state transition from [{self.status.value}] to [{new_status.value}]. Reason: {reason}"
            )
        self.status = new_status

    def parse(self):
        """Transitions SUBMITTED job to PARSED after grammar-constrained decoding and parameter validation."""
        self.transition_to(JobStatus.PARSED, "Parameters and syntax verified")

    def request_approval(self, requested_at: datetime):
        """Initiates the Maker-Checker governance window."""
        if self.status == JobStatus.SUBMITTED:
            self.parse()
        self.transition_to(JobStatus.PENDING_APPROVAL, "Waiting for Checker sign-off")
        self.approval_requested_at = requested_at

    def apply_approval_decision(
        self,
        decision: ApprovalDecision,
        evaluated_at: datetime,
        timeout_seconds: int = 900
    ):
        """
        Hard Banking Invariant 1: Maker-Checker (Separation of Duties).
        Hard Banking Invariant 2: 15-Minute Fail-Closed Timeout.
        """
        if self.status != JobStatus.PENDING_APPROVAL:
            raise StateTransitionError(f"Cannot apply approval decision in status [{self.status.value}]")

        # Invariant 2: 15-Minute Fail-Closed Timeout
        if self.approval_requested_at is not None:
            elapsed = (evaluated_at - self.approval_requested_at).total_seconds()
            if elapsed > timeout_seconds:
                self.transition_to(JobStatus.TIMEOUT_DENIED, f"Approval timed out after {elapsed:.1f}s (> {timeout_seconds}s)")
                raise ApprovalTimeoutError("Approval window expired. Request denied fail-closed.")

        # Invariant 1: Hard Maker != Checker Inequality
        if decision.approver_id == self.requester_id:
            raise MakerCheckerViolationError(
                f"Separation of Duties Violation: Requester [{self.requester_id}] cannot approve their own change."
            )

        self.approver_id = decision.approver_id
        self.approval_decision = decision

        if decision.decision.upper() == "APPROVE":
            self.transition_to(JobStatus.QUEUED, f"Approved by {decision.approver_id}")
        else:
            self.transition_to(JobStatus.REJECTED, f"Rejected by {decision.approver_id}: {decision.reason}")

    def _validate_parameters(self):
        """
        Hard Invariant 3: Parameter Regex, Bounds, Schema, and Secret Linting.
        """
        schema = self.catalog_item.input_schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # 1. Required fields check
        for req_field in required:
            if req_field not in self.parameters:
                raise ParameterValidationError(f"Missing required parameter: '{req_field}'")

        # 2. Properties validation: Regex, Range, Enum, Entropy/Secret check
        for key, value in self.parameters.items():
            if key not in properties:
                continue

            prop_def = properties[key]
            val_type = prop_def.get("type")

            # Type checking
            if val_type == "string":
                if not isinstance(value, str):
                    raise ParameterValidationError(f"Parameter '{key}' must be string, got {type(value).__name__}")
                
                # Secret/Credential scanning (TruffleHog invariant) runs FIRST before regex
                self._lint_secret(key, value)

                # Regex constraint
                pattern = prop_def.get("pattern")
                if pattern and not re.match(pattern, value):
                    raise ParameterValidationError(
                        f"Parameter '{key}' value '{value}' does not match required regex pattern: {pattern}"
                    )

            elif val_type in ("integer", "number"):
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ParameterValidationError(f"Parameter '{key}' must be numeric, got {type(value).__name__}")
                
                minimum = prop_def.get("minimum")
                maximum = prop_def.get("maximum")
                if minimum is not None and value < minimum:
                    raise ParameterValidationError(f"Parameter '{key}' value {value} is below minimum {minimum}")
                if maximum is not None and value > maximum:
                    raise ParameterValidationError(f"Parameter '{key}' value {value} exceeds maximum {maximum}")

            elif val_type == "array":
                if not isinstance(value, list):
                    raise ParameterValidationError(f"Parameter '{key}' must be a list")

    @staticmethod
    def _lint_secret(key: str, value: str):
        """Pre-flight secret scanner to prevent credential leakage."""
        patterns = [
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"AKIA[0-9A-Z]{16}",
            r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"]{6,}['\"]",
        ]
        for pat in patterns:
            if re.search(pat, value):
                raise SecretLintError(
                    f"Security Invariant Triggered: High-entropy secret pattern detected in parameter '{key}'."
                )
