"""
Project Vulcan: Core Domain Repository Ports
Author: Robert C. Martin ("Uncle Bob") & Alex Xu (Systems Lead)
Clean Architecture: Domain repository interfaces isolating domain from database engines.
"""
import abc
from typing import Any, Dict, List, Optional

from app.domain.entities import AuditRecord, CatalogItem, ExecutionJob, JobStatus


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
    def search_hybrid(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        curation_status: Optional[str] = None
    ) -> List[Any]:
        """Executes hybrid dense HNSW + sparse keyword search with RRF fusion and refusal gating."""
        pass
