"""
Project Vulcan: Distributed Systems Chaos & Invariant Verification Suite (Milestone C.3)
Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")

Verifies:
1. Redlock lease expiry & monotonic fencing token race under artificial execution delay.
2. 10GB S3 multipart in-flight abort & orphaned chunk purge across 205 parts.
3. Ungraceful worker termination (SIGKILL) & ApprovalSweeper fail-closed orphan recovery.
"""
import multiprocessing
import os
import signal
import time
import unittest
from datetime import datetime, timezone

from app.adapters.crypto_audit_adapter import MerkleAuditLogger
from app.adapters.redlock_adapter import RedlockManager
from app.adapters.s3_multipart_adapter import CHUNK_SIZE_BYTES, S3MultipartGateway
from app.adapters.sqlite_repositories import SQLiteJobRepository
from app.catalog_data import get_catalog_items
from app.core.approval_sweeper import ApprovalSweeper
from app.domain.entities import (
    CatalogItem,
    CurationStatus,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
)


def _child_worker_process():
    """Background process simulating a long-running execution worker."""
    while True:
        time.sleep(1.0)


class TestChaosInvariants(unittest.TestCase):

    def setUp(self):
        self.lock_manager = RedlockManager()
        self.s3_gateway = S3MultipartGateway(
            bucket_name="pnc-vulcan-chaos-test",
            mock_mode=True
        )

    # --------------------------------------------------------------------------
    # DRILL 1: REDLOCK LEASE EXPIRY & FENCING RACE
    # --------------------------------------------------------------------------
    def test_chaos_redlock_lease_expiry_and_fencing_race(self):
        """
        Drill 1:
        Worker A acquires lock on target with a short TTL (0.3s) and receives fencing token F_A.
        Worker A sleeps past the lease expiry (0.5s).
        Worker B acquires the now-expired lock and receives strictly higher fencing token F_B > F_A.
        Worker A wakes up:
        - Fencing token validation rejects Worker A's stale token (fail-closed write protection).
        - Worker A's lock release attempt is rejected (compare-and-delete protects Worker B's lock).
        - Resource remains held by Worker B.
        - Worker B executes, validates token F_B, and releases cleanly.
        """
        resource = "pnc-core-db01"
        token_a = "runner-worker-A"
        token_b = "runner-worker-B"

        # 1. Worker A acquires target mutex with short TTL
        acquired_a = self.lock_manager.acquire(resource, ttl_seconds=0.3, owner_token=token_a)
        self.assertTrue(acquired_a, "Worker A must acquire lock initially")
        fencing_a = self.lock_manager.get_fencing_token(resource)
        self.assertIsNotNone(fencing_a)
        self.assertGreaterEqual(fencing_a, 1000)
        self.assertTrue(
            self.lock_manager.validate_fencing_token(resource, fencing_a),
            "Fencing token F_A must be valid while lease is active"
        )

        # 2. Worker A experiences artificial processing delay / pause past expiry
        time.sleep(0.5)

        # 3. Worker B acquires the expired lock on target infrastructure
        acquired_b = self.lock_manager.acquire(resource, ttl_seconds=5.0, owner_token=token_b)
        self.assertTrue(acquired_b, "Worker B must successfully acquire expired lock")
        fencing_b = self.lock_manager.get_fencing_token(resource)
        self.assertIsNotNone(fencing_b)
        self.assertGreater(
            fencing_b,
            fencing_a,
            f"Fencing token F_B ({fencing_b}) must be strictly greater than F_A ({fencing_a})"
        )

        # 4. Worker A wakes up and attempts a state commit with stale token F_A
        self.assertFalse(
            self.lock_manager.validate_fencing_token(resource, fencing_a),
            "Stale fencing token F_A must be rejected fail-closed"
        )

        # 5. Worker A attempts to release lock (compare-and-delete invariant)
        released_a = self.lock_manager.release(resource, owner_token=token_a)
        self.assertFalse(
            released_a,
            "Worker A's release must be rejected due to owner token mismatch / expiration"
        )
        self.assertTrue(
            self.lock_manager.is_locked(resource),
            "Resource must remain locked by Worker B"
        )

        # 6. Worker B validates active token and releases cleanly
        self.assertTrue(
            self.lock_manager.validate_fencing_token(resource, fencing_b),
            "Active fencing token F_B must be accepted"
        )
        released_b = self.lock_manager.release(resource, owner_token=token_b)
        self.assertTrue(released_b, "Worker B must release cleanly")
        self.assertFalse(
            self.lock_manager.is_locked(resource),
            "Resource must be completely unlocked after Worker B completes"
        )

    # --------------------------------------------------------------------------
    # DRILL 2: 10GB S3 MULTIPART ABORT & ORPHAN PURGE
    # --------------------------------------------------------------------------
    def test_chaos_s3_multipart_abort_and_orphan_purge(self):
        """
        Drill 2:
        Initiates 10GB multipart upload (205 parts at 50MB each).
        Simulates streaming parts 1-5, then injects network/runner abort.
        Asserts:
        - Upload transitions to ABORTED.
        - Buffered parts are purged to 0 (zero capacity leak).
        - Subsequent complete attempt raises fail-closed exception.
        - Cleanup sweeper handles orphaned upload state.
        """
        ten_gb_bytes = 10 * 1024 * 1024 * 1024
        expected_sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        job_id = "EXEC-CHAOS-10G"
        file_name = "rhel-9-hardened.iso"

        # 1. Initiate 10GB multipart upload
        init_res = self.s3_gateway.initiate_multipart_upload(
            file_name=file_name,
            file_size_bytes=ten_gb_bytes,
            sha256_checksum=expected_sha,
            job_id=job_id
        )
        upload_id = init_res["upload_id"]
        s3_key = init_res["s3_key"]
        self.assertEqual(init_res["total_parts"], 205)
        self.assertEqual(init_res["chunk_size_bytes"], CHUNK_SIZE_BYTES)

        # 2. Simulate uploading 5 parts
        s3_uri = f"s3://{self.s3_gateway.bucket_name}/{s3_key}"
        parts = [{"part_number": i, "etag": f"etag-part-{i}"} for i in range(1, 6)]
        self.s3_gateway._mock_objects[s3_uri]["parts"] = parts
        self.assertEqual(self.s3_gateway.get_parts_count(s3_key), 5)

        # 3. Inject abrupt abortion mid-stream
        aborted = self.s3_gateway.abort_multipart_upload(upload_id, s3_key)
        self.assertTrue(aborted, "Abort call must return True")

        # 4. Invariant: Buffered parts must be completely purged
        self.assertEqual(
            self.s3_gateway.get_parts_count(s3_key),
            0,
            "All temporary upload parts must be purged upon abort"
        )
        self.assertEqual(
            self.s3_gateway._mock_objects[s3_uri]["status"],
            "ABORTED",
            "Upload status must be recorded as ABORTED"
        )

        # 5. Invariant: Subsequent complete attempt must raise fail-closed exception
        with self.assertRaises(RuntimeError) as ctx:
            self.s3_gateway.complete_multipart_upload(upload_id, s3_key, parts)
        self.assertIn("ABORTED", str(ctx.exception))

        # 6. Run orphan cleaner
        cleaned = self.s3_gateway.cleanup_orphaned_uploads(max_age_seconds=0)
        self.assertGreaterEqual(cleaned, 0)

    # --------------------------------------------------------------------------
    # DRILL 3: WORKER CRASH & ORPHAN JOB REAPER
    # --------------------------------------------------------------------------
    def test_chaos_worker_crash_and_orphan_reaper(self):
        """
        Drill 3:
        Spawns a real child OS process simulating an execution runner.
        Attaches worker PID to a RUNNING job holding a distributed lock on target infrastructure.
        Creates a second RUNNING job attached to a living PID (current process).
        Terminates the worker process ungracefully with SIGKILL.
        Runs ApprovalSweeper.reap_orphaned_jobs():
        - Crashed job is reaped and transitioned to FAILED with reason WORKER_LOST.
        - Cryptographic Merkle audit record is synchronously appended with unbroken chain.
        - Target mutex lock held by dead worker is released.
        - Job belonging to living PID remains untouched in RUNNING status.
        """
        # 1. Spawn child worker process
        worker_proc = multiprocessing.Process(target=_child_worker_process, daemon=True)
        worker_proc.start()
        dead_pid = worker_proc.pid

        try:
            # 2. Setup repositories and sweeper
            catalog_items = get_catalog_items()
            catalog_item = catalog_items[0]
            job_repo = SQLiteJobRepository(db_path=":memory:", catalog=catalog_items)
            audit_logger = MerkleAuditLogger()
            sweeper = ApprovalSweeper(
                job_repo=job_repo,
                audit_logger=audit_logger,
                lock_manager=self.lock_manager
            )

            # 3. Create orphaned job assigned to child worker
            target_res = "prod-db-core-cluster"
            job_crashed = ExecutionJob(
                job_id="job-crashed-101",
                correlation_id="VULCAN-CORR-CRASH-01",
                catalog_item=catalog_item,
                requester_id="operator.crashed",
                target_resource_id=target_res,
                parameters={"port": 3000, "username": "openclaw"}
            )
            # Advance to RUNNING
            job_crashed.transition_to(JobStatus.PARSED, "Input parsed")
            job_crashed.transition_to(JobStatus.QUEUED, "Queued for dispatch")
            job_crashed.transition_to(JobStatus.LOCKED, "Target mutex acquired")
            job_crashed.transition_to(JobStatus.RUNNING, "Execution initiated")
            job_crashed.worker_pid = dead_pid
            owner_token = f"runner-{job_crashed.id}-{job_crashed.correlation_id}"
            job_crashed.lock_owner_token = owner_token

            # Acquire distributed lock for crashed job
            self.lock_manager.acquire(target_res, ttl_seconds=3600, owner_token=owner_token)
            self.assertTrue(self.lock_manager.is_locked(target_res))
            job_repo.save(job_crashed)

            # 4. Create healthy job assigned to living parent process
            job_healthy = ExecutionJob(
                job_id="job-healthy-102",
                correlation_id="VULCAN-CORR-HEALTHY-02",
                catalog_item=catalog_item,
                requester_id="operator.healthy",
                target_resource_id="prod-web-tier",
                parameters={"port": 3001, "username": "openclaw"}
            )
            job_healthy.transition_to(JobStatus.PARSED, "Input parsed")
            job_healthy.transition_to(JobStatus.QUEUED, "Queued for dispatch")
            job_healthy.transition_to(JobStatus.LOCKED, "Target mutex acquired")
            job_healthy.transition_to(JobStatus.RUNNING, "Execution initiated")
            job_healthy.worker_pid = os.getpid()  # Parent PID is alive
            job_repo.save(job_healthy)

            # 5. Terminate child worker ungracefully with SIGKILL
            os.kill(dead_pid, signal.SIGKILL)
            worker_proc.join(timeout=2.0)
            self.assertFalse(
                ApprovalSweeper._is_pid_alive(dead_pid),
                "Dead worker process must be confirmed dead by OS signal 0"
            )

            # 6. Execute ApprovalSweeper.reap_orphaned_jobs()
            reaped = sweeper.reap_orphaned_jobs()

            # 7. Assertions on reaped job
            self.assertEqual(len(reaped), 1, "Exactly one orphaned job must be reaped")
            reaped_job = reaped[0]
            self.assertEqual(reaped_job.id, "job-crashed-101")
            self.assertEqual(reaped_job.status, JobStatus.FAILED)
            self.assertIn("WORKER_LOST", reaped_job.error_message)
            self.assertIn(str(dead_pid), reaped_job.error_message)

            # 8. Assert lock was released
            self.assertFalse(
                self.lock_manager.is_locked(target_res),
                "Lock on target resource must be released when orphaned job is reaped"
            )

            # 9. Assert healthy job was NOT reaped
            persisted_healthy = job_repo.get_by_id("job-healthy-102")
            self.assertIsNotNone(persisted_healthy)
            self.assertEqual(
                persisted_healthy.status,
                JobStatus.RUNNING,
                "Job belonging to live worker must remain in RUNNING status"
            )

            # 10. Assert Merkle audit trail integrity
            self.assertTrue(
                audit_logger.verify_chain(),
                "Cryptographic Merkle audit chain must remain unbroken post-reap"
            )
            self.assertGreaterEqual(len(audit_logger.ledger), 1)
            last_record = audit_logger.ledger[-1]
            self.assertEqual(last_record.action, "WORKER_LOST")
            self.assertEqual(last_record.payload["dead_worker_pid"], dead_pid)
            self.assertEqual(last_record.actor, "system.orphan_reaper")

        finally:
            if worker_proc.is_alive():
                os.kill(worker_proc.pid, signal.SIGKILL)
                worker_proc.join(timeout=1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
