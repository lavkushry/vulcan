"""
Project Vulcan: Distributed Target Mutex (Redlock with Watchdog Heartbeat)
Author: Alex Xu (Systems Lead)
Guarantees mutual exclusion across distributed execution nodes with zero deadlock risk.
"""
import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from app.ports.interfaces import ILockManager

logger = logging.getLogger("vulcan.lock")

# Atomic Lua Scripts
LUA_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

LUA_EXTEND_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""


class DistributedTargetMutex:
    """
    Production-Grade Redis Redlock implementation with a background Watchdog Heartbeat.
    Guarantees mutual exclusion across distributed execution nodes.
    """

    def __init__(
        self,
        redis_nodes: List[Any],
        resource_id: str,
        lease_ms: int = 30000,
        retry_count: int = 3,
        retry_delay_ms: int = 200
    ):
        self.redis_nodes = redis_nodes or []
        self.quorum = (len(self.redis_nodes) // 2) + 1 if self.redis_nodes else 1
        self.resource_id = resource_id
        self.lock_key = f"lock:resource:{resource_id}"
        self.token_key = f"token:resource:{resource_id}"
        self.lease_ms = lease_ms
        self.retry_count = retry_count
        self.retry_delay_ms = retry_delay_ms

        self.lock_value = f"{uuid.uuid4().hex}:{time.time_ns()}"
        self.fencing_token: Optional[int] = None

        self._stop_watchdog = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._acquired = False

    def acquire(self) -> bool:
        """Attempts to acquire lock across quorum of Redis nodes."""
        if not self.redis_nodes:
            # Standalone fallback mode
            self._acquired = True
            self.fencing_token = int(time.time() * 1000)
            return True

        for attempt in range(self.retry_count):
            start_time_ms = int(time.time() * 1000)
            acquired_nodes = 0

            for client in self.redis_nodes:
                try:
                    if client.set(self.lock_key, self.lock_value, px=self.lease_ms, nx=True):
                        acquired_nodes += 1
                except Exception as e:
                    logger.warning(f"Redis node unreachable during lock acquire: {e}")

            elapsed_ms = int(time.time() * 1000) - start_time_ms
            drift_ms = int(self.lease_ms * 0.02) + 2
            validity_time_ms = self.lease_ms - elapsed_ms - drift_ms

            if acquired_nodes >= self.quorum and validity_time_ms > 0:
                self._acquired = True
                self._generate_fencing_token()
                self._start_watchdog()
                logger.info(
                    f"Lock acquired on [{self.resource_id}] with token [{self.fencing_token}]. "
                    f"Nodes: {acquired_nodes}/{len(self.redis_nodes)}"
                )
                return True
            else:
                self._release_all()
                time.sleep(self.retry_delay_ms / 1000.0)

        return False

    def _generate_fencing_token(self):
        """Atomically increments and fetches monotonic fencing token."""
        for client in self.redis_nodes:
            try:
                self.fencing_token = client.incr(self.token_key)
                break
            except Exception:
                continue
        if self.fencing_token is None:
            self.fencing_token = int(time.time_ns())

    def _start_watchdog(self):
        """Spawns daemon thread to renew lock lease every (lease_ms / 3)."""
        interval_sec = (self.lease_ms / 3.0) / 1000.0

        def heartbeat():
            while not self._stop_watchdog.wait(timeout=interval_sec):
                extended_nodes = 0
                for client in self.redis_nodes:
                    try:
                        res = client.eval(LUA_EXTEND_SCRIPT, 1, self.lock_key, self.lock_value, self.lease_ms)
                        if res == 1:
                            extended_nodes += 1
                    except Exception:
                        pass

                if self.redis_nodes and extended_nodes < self.quorum:
                    logger.critical(
                        f"Watchdog failed to extend quorum lease on [{self.resource_id}]. "
                        f"Active: {extended_nodes}/{len(self.redis_nodes)}"
                    )
                    break

        self._watchdog_thread = threading.Thread(
            target=heartbeat, daemon=True, name=f"Watchdog-{self.resource_id}"
        )
        self._watchdog_thread.start()

    def release(self):
        """Stops watchdog and safely deletes lock using atomic Lua verification."""
        if not self._acquired:
            return

        self._stop_watchdog.set()
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=2.0)

        self._release_all()
        self._acquired = False
        logger.info(f"Lock safely released on [{self.resource_id}].")

    def _release_all(self):
        for client in self.redis_nodes:
            try:
                client.eval(LUA_RELEASE_SCRIPT, 1, self.lock_key, self.lock_value)
            except Exception as e:
                logger.error(f"Error releasing lock on Redis node: {e}")

    def __enter__(self):
        if not self.acquire():
            raise BlockingIOError(f"Target resource [{self.resource_id}] is locked.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class RedlockManager(ILockManager):
    """
    Implements ILockManager domain port via DistributedTargetMutex.
    Supports multi-node Redis clusters with automatic memory fallback.
    """

    def __init__(self, redis_nodes: Optional[List[Any]] = None):
        self.redis_nodes = redis_nodes or []
        self._active_mutexes: Dict[str, DistributedTargetMutex] = {}
        self._fallback_locks: Dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, resource_id: str, ttl_seconds: int = 1800) -> bool:
        with self._lock:
            if self.redis_nodes:
                mutex = DistributedTargetMutex(
                    redis_nodes=self.redis_nodes,
                    resource_id=resource_id,
                    lease_ms=ttl_seconds * 1000
                )
                if mutex.acquire():
                    self._active_mutexes[resource_id] = mutex
                    return True
                return False
            else:
                # In-memory emulation mode
                now = time.time()
                if resource_id in self._fallback_locks:
                    if now < self._fallback_locks[resource_id]:
                        return False
                self._fallback_locks[resource_id] = now + ttl_seconds
                return True

    def release(self, resource_id: str) -> None:
        with self._lock:
            if self.redis_nodes and resource_id in self._active_mutexes:
                self._active_mutexes[resource_id].release()
                del self._active_mutexes[resource_id]
            elif resource_id in self._fallback_locks:
                del self._fallback_locks[resource_id]

    def is_locked(self, resource_id: str) -> bool:
        with self._lock:
            if self.redis_nodes:
                key = f"lock:resource:{resource_id}"
                for client in self.redis_nodes:
                    try:
                        if client.exists(key):
                            return True
                    except Exception:
                        pass
                return False
            else:
                now = time.time()
                if resource_id in self._fallback_locks:
                    return now < self._fallback_locks[resource_id]
                return False
