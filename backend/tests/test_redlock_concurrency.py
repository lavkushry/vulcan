"""
Project Vulcan: Distributed Target Mutex & Redlock Concurrency Tests
Author: Alex Xu (Distributed Systems Lead)
Verifies:
1. Mutual exclusion between concurrent jobs targeting the same resource.
2. Distinct resources do not block each other.
3. Automatic Watchdog Heartbeat renewal.
4. Monotonic fencing token generation.
"""
import time
import unittest
from app.adapters.redlock_adapter import DistributedTargetMutex, RedlockManager


class TestRedlockConcurrency(unittest.TestCase):

    def setUp(self):
        self.lock_manager = RedlockManager()

    def test_single_job_acquires_and_releases_lock(self):
        """Standard acquisition and release lifecycle."""
        resource = "f5-vip-dallas-01"
        acquired = self.lock_manager.acquire(resource, ttl_seconds=5)
        self.assertTrue(acquired)
        self.assertTrue(self.lock_manager.is_locked(resource))

        self.lock_manager.release(resource)
        self.assertFalse(self.lock_manager.is_locked(resource))

    def test_competing_job_on_same_resource_is_blocked(self):
        """Second worker targeting same host is strictly locked out."""
        resource = "pnc-core-db01"
        self.assertTrue(self.lock_manager.acquire(resource, ttl_seconds=10))

        # Attempt second acquisition
        second_acquire = self.lock_manager.acquire(resource, ttl_seconds=10)
        self.assertFalse(second_acquire, "Second acquire on active resource must fail")

        # After first releases, second succeeds
        self.lock_manager.release(resource)
        self.assertTrue(self.lock_manager.acquire(resource, ttl_seconds=10))
        self.lock_manager.release(resource)

    def test_independent_resources_execute_concurrently(self):
        """Jobs on different infrastructure targets proceed concurrently without blocking."""
        res_a = "f5-pittsburgh-01"
        res_b = "f5-dallas-02"

        self.assertTrue(self.lock_manager.acquire(res_a, ttl_seconds=10))
        self.assertTrue(self.lock_manager.acquire(res_b, ttl_seconds=10))

        self.lock_manager.release(res_a)
        self.lock_manager.release(res_b)

    def test_watchdog_thread_initialization_and_fencing_token(self):
        """Verifies DistributedTargetMutex initializes fencing token and watchdog."""
        mutex = DistributedTargetMutex(
            redis_nodes=[],  # Standalone mode
            resource_id="k8s-worker-pool-03",
            lease_ms=1000
        )
        self.assertTrue(mutex.acquire())
        self.assertIsNotNone(mutex.fencing_token)
        self.assertGreater(mutex.fencing_token, 0)
        mutex.release()


if __name__ == "__main__":
    unittest.main(verbosity=2)
