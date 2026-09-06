"""
Project Vulcan: Domain Ports (Dependency Inversion Interfaces)
Pure abstract base classes defining outer boundaries.
"""
import abc
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
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
    def record(self, job: ExecutionJob, action: str, payload: Dict[str, Any], actor: Optional[str] = None) -> AuditRecord:
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
    """Port for decoupled 10GB binary payload verification and S3 presigned multipart storage."""
    @abc.abstractmethod
    def verify_artifact_checksum(self, uri: str, expected_sha256: str) -> bool:
        """Verify storage artifact matches expected SHA256 checksum before worker runs."""
        pass

    def initiate_multipart_upload(
        self,
        file_name: str,
        file_size_bytes: int,
        sha256_checksum: str,
        job_id: str
    ) -> Dict[str, Any]:
        """Calculates 50MB chunks and generates presigned PUT URLs for each chunk."""
        raise NotImplementedError

    def complete_multipart_upload(
        self,
        upload_id: str,
        s3_key: str,
        parts: List[Dict[str, Any]]
    ) -> str:
        """Completes the multipart upload and returns final S3 URI."""
        raise NotImplementedError

    def abort_multipart_upload(
        self,
        upload_id: str,
        s3_key: str
    ) -> bool:
        """Abort in-progress multipart upload and purge temporary chunks (BKND-14)."""
        raise NotImplementedError

    def cleanup_orphaned_uploads(
        self,
        max_age_seconds: int = 86400
    ) -> int:
        """Find and abort multipart uploads older than max_age_seconds (BKND-14)."""
        raise NotImplementedError


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


class ChatCompletionRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    grammar_json_schema: Optional[Dict[str, Any]] = None
    max_tokens: int = 500
    temperature: float = 0.0


class ChatCompletionResponse(BaseModel):
    content: str
    parsed_json: Optional[Dict[str, Any]] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    model_version: str = "deterministic-fake-v1"


class IChatModelProvider(abc.ABC):
    """Port for conversational AI planning and schema-constrained decoding (LLM Boundary)."""
    @abc.abstractmethod
    def complete_structured(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Executes a schema-constrained completion call."""
        pass

    @abc.abstractmethod
    def stream_structured(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """Streams completion tokens over Server-Sent Events or WebSocket."""
        pass


class IEmbeddingProvider(abc.ABC):
    """Port for text and query vector embedding generation (pgvector 1,536-dim)."""

    @abc.abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embeds a single text into a normalized float vector."""
        pass

    @abc.abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts into normalized float vectors."""
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Returns the vector dimensionality (typically 1,536)."""
        pass

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Returns the unique name or model identifier of the provider."""
        pass

    @property
    def refusal_thresholds(self) -> Dict[str, float]:
        """Calibrated refusal gate thresholds for this provider."""
        return {
            "min_dense_no_sparse": 0.45,
            "min_dense_with_sparse": 0.35,
            "min_sparse_cutoff": 0.20,
            "rrf_dense_floor": 0.35,
        }

    def is_refusal(self, max_dense: float, max_sparse: float) -> bool:
        """Evaluates whether the query falls below the calibrated refusal thresholds."""
        t = self.refusal_thresholds
        min_no_sparse = t.get("min_dense_no_sparse", 0.45)
        min_with_sparse = t.get("min_dense_with_sparse", 0.35)
        sparse_cutoff = t.get("min_sparse_cutoff", 0.20)
        return (max_dense < min_no_sparse and max_sparse <= 0.0) or (max_dense < min_with_sparse and max_sparse < sparse_cutoff)


