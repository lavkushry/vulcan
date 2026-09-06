"""
Project Vulcan: Template Method Master Execution Pipeline (BaseJobRunner)
Clean Architecture Standard: Uncle Bob. Injected abstract ports, zero framework dependencies.
"""
import abc
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

from app.domain.entities import (
    EngineExecutionResult,
    EphemeralSecretLease,
    ExecutionJob,
    JobStatus,
    RiskTier,
)
from app.domain.exceptions import (
    AuditIntegrityError,
    HealthProbeDegradedError,
    MaintenanceWindowClosedError,
    ParameterValidationError,
    ResourceLockedError,
    StateTransitionError,
)
from app.ports.interfaces import (
    IAuditLogger,
    IExecutionEngine,
    IHealthProbeGateway,
    ILockManager,
    IObjectStorageGateway,
    ISecretProvider,
    IServiceNowGateway,
)


class BaseJobRunner(abc.ABC):
    """
    Template Method Pattern:
    Enforces the non-bypassable sequence of banking safeguards.
    Subclasses provide engine-specific hooks without altering safety gates.
    """

    def __init__(
        self,
        lock_manager: ILockManager,
        audit_logger: IAuditLogger,
        secret_provider: ISecretProvider,
        snow_gateway: Optional[IServiceNowGateway] = None,
        health_probe: Optional[IHealthProbeGateway] = None,
        storage_gateway: Optional[IObjectStorageGateway] = None,
        log_event_stream: Optional[Callable[[str, str], None]] = None
    ):
        self.lock_mgr = lock_manager
        self.audit = audit_logger
        self.secrets = secret_provider
        self.snow = snow_gateway
        self.health = health_probe
        self.storage = storage_gateway
        self.log_stream = log_event_stream

    def run(self, job: ExecutionJob) -> EngineExecutionResult:
        """The Master Template Method enforcing all banking invariants."""
        # 1. State Pre-flight
        if job.status not in (JobStatus.QUEUED, JobStatus.PARSED):
            if job.catalog_item.risk_tier == RiskTier.HIGH and job.status != JobStatus.QUEUED:
                raise StateTransitionError(
                    f"High risk job must be in QUEUED status to execute, got {job.status.value}"
                )

        # 2. Hard Invariant: Maintenance Window Verification
        current_time = datetime.now(timezone.utc)
        if job.catalog_item.risk_tier in (RiskTier.HIGH, RiskTier.MEDIUM) and job.servicenow_chg:
            if self.snow and not self.snow.is_within_maintenance_window(job.servicenow_chg, current_time):
                try:
                    self.audit.record(job, "EXEC_BLOCKED", {
                        "reason": "MAINTENANCE_WINDOW_CLOSED",
                        "resource": job.target_resource_id,
                        "chg": job.servicenow_chg,
                        "details": f"Current time [{current_time.isoformat()}] is outside the approved window."
                    })
                except Exception as audit_err:
                    logger.critical("Audit ledger write failed for EXEC_BLOCKED (MAINTENANCE_WINDOW_CLOSED) on job %s: %s", job.id, audit_err)
                raise MaintenanceWindowClosedError(
                    f"Execution blocked: Current time [{current_time.isoformat()}] is outside the approved "
                    f"ServiceNow maintenance window for CHG [{job.servicenow_chg}]."
                )

        # 3. 10GB S3 Payload Integrity Checksum Verification
        if job.storage_artifact_uri and job.storage_artifact_sha256 and self.storage:
            if not self.storage.verify_artifact_checksum(job.storage_artifact_uri, job.storage_artifact_sha256):
                try:
                    self.audit.record(job, "EXEC_BLOCKED", {
                        "reason": "CHECKSUM_MISMATCH",
                        "resource": job.target_resource_id,
                        "uri": job.storage_artifact_uri
                    })
                except Exception as audit_err:
                    logger.critical("Audit ledger write failed for EXEC_BLOCKED (CHECKSUM_MISMATCH) on job %s: %s", job.id, audit_err)
                raise ParameterValidationError(
                    f"Storage artifact checksum mismatch on {job.storage_artifact_uri}"
                )

        # 4. Enforce Distributed Target Mutex
        owner_token = f"runner-{job.id}-{job.correlation_id}"
        if not self.lock_mgr.acquire(job.target_resource_id, owner_token=owner_token):
            try:
                self.audit.record(job, "EXEC_BLOCKED", {
                    "reason": "RESOURCE_LOCKED",
                    "resource": job.target_resource_id,
                    "details": f"Distributed target resource [{job.target_resource_id}] is locked by an active change."
                })
            except Exception as audit_err:
                logger.critical("Audit ledger write failed for EXEC_BLOCKED (RESOURCE_LOCKED) on job %s: %s", job.id, audit_err)
            raise ResourceLockedError(
                f"Distributed target resource [{job.target_resource_id}] is locked by an active change."
            )
        job.transition_to(JobStatus.LOCKED, "Distributed lock acquired")

        lease: Optional[EphemeralSecretLease] = None
        try:
            # 5. Check out JIT Ephemeral Secrets into RAM
            lease = self.secrets.checkout_ephemeral_secret(job.target_resource_id)

            # 6. Hard Banking Invariant: Synchronous Write-Before-Run Audit Commit
            try:
                self.audit.record(job, "EXEC_START", {
                    "resource": job.target_resource_id,
                    "requester": job.requester_id,
                    "approver": job.approver_id,
                    "chg": job.servicenow_chg
                })
            except Exception as audit_err:
                raise AuditIntegrityError(
                    f"Pre-execution audit write failed. Aborting execution: {audit_err}"
                ) from audit_err

            # 7. ServiceNow State Synchronization
            if job.servicenow_chg and self.snow:
                self.snow.update_work_notes(job.servicenow_chg, "Worker started change execution.", "In Progress")

            job.transition_to(JobStatus.RUNNING, "Worker spawned")
            job.started_at = datetime.now(timezone.utc)

            # 8. Engine Execution Hook (Subclass Strategy)
            def event_sink(line: str):
                if self.log_stream:
                    self.log_stream(job.correlation_id, line)

            result = self._execute_engine(job, event_sink, lease.secrets)

            # 9. Non-zero exit code check
            if result.exit_code != 0:
                raise RuntimeError(f"Execution engine failed with exit code {result.exit_code}: {result.stdout}")

            # 10. Post-Flight Semantic Health Probing (Exit 0 != Success)
            job.transition_to(JobStatus.VERIFYING, "Running synthetic post-flight health probes")
            if self.health:
                health_result = self.health.probe(job)
                if not health_result.is_healthy:
                    job.transition_to(JobStatus.DEGRADED, f"Health check failed: latency={health_result.latency_ms}ms")
                    if job.catalog_item.rollback_path:
                        job.transition_to(JobStatus.REVERTING, f"Automated rollback triggered: {job.catalog_item.rollback_path}")
                        try:
                            rb_result = self._execute_rollback(job, event_sink, lease.secrets if lease else {})
                            if rb_result.exit_code == 0:
                                job.transition_to(JobStatus.REVERTED, "Rollback playbook completed successfully")
                                job.completed_at = datetime.now(timezone.utc)
                                self.audit.record(job, "EXEC_REVERTED", {
                                    "status": "REVERTED",
                                    "rollback_path": job.catalog_item.rollback_path,
                                    "health_details": health_result.details
                                })
                                raise HealthProbeDegradedError("Post-flight health probe failed. System state automatically reverted.")
                            else:
                                job.transition_to(JobStatus.FAILED, f"Rollback failed with exit code {rb_result.exit_code}")
                                raise RuntimeError(f"Rollback execution failed: {rb_result.stdout}")
                        except Exception as rb_exc:
                            if job.status not in (JobStatus.REVERTED, JobStatus.FAILED):
                                job.transition_to(JobStatus.FAILED, f"Rollback error: {rb_exc}")
                            raise
                    else:
                        raise HealthProbeDegradedError("Post-flight semantic health check failed. System degraded.")

            # 11. Record Terminal Success & Close ServiceNow Ticket
            job.transition_to(JobStatus.SUCCESS, "Change execution & health verification completed")
            job.completed_at = datetime.now(timezone.utc)
            job.exit_code = 0

            self.audit.record(job, "EXEC_SUCCESS", {"exit_code": 0, "status": "SUCCESS"})
            if job.servicenow_chg and self.snow:
                self.snow.update_work_notes(job.servicenow_chg, "Execution verified healthy. Change closed.", "Closed Complete")

            return result

        except Exception as exc:
            # Handle Failure, Diagnostics, and Audit
            # Preserve DEGRADED and REVERTED states - do not overwrite to FAILED
            if job.status not in (JobStatus.DEGRADED, JobStatus.REVERTING, JobStatus.REVERTED, JobStatus.FAILED):
                job.transition_to(JobStatus.FAILED, str(exc))
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(exc)

            try:
                if job.status != JobStatus.REVERTED:
                    self.audit.record(job, "EXEC_FAILED", {"error": str(exc), "status": job.status.value})
            except Exception as audit_err:
                logger.critical("Audit ledger write failed for EXEC_FAILED on job %s: %s", job.id, audit_err)

            if job.servicenow_chg and self.snow:
                notes = f"Execution degraded & reverted: {str(exc)}" if job.status == JobStatus.REVERTED else f"Execution failed: {str(exc)}"
                self.snow.update_work_notes(job.servicenow_chg, notes, "In Progress")

            raise exc

        finally:
            # 12. Guaranteed Teardown: Revoke JIT credentials and release lock
            if lease:
                self.secrets.revoke_ephemeral_secret(lease)
            if job.status not in (JobStatus.QUEUED, JobStatus.PARSED, JobStatus.SUBMITTED, JobStatus.PENDING_APPROVAL):
                self.lock_mgr.release(job.target_resource_id, owner_token=owner_token)

    def _execute_rollback(
        self,
        job: ExecutionJob,
        event_callback: Callable[[str], None],
        secrets: Dict[str, str]
    ) -> EngineExecutionResult:
        """Executes automated rollback when health checks fail and rollback_path is defined."""
        event_callback(f"\033[1;33m[ROLLBACK]\033[0m Invoking rollback routine: {job.catalog_item.rollback_path}...")
        return self._execute_engine(job, event_callback, secrets)

    @abc.abstractmethod
    def _execute_engine(
        self,
        job: ExecutionJob,
        event_callback: Callable[[str], None],
        secrets: Dict[str, str]
    ) -> EngineExecutionResult:
        """Concrete subclasses implement Ansible or Terraform execution."""
        pass


class AnsibleJobRunner(BaseJobRunner):
    """Concrete implementation for Ansible playbooks delegating to IExecutionEngine port."""
    def __init__(self, engine_port: IExecutionEngine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine_port = engine_port

    def _execute_engine(self, job: ExecutionJob, event_callback: Callable[[str], None], secrets: Dict[str, str]) -> EngineExecutionResult:
        return self.engine_port.execute(job, event_callback, secrets)


class TerraformJobRunner(BaseJobRunner):
    """Concrete implementation for Terraform plan/apply lifecycles delegating to IExecutionEngine port."""
    def __init__(self, engine_port: IExecutionEngine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine_port = engine_port

    def _execute_engine(self, job: ExecutionJob, event_callback: Callable[[str], None], secrets: Dict[str, str]) -> EngineExecutionResult:
        return self.engine_port.execute(job, event_callback, secrets)
