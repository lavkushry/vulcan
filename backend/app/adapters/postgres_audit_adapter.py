"""
Project Vulcan: PostgreSQL Merkle Audit Ledger Adapter (Milestone B)
Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")
Implements IAuditLedgerRepository and IAuditLogger over PostgreSQL 16.
Replaces file-based fcntl locks with PostgreSQL ACID row-level locking (FOR UPDATE)
for tamper-evident, cross-process safe Merkle hash chaining.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from app.domain.entities import AuditRecord, ExecutionJob
from app.ports.interfaces import IAuditLogger
from app.ports.repositories import IAuditLedgerRepository

logger = logging.getLogger("vulcan.postgres_audit")


class PostgresAuditAdapter(IAuditLedgerRepository, IAuditLogger):
    """
    Cryptographic SHA-256 Merkle Chain Audit Ledger backed by PostgreSQL 16.
    Uses PostgreSQL transaction row-level locking (FOR UPDATE) to guarantee
    strictly sequential hash chaining across multiple concurrent workers.
    """
    GENESIS_HASH = "0" * 64

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = (
            db_url
            or os.getenv("POSTGRES_URL")
            or os.getenv("DATABASE_URL")
            or f"postgresql://{os.getenv('POSTGRES_USER', 'vulcan_admin')}@{os.getenv('POSTGRES_HOST', 'localhost')}:5432/{os.getenv('POSTGRES_DB', 'vulcan_control_plane')}"
        )

        self._ensure_tables()

    def _get_connection(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def _ensure_tables(self) -> None:
        """Verifies audit_ledger table and indexes exist in PostgreSQL, skipping if present."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.audit_ledger') AS tbl;")
                    row = cur.fetchone()
                    if row and row.get("tbl") is not None:
                        return  # Already migrated, skip DDL to avoid multi-worker lock contention
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS audit_ledger (
                            id BIGSERIAL PRIMARY KEY,
                            correlation_id VARCHAR(64) NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            actor VARCHAR(128) NOT NULL,
                            action VARCHAR(64) NOT NULL,
                            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                            prev_hash CHAR(64) NOT NULL,
                            current_hash CHAR(64) NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                        CREATE INDEX IF NOT EXISTS idx_audit_ledger_correlation ON audit_ledger(correlation_id);
                        CREATE INDEX IF NOT EXISTS idx_audit_ledger_timestamp ON audit_ledger(timestamp DESC);
                        CREATE INDEX IF NOT EXISTS idx_audit_ledger_current_hash ON audit_ledger(current_hash);
                    """)
                conn.commit()
        except Exception as e:
            logger.warning("Could not verify audit_ledger table on init: %s", e)

    def record(
        self,
        job: ExecutionJob,
        action: str,
        payload: Dict[str, Any],
        actor: Optional[str] = None
    ) -> AuditRecord:
        """
        Synchronously commits an audit record under an exclusive row lock.
        Implements IAuditLogger port.
        """
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        actor_id = actor or getattr(job, "dispatched_by", None) or job.requester_id or "system"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Advisory lock or row-level lock on the ledger head to guarantee strictly sequential chaining
                cur.execute("SELECT id, current_hash FROM audit_ledger ORDER BY id DESC LIMIT 1 FOR UPDATE;")
                last_row = cur.fetchone()

                if last_row:
                    prev_hash = last_row["current_hash"]
                    next_id = int(last_row["id"]) + 1
                else:
                    prev_hash = self.GENESIS_HASH
                    next_id = 1

                current_hash = AuditRecord.compute_hash(
                    correlation_id=job.correlation_id,
                    timestamp=now_str,
                    actor=actor_id,
                    action=action,
                    payload=payload,
                    prev_hash=prev_hash
                )

                cur.execute("""
                    INSERT INTO audit_ledger (
                        id, correlation_id, timestamp, actor, action,
                        payload, prev_hash, current_hash, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s);
                """, (
                    next_id,
                    job.correlation_id,
                    now,
                    actor_id,
                    action,
                    json.dumps(payload),
                    prev_hash,
                    current_hash,
                    now
                ))
            conn.commit()

        record = AuditRecord(
            id=next_id,
            correlation_id=job.correlation_id,
            timestamp=now_str,
            actor=actor_id,
            action=action,
            payload=payload,
            prev_hash=prev_hash,
            current_hash=current_hash
        )
        logger.info(
            "Committed Merkle audit record #%d [%s] for job %s (hash: %s...)",
            next_id, action, job.correlation_id, current_hash[:12]
        )
        return record

    def append(self, record: AuditRecord) -> None:
        """
        Atomically appends a pre-computed audit record.
        Implements IAuditLedgerRepository port.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_ledger (
                        id, correlation_id, timestamp, actor, action,
                        payload, prev_hash, current_hash, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
                    ON CONFLICT (id) DO NOTHING;
                """, (
                    record.id,
                    record.correlation_id,
                    record.timestamp,
                    record.actor,
                    record.action,
                    json.dumps(record.payload),
                    record.prev_hash,
                    record.current_hash
                ))
            conn.commit()

    def get_last_hash(self) -> str:
        """Return the current tip of the Merkle hash chain."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_hash FROM audit_ledger ORDER BY id DESC LIMIT 1;")
                row = cur.fetchone()
                if row:
                    return str(row["current_hash"]).strip()
        return self.GENESIS_HASH

    def get_chain(self, correlation_id: Optional[str] = None) -> List[AuditRecord]:
        """Retrieves the complete audit record chain or a subset by correlation ID."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if correlation_id:
                    cur.execute(
                        "SELECT * FROM audit_ledger WHERE correlation_id = %s ORDER BY id ASC;",
                        (correlation_id,)
                    )
                else:
                    cur.execute("SELECT * FROM audit_ledger ORDER BY id ASC;")
                rows = cur.fetchall()

        records = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            elif not isinstance(payload, dict):
                payload = {}

            ts_str = row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"])

            records.append(AuditRecord(
                id=int(row["id"]),
                correlation_id=row["correlation_id"],
                timestamp=ts_str,
                actor=row["actor"],
                action=row["action"],
                payload=payload,
                prev_hash=str(row["prev_hash"]).strip(),
                current_hash=str(row["current_hash"]).strip()
            ))
        return records

    def verify_integrity(self, window: Optional[int] = None) -> bool:
        """
        Validates the SHA-256 hash chain from genesis (or window) to head.
        Recalculates every block's cryptographic hash and checks link integrity.
        """
        if window:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM audit_ledger ORDER BY id DESC LIMIT %s;", (window,))
                    rows = cur.fetchall()
            if not rows:
                return True
            rows.reverse()
            chain = []
            for row in rows:
                payload = row["payload"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                chain.append(AuditRecord(
                    id=int(row["id"]),
                    correlation_id=row["correlation_id"],
                    timestamp=row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"]),
                    actor=row["actor"],
                    action=row["action"],
                    payload=payload,
                    prev_hash=row["prev_hash"],
                    current_hash=row["current_hash"]
                ))
            expected_prev = chain[0].prev_hash
        else:
            chain = self.get_chain()
            if not chain:
                return True
            expected_prev = self.GENESIS_HASH

        for idx, rec in enumerate(chain):
            # 1. Verify link to previous block
            if rec.prev_hash != expected_prev:
                logger.error(
                    "Merkle chain break at record #%d: prev_hash '%s' != expected '%s'",
                    rec.id, rec.prev_hash, expected_prev
                )
                return False

            # 2. Recalculate block hash
            calculated = AuditRecord.compute_hash(
                correlation_id=rec.correlation_id,
                timestamp=rec.timestamp,
                actor=rec.actor,
                action=rec.action,
                payload=rec.payload,
                prev_hash=rec.prev_hash
            )
            if calculated != rec.current_hash:
                logger.error(
                    "Merkle hash mismatch at record #%d: current_hash '%s' != calculated '%s'",
                    rec.id, rec.current_hash, calculated
                )
                return False

            expected_prev = rec.current_hash

        return True

    def verify_chain(self, window: int = 50) -> bool:
        """Alias for verify_integrity implementing IAuditLogger port with 10s TTL cache and 50-block sliding window."""
        now = time.time()
        if now - getattr(self, "_last_verify_time", 0.0) < 10.0:
            return getattr(self, "_last_verify_result", True)
        res = self.verify_integrity(window=window)
        self._last_verify_time = now
        self._last_verify_result = res
        return res

    @property
    def ledger(self) -> List[AuditRecord]:
        """Provides uniform interface compatibility with MerkleAuditLogger."""
        return self.get_chain()

    @property
    def records(self) -> List[AuditRecord]:
        """Provides uniform interface compatibility with test audit loggers."""
        return self.get_chain()
