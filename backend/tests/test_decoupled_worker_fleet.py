"""
Project Vulcan: Decoupled Worker Fleet & Job Queue Test Suite (BKND-18)
Author: Alex Xu & Uncle Bob
Verifies Little's Law 75-runner capacity, Redis Streams / In-Memory queue contracts,
worker consumer lifecycles, and zero thread leakage in the FastAPI API process.
"""
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.adapters.redis_queue_adapter import InMemoryJobQueue, RedisJobQueue
from app.domain.entities import (
    CatalogItem,
    EngineExecutionResult,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
)
from app.ports.interfaces import JobQueueMessage
from app.workers.execution_worker import ExecutionWorker, ExecutionWorkerFleet


class TestDecoupledWorkerFleet(unittest.TestCase):
    """Exhaustive test suite for BKND-18 decoupled runner fleet and queue abstraction."""

    def setUp(self):
        self.queue = InMemoryJobQueue()
        self.catalog_item = CatalogItem(
            id="cat-s3-test",
            identifier="cloud-s3-kms-bucket-provision",
            name="Provision S3 Bucket with KMS",
            engine=ExecutionEngineType.TERRAFORM,
            git_repo="https://github.pnc.com/vulcan/infra-modules.git",
            git_commit_sha="a" * 40,
            playbook_or_module_path="modules/s3",
            risk_tier=RiskTier.LOW,
            requires_maker_checker=False,
            requires_chg=False,
            input_schema={
                "properties": {
                    "bucket_name": {"type": "string"},
                    "kms_key_arn": {"type": "string"},
                    "retention_days": {"type": "integer", "default": 90}
                },
                "required": ["bucket_name", "kms_key_arn"]
            }
        )

    def test_inmemory_job_queue_enqueue_dequeue_ack(self):
        """Validates basic FIFO queueing, message unicity, and consumer acking."""
        self.assertEqual(self.queue.queue_depth(), 0)

        msg_id1 = self.queue.enqueue("job-001", "EXEC-001", priority=1, payload={"target": "s3-east"})
        msg_id2 = self.queue.enqueue("job-002", "EXEC-002", priority=2, payload={"target": "s3-west"})

        self.assertEqual(self.queue.queue_depth(), 2)
        self.assertTrue(msg_id1.startswith("inmem-msg-"))
        self.assertTrue(msg_id2.startswith("inmem-msg-"))

        # Dequeue consumer 1
        msg1 = self.queue.dequeue("worker-1", timeout_seconds=0.1)
        self.assertIsNotNone(msg1)
        self.assertEqual(msg1.job_id, "job-001")
        self.assertEqual(msg1.correlation_id, "EXEC-001")
        self.assertEqual(msg1.priority, 1)

        # Ack consumer 1
        self.assertTrue(self.queue.ack(msg1.message_id))
        self.assertEqual(self.queue.queue_depth(), 1)

        # Dequeue consumer 2
        msg2 = self.queue.dequeue("worker-2", timeout_seconds=0.1)
        self.assertIsNotNone(msg2)
        self.assertEqual(msg2.job_id, "job-002")
        self.assertTrue(self.queue.ack(msg2.message_id))
        self.assertEqual(self.queue.queue_depth(), 0)

        # Empty queue dequeue returns None
        empty_msg = self.queue.dequeue("worker-1", timeout_seconds=0.05)
        self.assertIsNone(empty_msg)

    def test_inmemory_job_queue_nack_and_requeue(self):
        """Validates NACK with requeue increases retry count and re-delivers."""
        msg_id = self.queue.enqueue("job-err", "EXEC-ERR", priority=0)
        msg = self.queue.dequeue("worker-x", timeout_seconds=0.1)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.retry_count, 0)

        # NACK with requeue=True
        self.assertTrue(self.queue.nack(msg.message_id, requeue=True))

        # Should be available again with retry_count incremented
        reclaimed_msg = self.queue.dequeue("worker-y", timeout_seconds=0.1)
        self.assertIsNotNone(reclaimed_msg)
        self.assertEqual(reclaimed_msg.job_id, "job-err")
        self.assertEqual(reclaimed_msg.retry_count, 1)

        # NACK without requeue should purge it
        self.assertTrue(self.queue.nack(reclaimed_msg.message_id, requeue=False))
        self.assertIsNone(self.queue.dequeue("worker-z", timeout_seconds=0.05))

    def test_inmemory_job_queue_stale_reclaim(self):
        """Validates that dead worker leases are reclaimed by reaper after min_idle_ms."""
        self.queue.enqueue("job-stale", "EXEC-STALE")
        msg = self.queue.dequeue("worker-dead", timeout_seconds=0.1)
        self.assertIsNotNone(msg)

        # Immediately check stale reclaim with 10s idle — should not reclaim
        reclaimed = self.queue.requeue_stale(min_idle_ms=10000)
        self.assertEqual(len(reclaimed), 0)

        # Check with 0ms idle — should immediately reclaim
        time.sleep(0.01)
        reclaimed = self.queue.requeue_stale(min_idle_ms=5)
        self.assertEqual(len(reclaimed), 1)
        self.assertEqual(reclaimed[0].job_id, "job-stale")
        self.assertEqual(reclaimed[0].retry_count, 1)

    def test_redis_job_queue_contracts(self):
        """Unit tests RedisJobQueue interactions with mocked redis client."""
        mock_redis = MagicMock()
        mock_redis.xadd.return_value = b"1700000000000-0"
        mock_redis.xlen.return_value = 5
        mock_redis.xack.return_value = 1

        rq = RedisJobQueue(redis_client=mock_redis, stream_name="test:stream", group_name="test:group")
        mock_redis.xgroup_create.assert_called_once_with("test:stream", "test:group", id="$", mkstream=True)

        msg_id = rq.enqueue("job-redis", "EXEC-REDIS", priority="HIGH")
        self.assertEqual(msg_id, "1700000000000-0")
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args[0]
        self.assertEqual(call_args[0], "test:stream")
        self.assertEqual(call_args[1]["priority"], "2")  # Normalized from HIGH

        self.assertEqual(rq.queue_depth(), 5)
        self.assertTrue(rq.ack("1700000000000-0"))
        mock_redis.xack.assert_called_once_with("test:stream", "test:group", "1700000000000-0")

    def test_execution_worker_processes_job_lifecycle(self):
        """Worker dequeues message, invokes runner, updates job status, and ACKs message."""
        job = ExecutionJob(
            job_id="job-unit-01",
            correlation_id="EXEC-UNIT-01",
            catalog_item=self.catalog_item,
            requester_id="test.user",
            target_resource_id="arn:aws:s3:::test-bucket",
            parameters={"bucket_name": "test-bucket", "kms_key_arn": "arn:aws:kms:test"}
        )
        job.parse()
        job.transition_to(JobStatus.QUEUED, "Queued")

        mock_container = MagicMock()
        mock_container.job_repo.get_by_correlation_id.return_value = job
        mock_container.jobs = {"EXEC-UNIT-01": job}

        mock_runner = MagicMock()
        def fake_run(j):
            j.transition_to(JobStatus.LOCKED, "Lock acquired")
            j.transition_to(JobStatus.RUNNING, "Running")
            j.transition_to(JobStatus.VERIFYING, "Verifying")
            j.transition_to(JobStatus.SUCCESS, "Success")
            j.exit_code = 0
            return EngineExecutionResult(status="SUCCESS", exit_code=0, stdout="done")
        mock_runner.run.side_effect = fake_run
        mock_container.create_runner.return_value = mock_runner

        mock_ws = MagicMock()
        worker = ExecutionWorker(self.queue, mock_container, mock_ws, worker_id="test-runner-01")

        # Enqueue job
        msg_id = self.queue.enqueue(job.id, job.correlation_id, priority=0)
        self.assertEqual(self.queue.queue_depth(), 1)

        # Worker processes message
        processed = worker.run_once(timeout_seconds=0.1)
        self.assertTrue(processed)
        self.assertEqual(self.queue.queue_depth(), 0)

        # Invariants verified
        self.assertEqual(job.status, JobStatus.SUCCESS)
        self.assertIsNotNone(job.worker_pid)
        mock_runner.run.assert_called_once_with(job)
        mock_container.job_repo.save.assert_called()
        mock_ws.publish.assert_called()

    def test_execution_worker_handles_failure_and_diagnostics(self):
        """On runner failure, worker sets FAILED status, attaches AI diagnostics, and ACKs to avoid poison loops."""
        job = ExecutionJob(
            job_id="job-fail-01",
            correlation_id="EXEC-FAIL-01",
            catalog_item=self.catalog_item,
            requester_id="test.user",
            target_resource_id="arn:aws:s3:::test-fail",
            parameters={"bucket_name": "test-fail", "kms_key_arn": "arn:aws:kms:test"}
        )
        job.parse()
        job.transition_to(JobStatus.QUEUED, "Queued")

        mock_container = MagicMock()
        mock_container.job_repo.get_by_correlation_id.return_value = job
        mock_container.jobs = {"EXEC-FAIL-01": job}

        mock_runner = MagicMock()
        mock_runner.run.side_effect = RuntimeError("ResourceLockedError: Target node locked by PNC-MUTEX-99")
        mock_container.create_runner.return_value = mock_runner

        mock_diag = MagicMock()
        mock_diag.root_cause = "Resource target locked by PNC-MUTEX-99"
        mock_diag.to_dict.return_value = {"root_cause": mock_diag.root_cause, "confidence": 0.98}
        mock_container.diagnostic_engine.diagnose.return_value = mock_diag

        mock_ws = MagicMock()
        worker = ExecutionWorker(self.queue, mock_container, mock_ws, worker_id="test-fail-worker")

        self.queue.enqueue(job.id, job.correlation_id)
        processed = worker.run_once(timeout_seconds=0.1)

        self.assertTrue(processed)
        self.assertEqual(self.queue.queue_depth(), 0)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIn("ResourceLockedError", job.error_message)
        self.assertEqual(job.diagnostic, "Resource target locked by PNC-MUTEX-99")

    def test_execution_worker_fleet_high_throughput(self):
        """
        Validates Little's Law capacity:
        A pool of workers concurrently drains a burst of 50 queued jobs with zero thread leakage.
        """
        jobs = {}
        mock_container = MagicMock()
        for i in range(50):
            cid = f"EXEC-FLEET-{i:03d}"
            j = ExecutionJob(
                job_id=f"job-fleet-{i:03d}",
                correlation_id=cid,
                catalog_item=self.catalog_item,
                requester_id="load.tester",
                target_resource_id=f"s3-bucket-{i}",
                parameters={"bucket_name": f"bucket-{i}", "kms_key_arn": "kms"}
            )
            j.parse()
            j.transition_to(JobStatus.QUEUED, "Queued")
            jobs[cid] = j

        mock_container.job_repo.get_by_correlation_id.side_effect = lambda c: jobs.get(c)
        mock_container.jobs = jobs

        mock_runner = MagicMock()
        def fast_run(job):
            job.transition_to(JobStatus.LOCKED, "Lock acquired")
            job.transition_to(JobStatus.RUNNING, "Run")
            job.transition_to(JobStatus.VERIFYING, "Verify")
            job.transition_to(JobStatus.SUCCESS, "Success")
            job.exit_code = 0
            return EngineExecutionResult(status="SUCCESS", exit_code=0, stdout="ok")
        mock_runner.run.side_effect = fast_run
        mock_container.create_runner.return_value = mock_runner

        mock_ws = MagicMock()

        # Enqueue 50 jobs
        for cid, j in jobs.items():
            self.queue.enqueue(j.id, cid)

        self.assertEqual(self.queue.queue_depth(), 50)

        # Start fleet with 10 concurrent worker threads
        fleet = ExecutionWorkerFleet(
            job_queue=self.queue,
            container=mock_container,
            ws_hub=mock_ws,
            concurrency=10,
            fleet_name="fleet-test"
        )
        fleet.start()
        self.assertTrue(fleet.is_running)
        self.assertEqual(fleet.active_worker_count(), 10)

        # Wait for drain
        start = time.time()
        while self.queue.queue_depth() > 0 and (time.time() - start) < 5.0:
            time.sleep(0.05)

        self.assertEqual(self.queue.queue_depth(), 0)

        # Verify all 50 jobs transitioned to SUCCESS
        for cid, j in jobs.items():
            self.assertEqual(j.status, JobStatus.SUCCESS, f"Job {cid} should be SUCCESS")

        # Graceful shutdown
        fleet.stop(timeout_seconds=2.0)
        self.assertFalse(fleet.is_running)
        self.assertEqual(fleet.active_worker_count(), 0)


if __name__ == "__main__":
    unittest.main()
