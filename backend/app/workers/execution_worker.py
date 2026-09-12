"""
Project Vulcan: Decoupled Execution Worker & Fleet Manager (BKND-18)
Author: Alex Xu (Distributed Systems Lead)
Pulls execution jobs from Redis Streams (or in-memory queue), executes them via BaseJobRunner,
and streams stdout / telemetry over WebSocketHub Redis Pub/Sub backplane.
Enforces Little's Law capacity sizing for 75 concurrent workers with bounded memory footprint.
"""
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from app.domain.entities import ExecutionJob, JobStatus
from app.ports.interfaces import IJobQueue, JobQueueMessage

logger = logging.getLogger("vulcan.worker")


class ExecutionWorker:
    """
    Autonomous worker consumer executing single-task automation pipelines.
    Identified by a unique worker consumer ID.
    """

    def __init__(
        self,
        job_queue: IJobQueue,
        container: Any,
        ws_hub: Any,
        worker_id: Optional[str] = None
    ):
        self.job_queue = job_queue
        self.container = container
        self.ws_hub = ws_hub
        self.worker_id = worker_id or f"runner-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._stop_event = threading.Event()

    def process_message(self, msg: JobQueueMessage) -> bool:
        """
        Executes an enqueued job through BaseJobRunner pipeline.
        Commits status updates and acks message upon completion.
        """
        correlation_id = msg.correlation_id
        logger.info("[%s] Processing job message [%s] for correlation_id [%s]", self.worker_id, msg.message_id, correlation_id)

        # 1. Look up job from repository or cache
        job: Optional[ExecutionJob] = None
        if hasattr(self.container, "job_repo") and self.container.job_repo:
            job = self.container.job_repo.get_by_correlation_id(correlation_id)
        if not job and hasattr(self.container, "jobs"):
            job = self.container.jobs.get(correlation_id)

        if not job:
            logger.warning("[%s] Job [%s] not found in repository. Acknowledging message to prevent poison loop.", self.worker_id, correlation_id)
            self.job_queue.ack(msg.message_id)
            return False

        # 2. Bind worker PID to job
        job.worker_pid = os.getpid()
        if hasattr(self.container, "job_repo") and self.container.job_repo:
            self.container.job_repo.save(job)

        # 3. Create execution runner with WebSocket stream hooks
        def _status_callback(corr_id: str, status: str, message: str):
            if self.ws_hub:
                self.ws_hub.publish(corr_id, "status", {"status": status, "message": message})

        runner = self.container.create_runner(
            log_event_stream=self.ws_hub.emit_log if self.ws_hub else None,
            status_event_stream=_status_callback if self.ws_hub else None
        )

        # 4. Execute template method pipeline
        try:
            logger.info("[%s] Executing BaseJobRunner for job [%s]", self.worker_id, correlation_id)
            runner.run(job)
            if hasattr(self.container, "job_repo") and self.container.job_repo:
                self.container.job_repo.save(job)
            if hasattr(self.container, "jobs") and isinstance(self.container.jobs, dict):
                self.container.jobs[correlation_id] = job
            if self.ws_hub:
                self.ws_hub.publish(job.correlation_id, "status", {
                    "status": job.status.value,
                    "message": "Execution complete"
                })
        except Exception as e:
            logger.error("[%s] Execution failure on job [%s]: %s", self.worker_id, correlation_id, e)
            if job.status not in (JobStatus.FAILED, JobStatus.REVERTED, JobStatus.DEGRADED):
                job.transition_to(JobStatus.FAILED, str(e))
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(e)
            if hasattr(self.container, "job_repo") and self.container.job_repo:
                self.container.job_repo.save(job)
            if hasattr(self.container, "jobs") and isinstance(self.container.jobs, dict):
                self.container.jobs[correlation_id] = job
            if self.ws_hub:
                self.ws_hub.emit_log(job.correlation_id, f"\033[1;31m[EXECUTION ERROR]\033[0m {str(e)}", "stderr")
                self.ws_hub.publish(job.correlation_id, "status", {
                    "status": job.status.value,
                    "message": str(e)
                })
            # Failure Diagnostics
            try:
                if hasattr(self.container, "diagnostic_engine") and self.container.diagnostic_engine:
                    cat_id = job.catalog_item.identifier if job.catalog_item else "unknown"
                    diag = self.container.diagnostic_engine.diagnose(str(e), cat_id, exit_code=job.exit_code or 1)
                    if self.ws_hub:
                        self.ws_hub.publish(job.correlation_id, "diagnostic", diag.to_dict())
                    job.diagnostic = diag.root_cause
                    job.diagnostic_details = diag.to_dict()
                    if hasattr(self.container, "job_repo") and self.container.job_repo:
                        self.container.job_repo.save(job)
                    if hasattr(self.container, "jobs") and isinstance(self.container.jobs, dict):
                        self.container.jobs[correlation_id] = job
            except Exception as diag_err:
                logger.debug("[%s] Diagnostics generation exception: %s", self.worker_id, diag_err)
        finally:
            # 5. Acknowledge message from queue
            self.job_queue.ack(msg.message_id)
            logger.info("[%s] Acknowledged message [%s] for job [%s]", self.worker_id, msg.message_id, correlation_id)

        return True

    def run_once(self, timeout_seconds: float = 1.0) -> bool:
        """Polls queue once and processes next job. Returns True if job was processed."""
        msg = self.job_queue.dequeue(self.worker_id, timeout_seconds=timeout_seconds)
        if not msg:
            return False
        return self.process_message(msg)

    def run_loop(self) -> None:
        """Continuous execution loop until stop signal is set."""
        logger.info("[%s] Worker loop started", self.worker_id)
        while not self._stop_event.is_set():
            try:
                processed = self.run_once(timeout_seconds=1.0)
                if not processed:
                    time.sleep(0.05)
            except Exception as e:
                logger.error("[%s] Unhandled exception in worker loop: %s", self.worker_id, e)
                time.sleep(0.5)
        logger.info("[%s] Worker loop stopped", self.worker_id)

    def stop(self) -> None:
        """Signals worker loop to terminate."""
        self._stop_event.set()


class ExecutionWorkerFleet:
    """
    Fleet manager coordinating a pool of concurrent ExecutionWorkers.
    Default capacity sized for 75 concurrent jobs (BKND-18 / Little's Law).
    """

    def __init__(
        self,
        job_queue: IJobQueue,
        container: Any,
        ws_hub: Any,
        concurrency: int = 75,
        fleet_name: str = "vulcan-fleet"
    ):
        self.job_queue = job_queue
        self.container = container
        self.ws_hub = ws_hub
        self.concurrency = concurrency
        self.fleet_name = fleet_name
        self.workers: List[ExecutionWorker] = []
        self._threads: List[threading.Thread] = []
        self._is_running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Starts worker threads up to configured concurrency."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            logger.info("Starting ExecutionWorkerFleet [%s] with concurrency=%d", self.fleet_name, self.concurrency)
            for i in range(self.concurrency):
                worker_id = f"{self.fleet_name}-w{i+1:02d}"
                worker = ExecutionWorker(
                    job_queue=self.job_queue,
                    container=self.container,
                    ws_hub=self.ws_hub,
                    worker_id=worker_id
                )
                self.workers.append(worker)
                t = threading.Thread(
                    target=worker.run_loop,
                    name=f"worker-thread-{worker_id}",
                    daemon=True
                )
                t.start()
                self._threads.append(t)
            logger.info("All %d workers active in fleet [%s]", len(self.workers), self.fleet_name)

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Gracefully signals all workers to stop and joins threads."""
        with self._lock:
            if not self._is_running:
                return
            logger.info("Stopping ExecutionWorkerFleet [%s]...", self.fleet_name)
            for worker in self.workers:
                worker.stop()
            self._is_running = False

        start_wait = time.time()
        for t in self._threads:
            rem = max(0.1, timeout_seconds - (time.time() - start_wait))
            t.join(timeout=rem)

        with self._lock:
            self.workers.clear()
            self._threads.clear()
        logger.info("ExecutionWorkerFleet [%s] completely stopped", self.fleet_name)

    @property
    def is_running(self) -> bool:
        return self._is_running

    def active_worker_count(self) -> int:
        return len([w for w in self.workers if not w._stop_event.is_set()])
