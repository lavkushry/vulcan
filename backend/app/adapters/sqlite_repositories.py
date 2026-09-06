"""
Project Vulcan: SQLite Repository Adapters
Implements IJobRepository, IAuditLedgerRepository, and ICatalogRepository
using SQLite for zero-dependency durable persistence.

Falls back gracefully to in-memory SQLite when file path is ":memory:".
Auto-creates tables on first run via CREATE TABLE IF NOT EXISTS.
"""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.domain.entities import (
    AuditRecord,
    CatalogItem,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
)
from app.ports.repositories import IAuditLedgerRepository, ICatalogRepository, IJobRepository

logger = logging.getLogger("vulcan.sqlite")


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ===========================================================================
# JOB REPOSITORY
# ===========================================================================

class SQLiteJobRepository(IJobRepository):
    """Durable job persistence using SQLite."""

    def __init__(self, db_path: str = "data/vulcan.db", catalog: Optional[List[CatalogItem]] = None):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = _get_connection(db_path)
        self._catalog = catalog
        self._create_tables()

    def _get_catalog_map(self) -> Dict[str, CatalogItem]:
        if self._catalog:
            return {item.identifier: item for item in self._catalog}
        from app.catalog_data import get_catalog_items
        return {item.identifier: item for item in get_catalog_items()}

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS execution_jobs (
                id TEXT PRIMARY KEY,
                correlation_id TEXT UNIQUE NOT NULL,
                catalog_identifier TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'SUBMITTED',
                risk_tier TEXT,
                requester_id TEXT NOT NULL,
                approver_id TEXT,
                target_resource_id TEXT,
                environment TEXT DEFAULT 'PROD',
                parameters TEXT DEFAULT '{}',
                servicenow_chg TEXT,
                storage_artifact_uri TEXT,
                storage_artifact_sha256 TEXT,
                approval_requested_at TEXT,
                approval_decision TEXT,
                exit_code INTEGER,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON execution_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_correlation ON execution_jobs(correlation_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_created ON execution_jobs(created_at);
        """)
        self._conn.commit()

    def save(self, job: ExecutionJob) -> None:
        with self._lock:
            approval_decision_json = None
            if job.approval_decision:
                approval_decision_json = json.dumps({
                    "decision": job.approval_decision.decision,
                    "approver_id": job.approval_decision.approver_id,
                    "decided_at": job.approval_decision.decided_at.isoformat(),
                    "reason": job.approval_decision.reason,
                    "chg_number": job.approval_decision.chg_number,
                })

            self._conn.execute("""
                INSERT INTO execution_jobs (
                    id, correlation_id, catalog_identifier, status, risk_tier,
                    requester_id, approver_id, target_resource_id, environment,
                    parameters, servicenow_chg, storage_artifact_uri,
                    storage_artifact_sha256, approval_requested_at,
                    approval_decision, exit_code, error_message,
                    created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    approver_id=excluded.approver_id,
                    approval_requested_at=excluded.approval_requested_at,
                    approval_decision=excluded.approval_decision,
                    exit_code=excluded.exit_code,
                    error_message=excluded.error_message,
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at
            """, (
                job.id,
                job.correlation_id,
                job.catalog_item.identifier,
                job.status.value,
                job.catalog_item.risk_tier.value,
                job.requester_id,
                job.approver_id,
                job.target_resource_id,
                job.environment,
                json.dumps(job.parameters),
                job.servicenow_chg,
                job.storage_artifact_uri,
                job.storage_artifact_sha256,
                job.approval_requested_at.isoformat() if job.approval_requested_at else None,
                approval_decision_json,
                job.exit_code,
                job.error_message,
                job.created_at.isoformat(),
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
            ))
            self._conn.commit()

    def _row_to_job(self, row: sqlite3.Row, catalog_map: Dict[str, CatalogItem]) -> Optional[ExecutionJob]:
        """Reconstruct an ExecutionJob from a database row."""
        cat_item = catalog_map.get(row["catalog_identifier"])
        if not cat_item:
            logger.warning(f"Catalog item not found for identifier: {row['catalog_identifier']}")
            return None

        params = json.loads(row["parameters"]) if row["parameters"] else {}
        job = ExecutionJob(
            job_id=row["id"],
            correlation_id=row["correlation_id"],
            catalog_item=cat_item,
            requester_id=row["requester_id"],
            target_resource_id=row["target_resource_id"] or "",
            parameters=params,
            servicenow_chg=row["servicenow_chg"],
            storage_artifact_uri=row["storage_artifact_uri"],
            storage_artifact_sha256=row["storage_artifact_sha256"],
            environment=row["environment"] or "PROD",
        )

        # Restore mutable state without triggering transition validation
        job.status = JobStatus(row["status"])
        job.approver_id = row["approver_id"]
        job.exit_code = row["exit_code"]
        job.error_message = row["error_message"]

        if row["created_at"]:
            job.created_at = datetime.fromisoformat(row["created_at"])
        if row["started_at"]:
            job.started_at = datetime.fromisoformat(row["started_at"])
        if row["completed_at"]:
            job.completed_at = datetime.fromisoformat(row["completed_at"])
        if row["approval_requested_at"]:
            job.approval_requested_at = datetime.fromisoformat(row["approval_requested_at"])

        return job

    def get_by_id(self, job_id: str) -> Optional[ExecutionJob]:
        catalog_map = self._get_catalog_map()
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM execution_jobs WHERE id = ? OR correlation_id = ?",
                (job_id, job_id)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_job(row, catalog_map)
        return None

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ExecutionJob]:
        catalog_map = self._get_catalog_map()
        with self._lock:
            if status:
                cursor = self._conn.execute(
                    "SELECT * FROM execution_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status.value, limit, offset)
                )
            else:
                cursor = self._conn.execute(
                    "SELECT * FROM execution_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
            rows = cursor.fetchall()
        jobs = []
        for row in rows:
            job = self._row_to_job(row, catalog_map)
            if job:
                jobs.append(job)
        return jobs

    def get_pending_approvals(self) -> List[ExecutionJob]:
        return self.list_jobs(status=JobStatus.PENDING_APPROVAL, limit=500)


# ===========================================================================
# AUDIT LEDGER REPOSITORY
# ===========================================================================

class SQLiteAuditLedgerRepository(IAuditLedgerRepository):
    """Durable Merkle audit chain persistence using SQLite."""

    def __init__(self, db_path: str = "data/vulcan.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = _get_connection(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correlation_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT DEFAULT '{}',
                prev_hash TEXT NOT NULL,
                current_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_ledger(correlation_id);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_ledger(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_hash ON audit_ledger(current_hash);
        """)
        self._conn.commit()

    def append(self, record: AuditRecord) -> None:
        with self._lock:
            self._conn.execute("""
                INSERT INTO audit_ledger (
                    id, correlation_id, timestamp, actor, action,
                    payload, prev_hash, current_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id,
                record.correlation_id,
                record.timestamp,
                record.actor,
                record.action,
                json.dumps(record.payload),
                record.prev_hash,
                record.current_hash,
            ))
            self._conn.commit()

    def get_chain(self, correlation_id: Optional[str] = None) -> List[AuditRecord]:
        with self._lock:
            if correlation_id:
                cursor = self._conn.execute(
                    "SELECT * FROM audit_ledger WHERE correlation_id = ? ORDER BY id",
                    (correlation_id,)
                )
            else:
                cursor = self._conn.execute(
                    "SELECT * FROM audit_ledger ORDER BY id"
                )
            rows = cursor.fetchall()

        records = []
        for row in rows:
            records.append(AuditRecord(
                id=row["id"],
                correlation_id=row["correlation_id"],
                timestamp=row["timestamp"],
                actor=row["actor"],
                action=row["action"],
                payload=json.loads(row["payload"]) if row["payload"] else {},
                prev_hash=row["prev_hash"],
                current_hash=row["current_hash"],
            ))
        return records

    def verify_integrity(self) -> bool:
        """Validate the full SHA-256 Merkle chain from genesis to head."""
        chain = self.get_chain()
        if not chain:
            return True

        genesis_hash = "0" * 64
        expected_prev = genesis_hash

        for record in chain:
            if record.prev_hash != expected_prev:
                logger.error(
                    f"Merkle chain broken at record {record.id}: "
                    f"expected prev_hash={expected_prev}, got={record.prev_hash}"
                )
                return False

            computed = AuditRecord.compute_hash(
                record.correlation_id,
                record.timestamp,
                record.actor,
                record.action,
                record.payload,
                record.prev_hash,
            )
            if computed != record.current_hash:
                logger.error(
                    f"Hash mismatch at record {record.id}: "
                    f"computed={computed}, stored={record.current_hash}"
                )
                return False

            expected_prev = record.current_hash

        return True


# ===========================================================================
# CATALOG REPOSITORY
# ===========================================================================

class SQLiteCatalogRepository(ICatalogRepository):
    """Durable catalog persistence using SQLite."""

    def __init__(self, db_path: str = "data/vulcan.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = _get_connection(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS catalog_items (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                engine TEXT NOT NULL,
                git_repo TEXT NOT NULL,
                git_commit_sha TEXT NOT NULL,
                playbook_or_module_path TEXT NOT NULL,
                risk_tier TEXT NOT NULL,
                requires_maker_checker INTEGER DEFAULT 1,
                requires_chg INTEGER DEFAULT 1,
                input_schema TEXT DEFAULT '{}',
                rollback_path TEXT,
                category TEXT DEFAULT 'general',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_catalog_engine ON catalog_items(engine);
            CREATE INDEX IF NOT EXISTS idx_catalog_risk ON catalog_items(risk_tier);
            CREATE INDEX IF NOT EXISTS idx_catalog_identifier ON catalog_items(identifier);
        """)
        self._conn.commit()

    def seed_if_empty(self, items: List[CatalogItem]) -> int:
        """Seed catalog items if the table is empty. Returns count of items seeded."""
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM catalog_items")
            count = cursor.fetchone()[0]
            if count > 0:
                return 0

            for item in items:
                self._conn.execute("""
                    INSERT OR IGNORE INTO catalog_items (
                        id, identifier, name, engine, git_repo, git_commit_sha,
                        playbook_or_module_path, risk_tier, requires_maker_checker,
                        requires_chg, input_schema, rollback_path, category,
                        description, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.id,
                    item.identifier,
                    item.name,
                    item.engine.value,
                    item.git_repo,
                    item.git_commit_sha,
                    item.playbook_or_module_path,
                    item.risk_tier.value,
                    1 if item.requires_maker_checker else 0,
                    1 if item.requires_chg else 0,
                    json.dumps(item.input_schema),
                    item.rollback_path,
                    item.category,
                    item.description,
                    json.dumps(item.tags),
                ))
            self._conn.commit()
            return len(items)

    def get_by_identifier(self, identifier: str) -> Optional[CatalogItem]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM catalog_items WHERE identifier = ?",
                (identifier,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_item(row)
        return None

    def list_all(self) -> List[CatalogItem]:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM catalog_items ORDER BY category, name")
            rows = cursor.fetchall()
        return [self._row_to_item(row) for row in rows]

    def search_vector(self, embedding: List[float], top_k: int = 10) -> List[CatalogItem]:
        """Vector search not available in SQLite. Falls back to returning all items."""
        logger.debug("Vector search not available in SQLite adapter; returning full catalog.")
        return self.list_all()[:top_k]

    def _row_to_item(self, row: sqlite3.Row) -> CatalogItem:
        return CatalogItem(
            id=row["id"],
            identifier=row["identifier"],
            name=row["name"],
            engine=ExecutionEngineType(row["engine"]),
            git_repo=row["git_repo"],
            git_commit_sha=row["git_commit_sha"],
            playbook_or_module_path=row["playbook_or_module_path"],
            risk_tier=RiskTier(row["risk_tier"]),
            requires_maker_checker=bool(row["requires_maker_checker"]),
            requires_chg=bool(row["requires_chg"]),
            input_schema=json.loads(row["input_schema"]) if row["input_schema"] else {},
            rollback_path=row["rollback_path"],
            category=row["category"] or "general",
            description=row["description"] or "",
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )
