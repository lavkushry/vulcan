"""
Project Vulcan: Domain Ports (Dependency Inversion Interfaces)
Pure abstract base classes defining outer boundaries.
"""
import abc
from datetime import datetime, timezone
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

    def get_fencing_token(self, resource_id: str) -> Optional[int]:
        """Returns the current monotonic fencing token for resource_id, if available."""
        return None

    def validate_fencing_token(self, resource_id: str, token: int) -> bool:
        """Inspect if the given fencing token matches the current active token for resource_id."""
        return True


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

    def lookup_cmdb_ci(self, ci_name_or_id: str) -> Optional[Dict[str, Any]]:
        """Fetch Configuration Item (CI) details from ServiceNow CMDB."""
        return None

    def hydrate_ticket_and_cmdb(self, chg_number: str) -> Dict[str, Any]:
        """
        Unified fetch: validates change ticket and enriches with CMDB CI attributes (CHAT-14).
        Default implementation wraps validate_chg and lookup_cmdb_ci.
        """
        ticket = self.validate_chg(chg_number)
        is_valid = ticket.get("is_valid", False)
        ci_val = ticket.get("ci")
        cmdb_data = self.lookup_cmdb_ci(ci_val) if ci_val else None
        now = datetime.now(timezone.utc)
        in_window = self.is_within_maintenance_window(chg_number, now) if is_valid else False

        params: Dict[str, Any] = {"servicenow_chg": chg_number}
        provenance: Dict[str, str] = {"servicenow_chg": "✓ CHG"}
        if ci_val:
            params["target_host"] = ci_val
            params["hostname"] = ci_val
            provenance["target_host"] = "🏢 CMDB"
            provenance["hostname"] = "🏢 CMDB"
        if cmdb_data:
            if cmdb_data.get("ip_address"):
                params["ip_address"] = cmdb_data["ip_address"]
                provenance["ip_address"] = "🏢 CMDB"
            if cmdb_data.get("environment"):
                params["environment"] = cmdb_data["environment"]
                provenance["environment"] = "🏢 CMDB"
            if cmdb_data.get("tier"):
                params["tier"] = cmdb_data["tier"]
                provenance["tier"] = "🏢 CMDB"
            if cmdb_data.get("datacenter"):
                params["datacenter"] = cmdb_data["datacenter"]
                provenance["datacenter"] = "🏢 CMDB"

        return {
            "chg_number": chg_number,
            "is_valid": is_valid,
            "state": ticket.get("state"),
            "risk": ticket.get("risk"),
            "start_time": ticket.get("start_time"),
            "end_time": ticket.get("end_time"),
            "in_maintenance_window": in_window,
            "ci": ci_val,
            "cmdb": cmdb_data,
            "parameters_hydrated": params,
            "provenance": provenance,
            "error": ticket.get("error")
        }


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


class InjectionInspectionResult(BaseModel):
    """Result of multi-stage prompt injection, secret leak, and adversarial intent analysis (CHAT-17)."""
    is_adversarial: bool = False
    stage: Optional[str] = None  # stage_1_normalization, stage_2_secrets_entropy, stage_3_delimiters_patterns, stage_4_intent_classifier
    refusal_reason: Optional[str] = None
    risk_score: float = 0.0  # Normalized [0.0, 1.0]
    entropy_score: float = 0.0  # Max Shannon entropy observed in alphanumeric tokens
    detected_patterns: List[str] = Field(default_factory=list)
    sanitized_prompt: str = ""
    unpacked_payload: Optional[str] = None
    latency_ms: float = 0.0


class IInjectionDefensePipeline(abc.ABC):
    """Port for Four-Stage Adversarial Prompt Injection & Secret Sanitization Pipeline (CHAT-17)."""

    @abc.abstractmethod
    def inspect(self, prompt: str) -> InjectionInspectionResult:
        """
        Inspects an incoming prompt across all four defense-in-depth stages:
        Stage 1: Unicode NFKC normalization, homoglyph translation & invisible character stripping.
        Stage 2: High-entropy secret detection (Shannon entropy, API keys, private keys, Base64/Hex unpacking).
        Stage 3: Delimiter framing, structural tag escapes, prompt injection & destructive execution patterns.
        Stage 4: Adversarial Intent Classifier (multi-signal semantic scoring with operational whitelist weighting).
        """
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
    def is_calibrated(self) -> bool:
        """Indicates whether refusal gate thresholds have been empirically calibrated for this model."""
        return True

    @property
    def refusal_thresholds(self) -> Dict[str, Any]:
        """Calibrated refusal gate thresholds for this provider."""
        return {
            "calibrated": True,
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
        return (max_dense < min_no_sparse and max_sparse <= 0.0) or (max_dense < min_with_sparse and max_sparse <= sparse_cutoff)


class JobQueueMessage(BaseModel):
    """Represents a job dispatch payload enqueued on the message broker."""
    message_id: str
    job_id: str
    correlation_id: str
    enqueued_at: datetime
    priority: int = 0
    retry_count: int = 0
    payload: Optional[Dict[str, Any]] = None


class IJobQueue(abc.ABC):
    """Port for decoupled, durable job dispatch queue (e.g. Redis Streams / in-memory)."""

    @abc.abstractmethod
    def enqueue(self, job_id: str, correlation_id: str, priority: int = 0, payload: Optional[Dict[str, Any]] = None) -> str:
        """Enqueues a job for execution. Returns unique message ID."""
        pass

    @abc.abstractmethod
    def dequeue(self, worker_id: str, timeout_seconds: float = 2.0) -> Optional[JobQueueMessage]:
        """Dequeues the next available job message for the specified worker consumer."""
        pass

    @abc.abstractmethod
    def ack(self, message_id: str) -> bool:
        """Acknowledges successful processing and dequeues message from consumer group."""
        pass

    @abc.abstractmethod
    def nack(self, message_id: str, requeue: bool = True) -> bool:
        """Negatively acknowledges processing failure."""
        pass

    @abc.abstractmethod
    def requeue_stale(self, min_idle_ms: int = 60000, worker_id: str = "recovery_reaper") -> List[JobQueueMessage]:
        """Reclaims pending messages from dead or crashed workers."""
        pass

    @abc.abstractmethod
    def queue_depth(self) -> int:
        """Returns total count of pending and unacknowledged messages."""
        pass


