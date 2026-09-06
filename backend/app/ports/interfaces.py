"""
Project Vulcan: Domain Ports (Dependency Inversion Interfaces)
Pure abstract base classes defining outer boundaries.
"""
import abc
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from app.domain.entities import (
    AuditRecord,
    EngineExecutionResult,
    EphemeralSecretLease,
    ExecutionJob,
    HealthCheckResult,
)


class ILockManager(abc.ABC):
    """Port for distributed resource mutual exclusion (e.g. Redis Redlock with fencing tokens)."""
    @abc.abstractmethod
    def acquire(self, resource_id: str, ttl_seconds: int = 1800, owner_token: Optional[str] = None) -> bool:
        """Atomically acquire a lock on resource_id with an ownership token. Returns True if acquired."""
        pass

    @abc.abstractmethod
    def release(self, resource_id: str, owner_token: Optional[str] = None) -> bool:
        """
        Safely releases lock on resource_id using atomic compare-and-delete.
        Guarantees that expired locks held by other workers are never deleted.
        """
        pass

    @abc.abstractmethod
    def is_locked(self, resource_id: str) -> bool:
        """Inspect if the resource_id is currently held."""
        pass


class ISecretProvider(abc.ABC):
    """Port for Just-In-Time privileged credential checkout into RAM (e.g. CyberArk PAM)."""
    @abc.abstractmethod
    def checkout_ephemeral_secret(self, target: str) -> EphemeralSecretLease:
        """Retrieve short-lived credentials for target into RAM only."""
        pass

    @abc.abstractmethod
    def revoke_ephemeral_secret(self, lease: EphemeralSecretLease) -> None:
        """Immediately revoke or invalidate the ephemeral credential lease."""
        pass


class IAuditLogger(abc.ABC):
    """Port for cryptographic immutable audit recording (Merkle hash chain)."""
    @abc.abstractmethod
    def record(self, job: ExecutionJob, action: str, payload: Dict[str, Any]) -> AuditRecord:
        """Commit an audit record synchronously before or after execution."""
        pass

    @abc.abstractmethod
    def get_last_hash(self) -> str:
        """Return the current tip of the Merkle hash chain."""
        pass

    @abc.abstractmethod
    def verify_chain(self) -> bool:
        """Mathematically recalculate and verify entire cryptographic hash sequence."""
        pass


class IServiceNowGateway(abc.ABC):
    """Port for enterprise Change Management and Maintenance Window verification."""
    @abc.abstractmethod
    def validate_chg(self, chg_number: str) -> Dict[str, Any]:
        """Fetch and validate ServiceNow CHG ticket details."""
        pass

    @abc.abstractmethod
    def is_within_maintenance_window(self, chg_number: str, check_time: datetime) -> bool:
        """Verify if check_time falls within the CHG's approved scheduled window."""
        pass

    @abc.abstractmethod
    def update_work_notes(self, chg_number: str, notes: str, new_state: Optional[str] = None) -> None:
        """Synchronize execution status and work notes bi-directionally to ServiceNow."""
        pass


class IObjectStorageGateway(abc.ABC):
    """Port for decoupled 10GB binary payload verification (MinIO / S3)."""
    @abc.abstractmethod
    def verify_artifact_checksum(self, uri: str, expected_sha256: str) -> bool:
        """Verify storage artifact matches expected SHA256 checksum before worker runs."""
        pass


class IHealthProbeGateway(abc.ABC):
    """Port for synthetic post-flight health probes (TLS 1.3, HTTP 200, Latency)."""
    @abc.abstractmethod
    def probe(self, job: ExecutionJob) -> HealthCheckResult:
        """Execute post-flight health checks to verify true service stability."""
        pass


class IExecutionEngine(abc.ABC):
    """Port for underlying runtime execution engines (Ansible, Terraform, OpenTofu)."""
    @abc.abstractmethod
    def execute(
        self,
        job: ExecutionJob,
        event_callback: Callable[[str], None],
        secrets: Dict[str, str]
    ) -> EngineExecutionResult:
        """Execute the automation script or playbook."""
        pass
