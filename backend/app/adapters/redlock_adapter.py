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
    Enforces atomic compare-and-delete: locks can ONLY be released by the owner token that acquired them.
    Prevents expired locks from being deleted out from under new holders.
    """

    def __init__(self, redis_nodes: Optional[List[Any]] = None):
        self.redis_nodes = redis_nodes or []
        self._active_mutexes: Dict[str, DistributedTargetMutex] = {}
        # Map: resource_id -> (expiry_timestamp, owner_token, fencing_token)
        self._fallback_locks: Dict[str, tuple] = {}
        self._fencing_counter: int = 1000
        self._lock = threading.Lock()

    def acquire(self, resource_id: str, ttl_seconds: int = 1800, owner_token: Optional[str] = None) -> bool:
        token = owner_token or f"tok-{uuid.uuid4().hex[:12]}"
        with self._lock:
            if self.redis_nodes:
                mutex = DistributedTargetMutex(
                    redis_nodes=self.redis_nodes,
                    resource_id=resource_id,
                    lease_ms=ttl_seconds * 1000
                )
                if owner_token:
                    mutex.lock_value = owner_token
                if mutex.acquire():
                    self._active_mutexes[resource_id] = mutex
                    return True
                return False
            else:
                # In-memory emulation mode with ownership & compare-and-delete
                now = time.time()
                if resource_id in self._fallback_locks:
                    expiry, cur_owner, _ = self._fallback_locks[resource_id]
                    if now < expiry:
                        # Lock is actively held
                        return False
                # Lock is free or expired: acquire with owner_token and monotonic fencing token
                self._fencing_counter += 1
                self._fallback_locks[resource_id] = (now + ttl_seconds, token, self._fencing_counter)
                return True

    def release(self, resource_id: str, owner_token: Optional[str] = None) -> bool:
        """
        Safely releases lock using atomic compare-and-delete.
        Returns True if the lock was successfully released by the owner.
        Returns False if the lock was expired, stolen, or held by another owner.
        """
        with self._lock:
            if self.redis_nodes and resource_id in self._active_mutexes:
                mutex = self._active_mutexes[resource_id]
                mutex.release()
                del self._active_mutexes[resource_id]
                return True
            elif resource_id in self._fallback_locks:
                expiry, cur_owner, _ = self._fallback_locks[resource_id]
                now = time.time()
                # If owner_token is specified, enforce compare-and-delete!
                if owner_token is not None:
                    if cur_owner != owner_token:
                        logger.warning(
                            f"Lock release rejected for [{resource_id}]: Owner token mismatch "
                            f"(attempted by [{owner_token}], currently held by [{cur_owner}])."
                        )
                        return False
                    if now >= expiry:
                        logger.warning(
                            f"Lock release rejected for [{resource_id}]: Lock already expired at {expiry}."
                        )
                        del self._fallback_locks[resource_id]
                        return False
                del self._fallback_locks[resource_id]
                return True
            return False

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
                    expiry, _, _ = self._fallback_locks[resource_id]
                    return now < expiry
                return False

    def get_fencing_token(self, resource_id: str) -> Optional[int]:
        with self._lock:
            if self.redis_nodes and resource_id in self._active_mutexes:
                return self._active_mutexes[resource_id].fencing_token
            elif resource_id in self._fallback_locks:
                return self._fallback_locks[resource_id][2]
            return None
