"""
Project Vulcan: Redis Streams & In-Memory Decoupled Job Queue Adapters (BKND-18)
Author: Alex Xu (Distributed Systems Lead)
Enforces decoupled asynchronous job dispatch with consumer groups, at-least-once delivery,
and stale worker auto-claim recovery.
"""
import json
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.ports.interfaces import IJobQueue, JobQueueMessage

logger = logging.getLogger("vulcan.queue")


def _normalize_priority(priority: Any) -> int:
    if isinstance(priority, int):
        return priority
    if hasattr(priority, "value"):
        priority = priority.value
    if isinstance(priority, str):
        mapping = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
        return mapping.get(priority.upper(), 0)
    try:
        return int(priority)
    except Exception:
        return 0


class RedisJobQueue(IJobQueue):
    """
    Durable Redis Streams job dispatch queue with consumer groups.
    Stream: vulcan:jobs:dispatch
    Consumer Group: vulcan:workers
    """

    def __init__(
        self,
        redis_client: Any,
        stream_name: str = "vulcan:jobs:dispatch",
        group_name: str = "vulcan:workers"
    ):
        self.redis = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self._ensure_consumer_group()

    def _ensure_consumer_group(self) -> None:
        """Idempotently ensures the Redis Stream and Consumer Group exist."""
        try:
            # MKSTREAM creates the stream if it does not exist
            self.redis.xgroup_create(self.stream_name, self.group_name, id="$", mkstream=True)
            logger.info("Created Redis consumer group '%s' on stream '%s'", self.group_name, self.stream_name)
        except Exception as e:
            # Group already exists (BUSYGROUP) is normal and expected
            err_msg = str(e)
            if "BUSYGROUP" in err_msg:
                logger.debug("Redis consumer group '%s' already exists", self.group_name)
            else:
                logger.warning("Could not create Redis consumer group: %s", e)

    def enqueue(
        self,
        job_id: str,
        correlation_id: str,
        priority: int = 0,
        payload: Optional[Dict[str, Any]] = None
    ) -> str:
        """Pushes job metadata into Redis Stream."""
        p_int = _normalize_priority(priority)
        now = datetime.now(timezone.utc)
        data = {
            "job_id": job_id,
            "correlation_id": correlation_id,
            "enqueued_at": now.isoformat(),
            "priority": str(p_int),
            "retry_count": "0",
            "payload": json.dumps(payload or {})
        }
        raw_id = self.redis.xadd(self.stream_name, data)
        msg_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
        logger.info("Enqueued job [%s / %s] to stream '%s' with msg_id [%s]", job_id, correlation_id, self.stream_name, msg_id)
        return msg_id

    def dequeue(self, worker_id: str, timeout_seconds: float = 1.0) -> Optional[JobQueueMessage]:
        """
        Reads next unassigned message for worker_id from consumer group.
        Blocks up to timeout_seconds.
        """
        block_ms = max(50, int(timeout_seconds * 1000))
        try:
            response = self.redis.xreadgroup(
                self.group_name,
                worker_id,
                {self.stream_name: ">"},
                count=1,
                block=block_ms
            )
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                return None
            logger.warning("Error reading from Redis Stream '%s': %s", self.stream_name, e)
            return None

        if not response:
            return None

        for stream, messages in response:
            for raw_msg_id, fields in messages:
                msg_id = raw_msg_id.decode("utf-8") if isinstance(raw_msg_id, bytes) else str(raw_msg_id)
                decoded_fields = {}
                for k, v in fields.items():
                    key = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                    val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                    decoded_fields[key] = val

                try:
                    payload = json.loads(decoded_fields.get("payload", "{}"))
                except Exception:
                    payload = {}

                try:
                    enqueued_at = datetime.fromisoformat(decoded_fields.get("enqueued_at", datetime.now(timezone.utc).isoformat()))
                except Exception:
                    enqueued_at = datetime.now(timezone.utc)

                return JobQueueMessage(
                    message_id=msg_id,
                    job_id=decoded_fields.get("job_id", ""),
                    correlation_id=decoded_fields.get("correlation_id", ""),
                    enqueued_at=enqueued_at,
                    priority=int(decoded_fields.get("priority", 0)),
                    retry_count=int(decoded_fields.get("retry_count", 0)),
                    payload=payload
                )

        return None

    def ack(self, message_id: str) -> bool:
        """Acknowledges processing completion and removes from PEL."""
        try:
            res = self.redis.xack(self.stream_name, self.group_name, message_id)
            return bool(res > 0)
        except Exception as e:
            logger.warning("Failed to XACK message [%s]: %s", message_id, e)
            return False

    def nack(self, message_id: str, requeue: bool = True) -> bool:
        """Negative acknowledgment; leaves in PEL for retry or deletes."""
        if not requeue:
            return self.ack(message_id)
        return True

    def requeue_stale(self, min_idle_ms: int = 60000, worker_id: str = "recovery_reaper") -> List[JobQueueMessage]:
        """
        Reclaims orphaned jobs from dead workers using XAUTOCLAIM.
        """
        claimed_messages: List[JobQueueMessage] = []
        try:
            if hasattr(self.redis, "xautoclaim"):
                start_id = "0-0"
                while True:
                    result = self.redis.xautoclaim(
                        self.stream_name,
                        self.group_name,
                        worker_id,
                        min_idle_time=min_idle_ms,
                        start_id=start_id,
                        count=10
                    )
                    next_id = result[0]
                    messages = result[1]
                    if not messages:
                        break
                    for raw_msg_id, fields in messages:
                        msg_id = raw_msg_id.decode("utf-8") if isinstance(raw_msg_id, bytes) else str(raw_msg_id)
                        decoded_fields = {}
                        for k, v in fields.items():
                            key = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                            val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                            decoded_fields[key] = val
                        try:
                            payload = json.loads(decoded_fields.get("payload", "{}"))
                        except Exception:
                            payload = {}
                        claimed_messages.append(JobQueueMessage(
                            message_id=msg_id,
                            job_id=decoded_fields.get("job_id", ""),
                            correlation_id=decoded_fields.get("correlation_id", ""),
                            enqueued_at=datetime.now(timezone.utc),
                            priority=int(decoded_fields.get("priority", 0)),
                            retry_count=int(decoded_fields.get("retry_count", 0)) + 1,
                            payload=payload
                        ))
                    if next_id in ("0-0", b"0-0") or len(messages) < 10:
                        break
                    start_id = next_id
        except Exception as e:
            logger.debug("xautoclaim not supported or failed: %s", e)

        return claimed_messages

    def queue_depth(self) -> int:
        """Returns the length of the Redis Stream."""
        try:
            return int(self.redis.xlen(self.stream_name))
        except Exception:
            return 0


class InMemoryJobQueue(IJobQueue):
    """
    Thread-safe in-memory queue fallback for offline CI/CD, hermetic unit tests,
    and single-process development.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def enqueue(
        self,
        job_id: str,
        correlation_id: str,
        priority: int = 0,
        payload: Optional[Dict[str, Any]] = None
    ) -> str:
        p_int = _normalize_priority(priority)
        msg_id = f"inmem-msg-{uuid.uuid4().hex[:8]}"
        msg = JobQueueMessage(
            message_id=msg_id,
            job_id=job_id,
            correlation_id=correlation_id,
            enqueued_at=datetime.now(timezone.utc),
            priority=p_int,
            retry_count=0,
            payload=payload or {}
        )
        self._queue.put(msg)
        return msg_id

    def dequeue(self, worker_id: str, timeout_seconds: float = 2.0) -> Optional[JobQueueMessage]:
        try:
            msg: JobQueueMessage = self._queue.get(timeout=timeout_seconds)
            with self._lock:
                self._pending[msg.message_id] = {
                    "message": msg,
                    "worker_id": worker_id,
                    "claimed_at": time.time()
                }
            return msg
        except queue.Empty:
            return None

    def ack(self, message_id: str) -> bool:
        with self._lock:
            if message_id in self._pending:
                del self._pending[message_id]
                return True
        return False

    def nack(self, message_id: str, requeue: bool = True) -> bool:
        with self._lock:
            if message_id in self._pending:
                entry = self._pending.pop(message_id)
                if requeue:
                    msg = entry["message"]
                    msg.retry_count += 1
                    self._queue.put(msg)
                return True
        return False

    def requeue_stale(self, min_idle_ms: int = 60000, worker_id: str = "recovery_reaper") -> List[JobQueueMessage]:
        reclaimed = []
        now = time.time()
        idle_seconds = min_idle_ms / 1000.0
        with self._lock:
            to_remove = []
            for msg_id, data in self._pending.items():
                if now - data["claimed_at"] >= idle_seconds:
                    to_remove.append(msg_id)
                    msg = data["message"]
                    msg.retry_count += 1
                    self._queue.put(msg)
                    reclaimed.append(msg)
            for msg_id in to_remove:
                del self._pending[msg_id]
        return reclaimed

    def queue_depth(self) -> int:
        with self._lock:
            return self._queue.qsize() + len(self._pending)
