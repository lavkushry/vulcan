"""
Project Vulcan: SQLite Repository Adapters
Implements IJobRepository, IAuditLedgerRepository, and ICatalogRepository
using SQLite for zero-dependency durable persistence.

Falls back gracefully to in-memory SQLite when file path is ":memory:".
Auto-creates tables on first run via CREATE TABLE IF NOT EXISTS.
"""
import json
import logging
import os
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
    dir_path = os.path.dirname(db_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
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
                dispatched_by TEXT,
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
        try:
            self._conn.execute("ALTER TABLE execution_jobs ADD COLUMN dispatched_by TEXT;")
        except Exception:
            pass
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
                    requester_id, approver_id, dispatched_by, target_resource_id, environment,
                    parameters, servicenow_chg, storage_artifact_uri,
                    storage_artifact_sha256, approval_requested_at,
                    approval_decision, exit_code, error_message,
                    created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    parameters=excluded.parameters,
                    servicenow_chg=excluded.servicenow_chg,
                    target_resource_id=excluded.target_resource_id,
                    approver_id=excluded.approver_id,
                    dispatched_by=excluded.dispatched_by,
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
                getattr(job, "dispatched_by", None),
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
        job.dispatched_by = row["dispatched_by"] if "dispatched_by" in row.keys() else None
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

    def get_by_correlation_id(self, correlation_id: str) -> Optional[ExecutionJob]:
        return self.get_by_id(correlation_id)

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
        """Seed catalog items, ensuring all catalog items are synchronized into SQLite."""
        with self._lock:
            existing = {row[0] for row in self._conn.execute("SELECT id FROM catalog_items").fetchall()}
            seeded = 0
            for item in items:
                if item.id not in existing:
                    self._conn.execute("""
                        INSERT INTO catalog_items (
                            id, identifier, name, engine, git_repo, git_commit_sha,
                            playbook_or_module_path, risk_tier, requires_maker_checker,
                            requires_chg, input_schema, rollback_path, category,
                            description, tags
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item.id,
                        item.identifier,
                        item.name,
                        item.engine.value if hasattr(item.engine, "value") else str(item.engine),
                        item.git_repo,
                        item.git_commit_sha,
                        item.playbook_or_module_path,
                        item.risk_tier.value if hasattr(item.risk_tier, "value") else str(item.risk_tier),
                        1 if item.requires_maker_checker else 0,
                        1 if item.requires_chg else 0,
                        json.dumps(item.input_schema),
                        item.rollback_path,
                        item.category,
                        item.description,
                        json.dumps(item.tags)
                    ))
                    seeded += 1
            self._conn.commit()
            return seeded

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

    def list_all(self, curation_status: Optional[str] = None) -> List[CatalogItem]:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM catalog_items ORDER BY category, name")
            rows = cursor.fetchall()
        items = [self._row_to_item(row) for row in rows]
        if curation_status:
            items = [i for i in items if getattr(i, "curation_status", None) == curation_status]
        return items

    def search_vector(self, embedding: List[float], top_k: int = 10) -> List[CatalogItem]:
        """Vector search not available in SQLite. Falls back to returning all items."""
        logger.debug("Vector search not available in SQLite adapter; returning full catalog.")
        return self.list_all()[:top_k]

    def save(self, item: CatalogItem, embedding: Optional[List[float]] = None) -> None:
        """Persists or updates a catalog item in SQLite."""
        with self._lock:
            self._conn.execute("""
                INSERT INTO catalog_items (
                    id, identifier, name, engine, git_repo, git_commit_sha,
                    playbook_or_module_path, risk_tier, requires_maker_checker,
                    requires_chg, input_schema, rollback_path, category,
                    description, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    identifier=excluded.identifier,
                    name=excluded.name,
                    engine=excluded.engine,
                    git_repo=excluded.git_repo,
                    git_commit_sha=excluded.git_commit_sha,
                    playbook_or_module_path=excluded.playbook_or_module_path,
                    risk_tier=excluded.risk_tier,
                    requires_maker_checker=excluded.requires_maker_checker,
                    requires_chg=excluded.requires_chg,
                    input_schema=excluded.input_schema,
                    rollback_path=excluded.rollback_path,
                    category=excluded.category,
                    description=excluded.description,
                    tags=excluded.tags,
                    updated_at=datetime('now')
            """, (
                item.id,
                item.identifier,
                item.name,
                item.engine.value if hasattr(item.engine, "value") else str(item.engine),
                item.git_repo,
                item.git_commit_sha,
                item.playbook_or_module_path,
                item.risk_tier.value if hasattr(item.risk_tier, "value") else str(item.risk_tier),
                1 if item.requires_maker_checker else 0,
                1 if item.requires_chg else 0,
                json.dumps(item.input_schema),
                item.rollback_path,
                item.category,
                item.description,
                json.dumps(item.tags)
            ))
            self._conn.commit()

    def count(self, curation_status: Optional[str] = None) -> int:
        """Returns total count of registered catalog items."""
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM catalog_items")
            return int(cursor.fetchone()[0])

    def search_sparse(
        self,
        query: str,
        top_k: int = 10,
        curation_status: Optional[str] = None
    ) -> List[Any]:
        """Sparse search fallback using keyword matching."""
        items = self.list_all(curation_status=curation_status)
        matches = []
        for it in items:
            text = f"{it.name} {it.description} {it.identifier}".lower()
            overlap = sum(1 for term in query.lower().split() if term in text)
            if overlap > 0:
                matches.append((it, float(overlap)))
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_k]

    def search_hybrid(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        curation_status: Optional[str] = None
    ) -> List[Any]:
        """Hybrid search fallback using keyword matching."""
        items = self.list_all(curation_status=curation_status)
        matches = []
        for it in items:
            text = f"{it.name} {it.description} {it.identifier}".lower()
            if any(term in text for term in query.lower().split()):
                matches.append((it, 1.0, {"sparse_score": 1.0, "dense_score": 0.0}))
        return matches[:top_k]

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


# ===========================================================================
# INTEGRATION REPOSITORY
# ===========================================================================

class SQLiteIntegrationRepository:
    """Durable enterprise connector settings persistence using SQLite."""

    def __init__(self, db_path: str = "data/vulcan.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = _get_connection(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS integration_connectors (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                icon TEXT NOT NULL,
                description TEXT NOT NULL,
                endpoint_url TEXT NOT NULL,
                auth_type TEXT DEFAULT 'NONE',
                auth_token TEXT,
                username TEXT,
                status TEXT DEFAULT 'DISCONNECTED',
                latency_ms INTEGER DEFAULT 0,
                version TEXT,
                last_sync_at TEXT,
                config_summary TEXT DEFAULT '{}',
                capabilities TEXT DEFAULT '[]'
            );
        """)
        self._conn.commit()

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM integration_connectors ORDER BY name ASC")
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM integration_connectors WHERE key = ?", (key,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def save(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute("""
                INSERT INTO integration_connectors (
                    key, name, category, icon, description, endpoint_url,
                    auth_type, auth_token, username, status, latency_ms,
                    version, last_sync_at, config_summary, capabilities
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    icon = excluded.icon,
                    description = excluded.description,
                    endpoint_url = excluded.endpoint_url,
                    auth_type = excluded.auth_type,
                    auth_token = CASE 
                        WHEN excluded.auth_token IS NOT NULL AND excluded.auth_token != '' 
                        THEN excluded.auth_token 
                        ELSE integration_connectors.auth_token 
                    END,
                    username = excluded.username,
                    status = excluded.status,
                    latency_ms = excluded.latency_ms,
                    version = excluded.version,
                    last_sync_at = excluded.last_sync_at,
                    config_summary = excluded.config_summary,
                    capabilities = excluded.capabilities
            """, (
                data["key"],
                data["name"],
                data["category"],
                data["icon"],
                data["description"],
                data["endpoint_url"],
                data.get("auth_type", "NONE"),
                data.get("auth_token"),
                data.get("username"),
                data.get("status", "DISCONNECTED"),
                data.get("latency_ms", 0),
                data.get("version", "v1.0"),
                data.get("last_sync_at", datetime.now(timezone.utc).isoformat()),
                json.dumps(data.get("config_summary", {})),
                json.dumps(data.get("capabilities", [])),
            ))
            self._conn.commit()

    def seed_if_empty(self, defaults: List[Dict[str, Any]]) -> int:
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM integration_connectors")
            if cursor.fetchone()[0] > 0:
                return 0
            for d in defaults:
                self._conn.execute("""
                    INSERT INTO integration_connectors (
                        key, name, category, icon, description, endpoint_url,
                        auth_type, auth_token, username, status, latency_ms,
                        version, last_sync_at, config_summary, capabilities
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d["key"], d["name"], d["category"], d["icon"], d["description"],
                    d["endpoint_url"], d.get("auth_type", "NONE"), d.get("auth_token"),
                    d.get("username"), d.get("status", "CONNECTED"), d.get("latency_ms", 20),
                    d.get("version", "v1.0"), datetime.now(timezone.utc).isoformat(),
                    json.dumps(d.get("config_summary", {})),
                    json.dumps(d.get("capabilities", []))
                ))
            self._conn.commit()
            return len(defaults)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "key": row["key"],
            "name": row["name"],
            "category": row["category"],
            "icon": row["icon"],
            "description": row["description"],
            "endpoint_url": row["endpoint_url"],
            "auth_type": row["auth_type"] or "NONE",
            "auth_token": row["auth_token"],
            "username": row["username"],
            "status": row["status"] or "DISCONNECTED",
            "latency_ms": row["latency_ms"] or 0,
            "version": row["version"] or "v1.0",
            "last_sync_at": row["last_sync_at"],
            "config_summary": json.loads(row["config_summary"]) if row["config_summary"] else {},
            "capabilities": json.loads(row["capabilities"]) if row["capabilities"] else [],
        }
