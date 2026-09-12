"""
Project Vulcan: Core Domain Repository Ports
Author: Robert C. Martin ("Uncle Bob") & Alex Xu (Systems Lead)
Clean Architecture: Domain repository interfaces isolating domain from database engines.
"""
import abc
from typing import Any, Dict, List, Optional, Union

from app.domain.entities import AuditRecord, CatalogItem, ExecutionJob, JobStatus
from app.domain.chat_entities import ChatFeedbackRecord, ChatSession, ChatTurn
from app.domain.external_resource_entities import (
    ExternalResource,
    ExternalResourceAuditRecord,
    ExternalResourceHealth,
    ExternalResourceVersion,
    ResourceCategory,
    ResourceEnvironment,
)



class IJobRepository(abc.ABC):
    """Abstract persistence port for ExecutionJob aggregate roots."""

    @abc.abstractmethod
    def save(self, job: ExecutionJob) -> None:
        """Persists or updates the execution job state."""
        pass

    @abc.abstractmethod
    def get_by_id(self, job_id: str) -> Optional[ExecutionJob]:
        """Retrieves a job by its unique identifier."""
        pass

    @abc.abstractmethod
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ExecutionJob]:
        """Lists jobs with optional status filtering and pagination."""
        pass

    @abc.abstractmethod
    def get_pending_approvals(self) -> List[ExecutionJob]:
        """Retrieves all jobs currently in PENDING_APPROVAL status."""
        pass

    @abc.abstractmethod
    def get_running_jobs(self) -> List[ExecutionJob]:
        """Retrieves all jobs currently in RUNNING or LOCKED status (for orphan reaper)."""
        pass

    def get_status_counts(self) -> Dict[str, int]:
        """Returns job counts grouped by status."""
        jobs = self.list_jobs(limit=10000)
        counts: Dict[str, int] = {}
        for j in jobs:
            st = j.status.value
            counts[st] = counts.get(st, 0) + 1
        counts["ALL"] = len(jobs)
        return counts


class IAuditLedgerRepository(abc.ABC):
    """Abstract persistence port for cryptographic Merkle audit records."""

    @abc.abstractmethod
    def append(self, record: AuditRecord) -> None:
        """Atomically appends a cryptographic audit record to the ledger."""
        pass

    @abc.abstractmethod
    def get_chain(self, correlation_id: Optional[str] = None) -> List[AuditRecord]:
        """Retrieves the complete audit record chain or a subset by correlation ID."""
        pass

    @abc.abstractmethod
    def verify_integrity(self) -> bool:
        """Validates the SHA-256 hash chain from genesis to head."""
        pass


class ICatalogRepository(abc.ABC):
    """Abstract persistence port for immutable catalog specifications."""

    @abc.abstractmethod
    def get_by_identifier(self, identifier: str) -> Optional[CatalogItem]:
        """Fetches catalog item by identifier."""
        pass

    @abc.abstractmethod
    def list_all(self, curation_status: Optional[str] = None) -> List[CatalogItem]:
        """Returns all registered catalog items."""
        pass

    @abc.abstractmethod
    def search_vector(self, embedding: List[float], top_k: int = 10) -> List[CatalogItem]:
        """Executes pgvector HNSW cosine similarity search over catalog items."""
        pass

    @abc.abstractmethod
    def save(self, item: CatalogItem, embedding: Optional[List[float]] = None) -> None:
        """Persists or updates a catalog item."""
        pass

    @abc.abstractmethod
    def count(self, curation_status: Optional[str] = None) -> int:
        """Returns total count of registered catalog items."""
        pass

    @abc.abstractmethod
    def search_sparse(
        self,
        query: str,
        top_k: int = 10,
        curation_status: Optional[str] = None
    ) -> List[Any]:
        """Executes sparse keyword/full-text search over catalog items."""
        pass

    @abc.abstractmethod
    def search_hybrid(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        curation_status: Optional[str] = None
    ) -> List[Any]:
        """Executes hybrid dense HNSW + sparse keyword search with RRF fusion and refusal gating."""
        pass


class IChatSessionRepository(abc.ABC):
    """
    Abstract persistence port for multi-turn conversational sessions (CHAT-03).
    Guarantees conversational continuity across pods, workers, and browser reloads.
    """

    @abc.abstractmethod
    def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """Creates and stores a new chat session."""
        pass

    @abc.abstractmethod
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Retrieves a session with all its turns."""
        pass

    @abc.abstractmethod
    def append_turn(self, session_id: str, turn: ChatTurn) -> ChatTurn:
        """Appends a turn to a session and updates session state."""
        pass

    @abc.abstractmethod
    def get_turns(self, session_id: str, limit: int = 50) -> List[ChatTurn]:
        """Retrieves turns for a given session in chronological order."""
        pass

    @abc.abstractmethod
    def list_sessions_for_user(self, user_id: str, limit: int = 20) -> List[ChatSession]:
        """Lists recent chat sessions for an operator."""
        pass

    @abc.abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Deletes a chat session and its associated turns."""
        pass


class IFeedbackRepository(abc.ABC):
    """
    Abstract persistence port for operator reinforcement feedback (CHAT-26).
    Enables gathering human ratings and corrections on intent resolutions
    for model evaluation, guardrail calibration, and RLHF/DPO dataset curation.
    """

    @abc.abstractmethod
    def save_feedback(self, record: ChatFeedbackRecord) -> ChatFeedbackRecord:
        """Persists an operator feedback record."""
        pass

    @abc.abstractmethod
    def list_feedback(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        rating: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ChatFeedbackRecord]:
        """Lists feedback records with optional filtering and pagination."""
        pass

    @abc.abstractmethod
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Aggregates feedback metrics (acceptance rate, volume, top corrections)."""
        pass

    @abc.abstractmethod
    def export_rlhf_dataset(self) -> List[Dict[str, Any]]:
        """Exports pairwise preference datasets (DPO / KTO / SFT) for training."""
        pass


class IExternalResourceRepository(abc.ABC):
    """
    Abstract persistence port for External Resources (R1, R2).
    Provides atomic persistence, immutable version history, time-series health telemetry,
    and Merkle-chained audit logging for external system integrations.
    """

    @abc.abstractmethod
    def save(self, resource: ExternalResource, actor: str, reason: str) -> ExternalResource:
        """
        Atomically persists or updates an external resource.
        """
        pass

    @abc.abstractmethod
    def get_by_id(self, resource_id: str) -> Optional[ExternalResource]:
        """
        Retrieves an external resource by its unique identifier.
        """
        pass

    @abc.abstractmethod
    def list_all(
        self,
        category: Optional[Union[ResourceCategory, str]] = None,
        environment: Optional[Union[ResourceEnvironment, str]] = None,
        enabled: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ExternalResource]:
        """
        Lists external resources matching optional filter criteria with pagination.
        """
        pass

    @abc.abstractmethod
    def delete(self, resource_id: str, actor: str) -> bool:
        """
        Deletes an external resource by its identifier.
        """
        pass

    @abc.abstractmethod
    def get_versions(self, resource_id: str, limit: int = 50) -> List[ExternalResourceVersion]:
        """
        Retrieves immutable historical configuration revision snapshots for a resource.
        """
        pass

    @abc.abstractmethod
    def record_health(self, health: ExternalResourceHealth) -> None:
        """
        Records a health telemetry check and updates the resource's current operational state.
        """
        pass

    @abc.abstractmethod
    def get_latest_health(self, resource_id: str) -> Optional[ExternalResourceHealth]:
        """
        Retrieves the most recent health check record for a resource.
        """
        pass

    @abc.abstractmethod
    def get_health_history(self, resource_id: str, limit: int = 50) -> List[ExternalResourceHealth]:
        """
        Retrieves chronological health check history for a resource.
        """
        pass

    @abc.abstractmethod
    def get_audit_records(
        self,
        resource_id: Optional[str] = None,
        limit: int = 50
    ) -> List[ExternalResourceAuditRecord]:
        """
        Retrieves Merkle audit ledger records.
        """
        pass

    @abc.abstractmethod
    def verify_audit_integrity(self) -> bool:
        """
        Cryptographically validates the SHA-256 Merkle chain across all audit records.
        """
        pass



