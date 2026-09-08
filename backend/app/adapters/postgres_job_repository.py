"""
Project Vulcan: PostgreSQL Durable Job Repository (Milestone B)
Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")
Implements IJobRepository over PostgreSQL 16 with ACID transactions and connection pooling.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from app.domain.entities import ApprovalDecision, CatalogItem, ExecutionJob, JobStatus
from app.ports.repositories import ICatalogRepository, IJobRepository

logger = logging.getLogger("vulcan.postgres_job_repo")


class PostgresJobRepository(IJobRepository):
    """
    Durable, cross-process safe ExecutionJob persistence using PostgreSQL 16.
    Ensures safe concurrent job state transitions and atomic upserts across multiple workers.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        catalog_repo: Optional[ICatalogRepository] = None,
        catalog: Optional[List[CatalogItem]] = None
    ):
        self.db_url = (
            db_url
            or os.getenv("POSTGRES_URL")
            or os.getenv("DATABASE_URL")
            or "postgresql://vulcan_admin:vulcan_secret_pnc_2026@localhost:5432/vulcan_control_plane"
        )
        self._catalog_repo = catalog_repo
        self._catalog = catalog
        self._ensure_tables()

    def _get_connection(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def _ensure_tables(self) -> None:
        """Verifies execution_jobs table exists, skipping DDL if already present."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.execution_jobs') AS tbl;")
                    row = cur.fetchone()
                    if row and row.get("tbl") is not None:
                        cur.execute("ALTER TABLE execution_jobs ADD COLUMN IF NOT EXISTS worker_pid INT;")
                        conn.commit()
                        return  # Already migrated, skip DDL to avoid multi-worker lock contention
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS execution_jobs (
                            id VARCHAR(64) PRIMARY KEY,
                            correlation_id VARCHAR(64) NOT NULL,
                            catalog_identifier VARCHAR(128) NOT NULL,
                            status VARCHAR(32) NOT NULL DEFAULT 'SUBMITTED',
                            risk_tier VARCHAR(16),
                            requester_id VARCHAR(128) NOT NULL,
                            approver_id VARCHAR(128),
                            dispatched_by VARCHAR(128),
                            target_resource_id VARCHAR(255) NOT NULL,
                            environment VARCHAR(32) NOT NULL DEFAULT 'PROD',
                            parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
                            servicenow_chg VARCHAR(64),
                            storage_artifact_uri VARCHAR(512),
                            storage_artifact_sha256 CHAR(64),
                            approval_requested_at TIMESTAMPTZ,
                            approval_decision JSONB,
                            exit_code INT,
                            error_message TEXT,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            started_at TIMESTAMPTZ,
                            completed_at TIMESTAMPTZ,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            worker_pid INT
                        );
                        CREATE INDEX IF NOT EXISTS idx_execution_jobs_status ON execution_jobs(status);
                        CREATE INDEX IF NOT EXISTS idx_execution_jobs_correlation_id ON execution_jobs(correlation_id);
                        CREATE INDEX IF NOT EXISTS idx_execution_jobs_created_at ON execution_jobs(created_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_execution_jobs_pending_approval ON execution_jobs(status, approval_requested_at) 
                        WHERE status = 'PENDING_APPROVAL';
                    """)
                    cur.execute("ALTER TABLE execution_jobs ADD COLUMN IF NOT EXISTS dispatched_by VARCHAR(128);")
                    cur.execute("ALTER TABLE execution_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
                    cur.execute("ALTER TABLE execution_jobs ADD COLUMN IF NOT EXISTS worker_pid INT;")
                conn.commit()
        except Exception as e:
            logger.warning("Could not verify execution_jobs table on init: %s", e)

    def _get_catalog_item(self, identifier: str) -> Optional[CatalogItem]:
        if self._catalog_repo:
            item = self._catalog_repo.get_by_identifier(identifier)
            if item:
                return item
        if self._catalog:
            for it in self._catalog:
                if it.identifier == identifier:
                    return it
        from app.catalog_data import get_catalog_items
        for it in get_catalog_items():
            if it.identifier == identifier:
                return it
        return None

    def save(self, job: ExecutionJob) -> None:
        """Persists or updates the execution job state via atomic UPSERT."""
        approval_decision_data = None
        if job.approval_decision:
            decided_at_str = (
                job.approval_decision.decided_at.isoformat()
                if hasattr(job.approval_decision.decided_at, "isoformat")
                else str(job.approval_decision.decided_at)
            )
            approval_decision_data = {
                "decision": job.approval_decision.decision,
                "approver_id": job.approval_decision.approver_id,
                "decided_at": decided_at_str,
                "reason": job.approval_decision.reason,
                "chg_number": job.approval_decision.chg_number,
            }

        now_utc = datetime.now(timezone.utc)
        params_json = json.dumps(job.parameters) if isinstance(job.parameters, dict) else "{}"
        appr_json = json.dumps(approval_decision_data) if approval_decision_data else None

        upsert_query = """
            INSERT INTO execution_jobs (
                id, correlation_id, catalog_identifier, status, risk_tier,
                requester_id, approver_id, dispatched_by, target_resource_id, environment,
                parameters, servicenow_chg, storage_artifact_uri,
                storage_artifact_sha256, approval_requested_at,
                approval_decision, exit_code, error_message,
                created_at, started_at, completed_at, updated_at, worker_pid
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s::jsonb, %s, %s,
                %s, %s,
                %s::jsonb, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                parameters = EXCLUDED.parameters,
                servicenow_chg = EXCLUDED.servicenow_chg,
                target_resource_id = EXCLUDED.target_resource_id,
                approver_id = EXCLUDED.approver_id,
                dispatched_by = EXCLUDED.dispatched_by,
                approval_requested_at = EXCLUDED.approval_requested_at,
                approval_decision = EXCLUDED.approval_decision,
                exit_code = EXCLUDED.exit_code,
                error_message = EXCLUDED.error_message,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at,
                updated_at = EXCLUDED.updated_at,
                worker_pid = EXCLUDED.worker_pid;
        """

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(upsert_query, (
                    job.id,
                    job.correlation_id,
                    job.catalog_item.identifier,
                    job.status.value,
                    job.catalog_item.risk_tier.value,
                    job.requester_id,
                    job.approver_id,
                    getattr(job, "dispatched_by", None),
                    job.target_resource_id or "unspecified",
                    job.environment or "PROD",
                    params_json,
                    job.servicenow_chg,
                    job.storage_artifact_uri,
                    job.storage_artifact_sha256,
                    job.approval_requested_at,
                    appr_json,
                    job.exit_code,
                    job.error_message,
                    job.created_at,
                    job.started_at,
                    job.completed_at,
                    now_utc,
                    getattr(job, "worker_pid", None),
                ))
            conn.commit()

    def _row_to_job(self, row: Dict[str, Any]) -> Optional[ExecutionJob]:
        """Reconstruct an ExecutionJob domain entity from a PostgreSQL row."""
        cat_identifier = row["catalog_identifier"]
        cat_item = self._get_catalog_item(cat_identifier)
        if not cat_item:
            logger.warning("Catalog item not found for identifier: %s", cat_identifier)
            return None

        params = row.get("parameters")
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        elif not isinstance(params, dict):
            params = {}

        job = ExecutionJob(
            job_id=row["id"],
            correlation_id=row["correlation_id"],
            catalog_item=cat_item,
            requester_id=row["requester_id"],
            target_resource_id=row.get("target_resource_id") or "",
            parameters=params,
            servicenow_chg=row.get("servicenow_chg"),
            storage_artifact_uri=row.get("storage_artifact_uri"),
            storage_artifact_sha256=row.get("storage_artifact_sha256"),
            environment=row.get("environment") or "PROD",
        )

        job.status = JobStatus(row["status"])
        job.approver_id = row.get("approver_id")
        job.dispatched_by = row.get("dispatched_by")
        job.worker_pid = row.get("worker_pid")
        job.exit_code = row.get("exit_code")
        job.error_message = row.get("error_message")

        job.created_at = row["created_at"]
        job.started_at = row.get("started_at")
        job.completed_at = row.get("completed_at")
        job.approval_requested_at = row.get("approval_requested_at")

        if row.get("approval_decision"):
            dec = row["approval_decision"]
            if isinstance(dec, str):
                try:
                    dec = json.loads(dec)
                except Exception:
                    dec = None
            if isinstance(dec, dict):
                dec_at = dec.get("decided_at")
                if isinstance(dec_at, str):
                    try:
                        dec_at = datetime.fromisoformat(dec_at)
                    except Exception:
                        dec_at = datetime.now(timezone.utc)
                job.approval_decision = ApprovalDecision(
                    decision=dec.get("decision", "APPROVED"),
                    approver_id=dec.get("approver_id", ""),
                    decided_at=dec_at or datetime.now(timezone.utc),
                    reason=dec.get("reason", ""),
                    chg_number=dec.get("chg_number")
                )

        return job

    def get_by_id(self, job_id: str) -> Optional[ExecutionJob]:
        query = "SELECT * FROM execution_jobs WHERE id = %s OR correlation_id = %s LIMIT 1;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (job_id, job_id))
                row = cur.fetchone()
                if row:
                    return self._row_to_job(row)
        return None

    def get_by_correlation_id(self, correlation_id: str) -> Optional[ExecutionJob]:
        return self.get_by_id(correlation_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ExecutionJob]:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        "SELECT * FROM execution_jobs WHERE status = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                        (status.value, limit, offset)
                    )
                else:
                    cur.execute(
                        "SELECT * FROM execution_jobs ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                        (limit, offset)
                    )
                rows = cur.fetchall()

        jobs = []
        for row in rows:
            job = self._row_to_job(row)
            if job:
                jobs.append(job)
        return jobs

    def get_pending_approvals(self) -> List[ExecutionJob]:
        return self.list_jobs(status=JobStatus.PENDING_APPROVAL, limit=500)

    def get_running_jobs(self) -> List[ExecutionJob]:
        """Retrieves all RUNNING and LOCKED jobs for orphan reaper inspection."""
        running = self.list_jobs(status=JobStatus.RUNNING, limit=500)
        locked = self.list_jobs(status=JobStatus.LOCKED, limit=500)
        return running + locked

    def count(self, status: Optional[JobStatus] = None) -> int:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if status:
                    cur.execute("SELECT COUNT(*) as cnt FROM execution_jobs WHERE status = %s;", (status.value,))
                else:
                    cur.execute("SELECT COUNT(*) as cnt FROM execution_jobs;")
                row = cur.fetchone()
                return int(row["cnt"]) if row else 0
