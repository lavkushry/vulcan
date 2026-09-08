"""
Project Vulcan: Distributed Approval Sweeper with Redlock Leader Election (Milestone B)
Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")
Enforces Hard Banking Invariant 2 (15-Minute Fail-Closed Approval Timeout).
Guarantees single-leader execution across multi-worker deployments via distributed mutex.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from app.domain.entities import ExecutionJob, JobStatus
from app.ports.interfaces import IAuditLogger, ILockManager
from app.ports.repositories import IJobRepository

logger = logging.getLogger("vulcan.approval_sweeper")


class ApprovalSweeper:
    """
    Distributed background service that sweeps expired pending approval jobs.
    Uses Redlock leader election so that in a multi-worker uvicorn topology,
    exactly ONE worker acts as the active sweeper at any given time.
    """
    LEADER_LOCK_RESOURCE = "leader:approval_sweeper"

    def __init__(
        self,
        job_repo: IJobRepository,
        audit_logger: IAuditLogger,
        lock_manager: ILockManager,
        event_publisher: Optional[Callable[[str, str, Any], None]] = None,
        interval_seconds: float = 5.0,
        timeout_seconds: int = 900,
        lease_ttl_seconds: int = 15,
        worker_id: Optional[str] = None
    ):
        self.job_repo = job_repo
        self.audit_logger = audit_logger
        self.lock_manager = lock_manager
        self.event_publisher = event_publisher
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.lease_ttl_seconds = lease_ttl_seconds
        self.worker_id = worker_id or f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"

        self._is_running = False
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._is_leader = False

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    def sweep_once(self) -> List[ExecutionJob]:
        """
        Executes a single sweep iteration.
        Finds all PENDING_APPROVAL jobs that have exceeded the timeout window
        and transitions them fail-closed to TIMEOUT_DENIED with Merkle audit recording.
        """
        now = datetime.now(timezone.utc)
        timed_out_jobs: List[ExecutionJob] = []

        try:
            pending = self.job_repo.get_pending_approvals()
        except Exception as e:
            logger.error("Failed to query pending approvals: %s", e)
            return []

        for job in pending:
            if not job.approval_requested_at:
                continue

            req_at = job.approval_requested_at
            if req_at.tzinfo is None:
                req_at = req_at.replace(tzinfo=timezone.utc)

            elapsed = (now - req_at).total_seconds()
            if elapsed > self.timeout_seconds:
                logger.warning(
                    "Job [%s] (%s) approval expired: %.1fs > %ds. Enforcing fail-closed TIMEOUT_DENIED.",
                    job.id, job.correlation_id, elapsed, self.timeout_seconds
                )
                try:
                    job.transition_to(
                        JobStatus.TIMEOUT_DENIED,
                        f"Approval timed out after {elapsed:.1f}s (> {self.timeout_seconds}s window)"
                    )
                    # 1. Commit synchronous Merkle audit record
                    self.audit_logger.record(
                        job=job,
                        action="APPROVAL_TIMEOUT",
                        payload={
                            "reason": "FAIL_CLOSED_TIMEOUT_DENIED",
                            "elapsed_seconds": round(elapsed, 2),
                            "timeout_seconds": self.timeout_seconds,
                            "catalog_identifier": job.catalog_item.identifier,
                            "requester_id": job.requester_id
                        },
                        actor="system.approval_sweeper"
                    )
                    # 2. Persist updated job status
                    self.job_repo.save(job)
                    timed_out_jobs.append(job)

                    # 3. Broadcast real-time status update to WebSocket clients
                    if self.event_publisher:
                        self.event_publisher(
                            job.correlation_id,
                            "status",
                            {
                                "status": "TIMEOUT_DENIED",
                                "reason": f"Approval window expired ({self.timeout_seconds}s limit)",
                                "job_id": job.id,
                                "correlation_id": job.correlation_id
                            }
                        )
                except Exception as ex:
                    logger.error("Error timing out job [%s]: %s", job.id, ex)

        return timed_out_jobs

    def reap_orphaned_jobs(self) -> List[ExecutionJob]:
        """
        Detects RUNNING/LOCKED jobs whose owning worker_pid is dead.
        Transitions them to FAILED with reason WORKER_LOST, writes Merkle audit record,
        and releases any held distributed lock.
        Enforces: "Every job must reach a terminal state."
        """
        now = datetime.now(timezone.utc)
        reaped: List[ExecutionJob] = []

        try:
            running = self.job_repo.get_running_jobs()
        except Exception as e:
            logger.error("Failed to query running jobs for orphan reaper: %s", e)
            return []

        for job in running:
            pid = getattr(job, "worker_pid", None)
            if pid is None:
                continue  # No PID recorded — cannot determine liveness

            if self._is_pid_alive(pid):
                continue  # Worker still alive — job is healthy

            # Worker is dead → reap the orphaned job
            reason = f"WORKER_LOST: owning worker PID {pid} no longer alive"
            logger.warning(
                "Reaping orphaned job [%s] (%s): %s",
                job.id, job.correlation_id, reason
            )
            try:
                job.transition_to(JobStatus.FAILED, reason)
                job.error_message = reason
                job.completed_at = now

                # 1. Commit synchronous Merkle audit record
                self.audit_logger.record(
                    job=job,
                    action="WORKER_LOST",
                    payload={
                        "reason": "WORKER_LOST",
                        "dead_worker_pid": pid,
                        "job_status_before": "RUNNING",
                        "catalog_identifier": job.catalog_item.identifier,
                        "correlation_id": job.correlation_id,
                        "requester_id": job.requester_id
                    },
                    actor="system.orphan_reaper"
                )

                # 2. Persist updated job status
                self.job_repo.save(job)
                reaped.append(job)

                # 3. Release any held distributed lock for this job's target resource
                try:
                    if job.target_resource_id:
                        owner_token = getattr(job, "lock_owner_token", None) or f"runner-{job.id}-{job.correlation_id}"
                        released = self.lock_manager.release(
                            job.target_resource_id,
                            owner_token=owner_token
                        )
                        logger.info("Released target mutex for [%s] (owner=%s): %s", job.target_resource_id, owner_token, released)
                except Exception as lock_err:
                    logger.debug("Lock release for reaped job [%s]: %s (may already be expired)", job.id, lock_err)

                # 4. Broadcast real-time status update to WebSocket clients
                if self.event_publisher:
                    self.event_publisher(
                        job.correlation_id,
                        "status",
                        {
                            "status": "FAILED",
                            "reason": reason,
                            "job_id": job.id,
                            "correlation_id": job.correlation_id
                        }
                    )
            except Exception as ex:
                logger.error("Error reaping orphaned job [%s]: %s", job.id, ex)

        return reaped

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """
        Portable PID liveness check (POSIX signal 0).

        ARCHITECTURAL LIMITATION (SINGLE-HOST ONLY):
        Signal 0 liveness check is valid ONLY within a single shared PID namespace (e.g., multi-worker
        uvicorn processes running on a single container or host).
        When execution runners scale out across multiple distributed hosts/nodes, PID numbers collide
        and are meaningless across nodes. For multi-node runner fleets, worker liveness MUST use
        distributed Redis/Postgres heartbeats (lease timestamps e.g. updated_at < now - heartbeat_timeout).
        """
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we lack permission

    async def run_loop(self):
        """Main async background loop with Redlock leader election."""
        logger.info(
            "Approval sweeper started for %s (interval=%.1fs, timeout=%ds)",
            self.worker_id, self.interval_seconds, self.timeout_seconds
        )
        self._is_running = True

        # Initial startup backoff so server completes startup and serves health probes first
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=min(2.0, self.interval_seconds))
        except asyncio.TimeoutError:
            pass

        while not self._stop_event.is_set():
            try:
                # 1. Attempt leader election via distributed lock
                acquired = await asyncio.to_thread(
                    self.lock_manager.acquire,
                    resource_id=self.LEADER_LOCK_RESOURCE,
                    ttl_seconds=self.lease_ttl_seconds,
                    owner_token=self.worker_id
                )

                if acquired:
                    if not self._is_leader:
                        logger.info("👑 Worker [%s] elected LEADER for approval sweeper.", self.worker_id)
                    self._is_leader = True

                    # 2. As leader, execute the sweep cycle off the event loop
                    swept = await asyncio.to_thread(self.sweep_once)
                    if swept:
                        logger.info("Sweeper denied %d expired jobs.", len(swept))

                    # 3. As leader, reap any orphaned jobs left by crashed workers
                    reaped = await asyncio.to_thread(self.reap_orphaned_jobs)
                    if reaped:
                        logger.warning(
                            "Reaped %d orphaned RUNNING jobs: %s",
                            len(reaped), [j.correlation_id for j in reaped]
                        )
                else:
                    if self._is_leader:
                        logger.warning("👑 Worker [%s] lost leadership lock.", self.worker_id)
                    self._is_leader = False

            except Exception as e:
                logger.error("Error in approval sweeper loop: %s", e)

            # Wait for next interval or stop event
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

        # Cleanup on stop: release leadership lock if held
        if self._is_leader:
            try:
                self.lock_manager.release(self.LEADER_LOCK_RESOURCE, owner_token=self.worker_id)
                logger.info("Worker [%s] released leadership lock on shutdown.", self.worker_id)
            except Exception as e:
                logger.warning("Error releasing leadership lock on stop: %s", e)
        self._is_leader = False
        self._is_running = False

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> asyncio.Task:
        """Starts the sweeper in the current event loop."""
        self._stop_event.clear()
        target_loop = loop or asyncio.get_event_loop()
        self._task = target_loop.create_task(self.run_loop())
        return self._task

    async def stop(self):
        """Stops the sweeper cleanly."""
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self.interval_seconds + 1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        self._is_running = False
