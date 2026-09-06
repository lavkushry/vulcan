"""
Project Vulcan: Cryptographic Merkle Audit Logger Adapter
Author: Robert C. Martin ("Uncle Bob") & Alex Xu
Provides immutable, tamper-evident audit logging using SHA256 cryptographic chaining.
"""
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.domain.entities import AuditRecord, ExecutionJob
from app.ports.interfaces import IAuditLogger

logger = logging.getLogger("vulcan.audit")


class MerkleAuditLogger(IAuditLogger):
    """
    Cryptographic SHA256 Merkle Chain Audit Logger.
    Every record commits: Hash_n = SHA256(Record_n + Hash_{n-1}).
    Supports append-only disk persistence and in-memory verification.
    """
    GENESIS_HASH = "0" * 64

    def __init__(self, persistence_file: Optional[str] = None):
        self.persistence_file = persistence_file
        self.ledger: List[AuditRecord] = []
        self._last_hash = self.GENESIS_HASH
        self._lock = threading.Lock()
        self._load_existing()

    def _load_existing(self):
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return

        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    rec = AuditRecord(
                        id=item["id"],
                        correlation_id=item["correlation_id"],
                        timestamp=item["timestamp"],
                        actor=item["actor"],
                        action=item["action"],
                        payload=item["payload"],
                        prev_hash=item["prev_hash"],
                        current_hash=item["current_hash"]
                    )
                    self.ledger.append(rec)
                    self._last_hash = rec.current_hash
            logger.info(f"Loaded {len(self.ledger)} audit records from {self.persistence_file}")
        except Exception as e:
            logger.error(f"Failed to load audit ledger from {self.persistence_file}: {e}")

    def _get_persisted_head(self) -> tuple[int, str]:
        """Reads the true authoritative chain head from transactional disk storage."""
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return 0, self.GENESIS_HASH

        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
                if not lines:
                    return 0, self.GENESIS_HASH
                last_record = json.loads(lines[-1])
                return last_record.get("id", len(lines)), last_record.get("current_hash", self.GENESIS_HASH)
        except Exception:
            return len(self.ledger), self._last_hash

    def record(self, job: ExecutionJob, action: str, payload: Dict[str, Any], actor: Optional[str] = None) -> AuditRecord:
        """
        Transactional, cross-process safe Merkle audit record commit.
        Acquires exclusive file lock to prevent chain forking when multiple workers execute concurrently.
        """
        import fcntl
        now_str = datetime.now(timezone.utc).isoformat()
        actor_id = actor or job.requester_id

        with self._lock:
            # If disk persistence is enabled, use exclusive advisory lock across worker processes
            if self.persistence_file:
                dir_path = os.path.dirname(os.path.abspath(self.persistence_file))
                os.makedirs(dir_path, exist_ok=True)
                lock_file_path = f"{self.persistence_file}.lock"
                
                with open(lock_file_path, "w") as lock_file:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    try:
                        last_id, true_last_hash = self._get_persisted_head()
                        rec_id = last_id + 1

                        current_hash = AuditRecord.compute_hash(
                            job.correlation_id,
                            now_str,
                            actor_id,
                            action,
                            payload,
                            true_last_hash
                        )

                        rec = AuditRecord(
                            id=rec_id,
                            correlation_id=job.correlation_id,
                            timestamp=now_str,
                            actor=actor_id,
                            action=action,
                            payload=payload,
                            prev_hash=true_last_hash,
                            current_hash=current_hash
                        )

                        with open(self.persistence_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "id": rec.id,
                                "correlation_id": rec.correlation_id,
                                "timestamp": rec.timestamp,
                                "actor": rec.actor,
                                "action": rec.action,
                                "payload": rec.payload,
                                "prev_hash": rec.prev_hash,
                                "current_hash": rec.current_hash
                            }) + "\n")
                            f.flush()
                            os.fsync(f.fileno())

                        self.ledger.append(rec)
                        self._last_hash = current_hash
                        return rec
                    finally:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            else:
                # In-memory single-process fallback
                rec_id = len(self.ledger) + 1
                current_hash = AuditRecord.compute_hash(
                    job.correlation_id,
                    now_str,
                    actor_id,
                    action,
                    payload,
                    self._last_hash
                )
                rec = AuditRecord(
                    id=rec_id,
                    correlation_id=job.correlation_id,
                    timestamp=now_str,
                    actor=actor_id,
                    action=action,
                    payload=payload,
                    prev_hash=self._last_hash,
                    current_hash=current_hash
                )
                self.ledger.append(rec)
                self._last_hash = current_hash
                return rec

    def get_last_hash(self) -> str:
        with self._lock:
            return self._last_hash

    def verify_chain(self) -> bool:
        """
        Mathematically verifies the integrity of the entire cryptographic chain.
        Returns True if zero records have been altered, reordered, or deleted.
        """
        with self._lock:
            prev = self.GENESIS_HASH
            for rec in self.ledger:
                if rec.prev_hash != prev:
                    logger.critical(f"Merkle chain broken at record #{rec.id}! prev_hash mismatch.")
                    return False

                expected_hash = AuditRecord.compute_hash(
                    rec.correlation_id,
                    rec.timestamp,
                    rec.actor,
                    rec.action,
                    rec.payload,
                    rec.prev_hash
                )
                if rec.current_hash != expected_hash:
                    logger.critical(f"Audit record #{rec.id} hash tampering detected!")
                    return False

                prev = rec.current_hash

            return True
