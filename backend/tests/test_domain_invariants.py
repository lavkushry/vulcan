"""
Project Vulcan: Core Domain Invariants & Banking Rules Unit Test Suite
Author: Robert C. Martin ("Uncle Bob")
Target: 100% Coverage of Banking Invariants, Maker-Checker, Mutexes, and Merkle Chaining.
"""
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from app.domain.entities import (
    ApprovalDecision,
    AuditRecord,
    CatalogItem,
    EngineExecutionResult,
    EphemeralSecretLease,
    ExecutionEngineType,
    ExecutionJob,
    HealthCheckResult,
    JobStatus,
    RiskTier,
)
from app.domain.exceptions import (
    ApprovalTimeoutError,
    AuditIntegrityError,
    HealthProbeDegradedError,
    MaintenanceWindowClosedError,
    MakerCheckerViolationError,
    ParameterValidationError,
    ResourceLockedError,
    SecretLintError,
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
from app.use_cases.runner import AnsibleJobRunner


# =====================================================================
# IN-MEMORY TEST DOUBLES (FAKES)
# =====================================================================

class InMemoryLockManager(ILockManager):
    def __init__(self):
        self._locks = set()
        self.release_call_count = 0

    def acquire(self, resource_id: str, ttl_seconds: int = 1800) -> bool:
        if resource_id in self._locks:
            return False
        self._locks.add(resource_id)
        return True

    def release(self, resource_id: str) -> None:
        self.release_call_count += 1
        self._locks.discard(resource_id)

    def is_locked(self, resource_id: str) -> bool:
        return resource_id in self._locks


class InMemoryAuditLogger(IAuditLogger):
    GENESIS_HASH = "0" * 64

    def __init__(self):
        self.ledger: List[AuditRecord] = []
        self._last_hash = self.GENESIS_HASH
        self.fail_pre_run_write = False

    def record(self, job: ExecutionJob, action: str, payload: Dict[str, Any]) -> AuditRecord:
        if self.fail_pre_run_write and action == "EXEC_START":
            raise IOError("Storage write failed: WORM volume unmounted.")

        rec_id = len(self.ledger) + 1
        now_str = datetime.now(timezone.utc).isoformat()
        current_hash = AuditRecord.compute_hash(
            job.correlation_id, now_str, job.requester_id, action, payload, self._last_hash
        )
        rec = AuditRecord(
            id=rec_id,
            correlation_id=job.correlation_id,
            timestamp=now_str,
            actor=job.requester_id,
            action=action,
            payload=payload,
            prev_hash=self._last_hash,
            current_hash=current_hash
        )
        self.ledger.append(rec)
        self._last_hash = current_hash
        return rec

    def get_last_hash(self) -> str:
        return self._last_hash

    def verify_chain(self) -> bool:
        prev = self.GENESIS_HASH
        for rec in self.ledger:
            if rec.prev_hash != prev:
                return False
            expected = AuditRecord.compute_hash(
                rec.correlation_id, rec.timestamp, rec.actor, rec.action, rec.payload, rec.prev_hash
            )
            if rec.current_hash != expected:
                return False
            prev = rec.current_hash
        return True


class InMemorySecretProvider(ISecretProvider):
    def __init__(self):
        self.revoked_leases = []
        self.active_leases = []

    def checkout_ephemeral_secret(self, target: str) -> EphemeralSecretLease:
        lease = EphemeralSecretLease(
            lease_id="lease-12345",
            secrets={"DYNAMIC_SSH_KEY": "privkey-mock-data"},
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        self.active_leases.append(lease)
        return lease

    def revoke_ephemeral_secret(self, lease: EphemeralSecretLease) -> None:
        self.revoked_leases.append(lease.lease_id)


class InMemoryServiceNowGateway(IServiceNowGateway):
    def __init__(self):
        self.window_open = True
        self.work_notes = []
        self.states = []

    def validate_chg(self, chg_number: str) -> Dict[str, Any]:
        return {"chg_number": chg_number, "state": "Scheduled"}

    def is_within_maintenance_window(self, chg_number: str, check_time: datetime) -> bool:
        return self.window_open

    def update_work_notes(self, chg_number: str, notes: str, new_state: Optional[str] = None) -> None:
        self.work_notes.append(notes)
        if new_state:
            self.states.append(new_state)


class InMemoryObjectStorageGateway(IObjectStorageGateway):
    def __init__(self):
        self.valid_checksums = {
            "s3://bucket/rhel9.iso": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }

    def verify_artifact_checksum(self, uri: str, expected_sha256: str) -> bool:
        return self.valid_checksums.get(uri) == expected_sha256


class InMemoryHealthProbeGateway(IHealthProbeGateway):
    def __init__(self, healthy: bool = True):
        self.healthy = healthy

    def probe(self, job: ExecutionJob) -> HealthCheckResult:
        return HealthCheckResult(
            is_healthy=self.healthy,
            latency_ms=25.0 if self.healthy else 950.0,
            error_rate=0.0 if self.healthy else 0.45,
            details={"probed_endpoints": 3}
        )


class FakeExecutionEngine(IExecutionEngine):
    def __init__(self, exit_code: int = 0, stdout_output: str = "Playbook ran cleanly."):
        self.exit_code = exit_code
        self.stdout_output = stdout_output
        self.invoked = False

    def execute(
        self,
        job: ExecutionJob,
        event_callback: Callable[[str], None],
        secrets: Dict[str, str]
    ) -> EngineExecutionResult:
        self.invoked = True
        event_callback("TASK [Gathering Facts] **************************")
        event_callback("ok: [pnc-f5-01]")
        return EngineExecutionResult(
            status="SUCCESS" if self.exit_code == 0 else "FAILED",
            exit_code=self.exit_code,
            stdout=self.stdout_output
        )


# =====================================================================
# UNIT TEST MATRIX (18 TEST CASES)
# =====================================================================

class TestVulcanCleanArchitectureSuite(unittest.TestCase):

    def setUp(self):
        self.catalog_item = CatalogItem(
            id="cat-01",
            identifier="f5-cert-renew",
            name="F5 SSL Certificate Renewal",
            engine=ExecutionEngineType.ANSIBLE,
            git_repo="git@github.com:pnc/network-playbooks.git",
            git_commit_sha="a1b2c3d4e5f67890123456789abcdef012345678",
            playbook_or_module_path="playbooks/renew_f5_cert.yml",
            risk_tier=RiskTier.HIGH,
            requires_maker_checker=True,
            requires_chg=True,
            input_schema={
                "type": "object",
                "required": ["hostname", "vip_ip", "cert_valid_days"],
                "properties": {
                    "hostname": {"type": "string", "pattern": r"^[a-z0-9-]+(\.pnc\.com)?$"},
                    "vip_ip": {"type": "string", "pattern": r"^\d{1,3}(\.\d{1,3}){3}$"},
                    "cert_valid_days": {"type": "integer", "minimum": 30, "maximum": 365}
                }
            }
        )
        self.valid_params = {
            "hostname": "f5-edge-01.pnc.com",
            "vip_ip": "10.200.1.50",
            "cert_valid_days": 90
        }
        self.lock_mgr = InMemoryLockManager()
        self.audit = InMemoryAuditLogger()
        self.secrets = InMemorySecretProvider()
        self.snow = InMemoryServiceNowGateway()
        self.health = InMemoryHealthProbeGateway(healthy=True)
        self.storage = InMemoryObjectStorageGateway()
        self.engine = FakeExecutionEngine(exit_code=0)

    # -------------------------------------------------------------
    # RULE 1: MAKER-CHECKER (SEPARATION OF DUTIES)
    # -------------------------------------------------------------
    def test_maker_checker_self_approval_strictly_forbidden(self):
        """Banking Rule: Requester cannot approve their own change (even with admin rights)."""
        job = ExecutionJob(
            job_id="j-01",
            correlation_id="EXEC-1001",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.request_approval(datetime.now(timezone.utc))

        decision = ApprovalDecision(
            decision="APPROVE",
            approver_id="lavkush.kumar",  # SAME AS REQUESTER
            decided_at=datetime.now(timezone.utc),
            reason="Self approval attempt"
        )
        with self.assertRaises(MakerCheckerViolationError) as ctx:
            job.apply_approval_decision(decision, datetime.now(timezone.utc))
        self.assertIn("Separation of Duties Violation", str(ctx.exception))
        self.assertEqual(job.status, JobStatus.PENDING_APPROVAL)

    def test_maker_checker_distinct_checker_succeeds(self):
        """Checker is different person: transitions cleanly to QUEUED."""
        job = ExecutionJob(
            job_id="j-02",
            correlation_id="EXEC-1002",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.request_approval(datetime.now(timezone.utc))

        decision = ApprovalDecision(
            decision="APPROVE",
            approver_id="sre.lead",  # DISTINCT CHECKER
            decided_at=datetime.now(timezone.utc),
            reason="Change reviewed and authorized"
        )
        job.apply_approval_decision(decision, datetime.now(timezone.utc))
        self.assertEqual(job.status, JobStatus.QUEUED)
        self.assertEqual(job.approver_id, "sre.lead")

    def test_maker_checker_15_minute_timeout_fails_closed(self):
        """Banking Rule: 15-minute approval inactivity triggers fail-closed denial."""
        job = ExecutionJob(
            job_id="j-03",
            correlation_id="EXEC-1003",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        req_time = datetime.now(timezone.utc) - timedelta(minutes=16)
        job.request_approval(req_time)

        decision = ApprovalDecision(
            decision="APPROVE",
            approver_id="sre.lead",
            decided_at=datetime.now(timezone.utc),
            reason="Late approval"
        )
        with self.assertRaises(ApprovalTimeoutError):
            job.apply_approval_decision(decision, datetime.now(timezone.utc), timeout_seconds=900)
        self.assertEqual(job.status, JobStatus.TIMEOUT_DENIED)

    # -------------------------------------------------------------
    # RULE 2: PARAMETER BOUNDS, REGEX & SECRET LINTING
    # -------------------------------------------------------------
    def test_parameter_regex_mismatch_rejected(self):
        """Invalid hostname failing regex pattern rejected at construction."""
        bad_params = self.valid_params.copy()
        bad_params["hostname"] = "INVALID!HOSTNAME$"
        with self.assertRaises(ParameterValidationError) as ctx:
            ExecutionJob(
                job_id="j-04",
                correlation_id="EXEC-1004",
                catalog_item=self.catalog_item,
                requester_id="lavkush.kumar",
                target_resource_id="f5-vip-01",
                parameters=bad_params
            )
        self.assertIn("does not match required regex pattern", str(ctx.exception))

    def test_parameter_numeric_bounds_violation_rejected(self):
        """cert_valid_days exceeding 365 maximum rejected immediately."""
        bad_params = self.valid_params.copy()
        bad_params["cert_valid_days"] = 500  # max is 365
        with self.assertRaises(ParameterValidationError) as ctx:
            ExecutionJob(
                job_id="j-05",
                correlation_id="EXEC-1005",
                catalog_item=self.catalog_item,
                requester_id="lavkush.kumar",
                target_resource_id="f5-vip-01",
                parameters=bad_params
            )
        self.assertIn("exceeds maximum 365", str(ctx.exception))

    def test_parameter_secret_linting_detects_embedded_credentials(self):
        """Security invariant: TruffleHog regex halts credential leakage."""
        leaky_params = self.valid_params.copy()
        leaky_params["hostname"] = "f5-edge-01.pnc.com"
        leaky_params["vip_ip"] = "AKIA1234567890ABCDEF"  # AWS Access Key signature
        with self.assertRaises(SecretLintError) as ctx:
            ExecutionJob(
                job_id="j-06",
                correlation_id="EXEC-1006",
                catalog_item=self.catalog_item,
                requester_id="lavkush.kumar",
                target_resource_id="f5-vip-01",
                parameters=leaky_params
            )
        self.assertIn("Security Invariant Triggered", str(ctx.exception))

    # -------------------------------------------------------------
    # RULE 3: MAINTENANCE WINDOW ENFORCEMENT
    # -------------------------------------------------------------
    def test_maintenance_window_closed_blocks_runner(self):
        """Runner halts prior to execution if current time outside maintenance window."""
        self.snow.window_open = False  # Window closed
        runner = AnsibleJobRunner(
            engine_port=self.engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets,
            snow_gateway=self.snow,
            health_probe=self.health
        )
        job = ExecutionJob(
            job_id="j-07",
            correlation_id="EXEC-1007",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.transition_to(JobStatus.PARSED)
        job.request_approval(datetime.now(timezone.utc))
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "sre.lead", datetime.now(timezone.utc), "Approved"),
            datetime.now(timezone.utc)
        )

        with self.assertRaises(MaintenanceWindowClosedError):
            runner.run(job)
        self.assertFalse(self.engine.invoked)
        self.assertFalse(self.lock_mgr.is_locked("f5-vip-01"))

    # -------------------------------------------------------------
    # RULE 4: WRITE-BEFORE-RUN AUDIT & CRYPTOGRAPHIC CHAIN
    # -------------------------------------------------------------
    def test_write_before_run_failure_aborts_prior_to_engine(self):
        """If synchronous audit log fails to commit, runner MUST abort without running engine."""
        self.audit.fail_pre_run_write = True
        runner = AnsibleJobRunner(
            engine_port=self.engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets,
            snow_gateway=self.snow,
            health_probe=self.health
        )
        job = ExecutionJob(
            job_id="j-08",
            correlation_id="EXEC-1008",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.transition_to(JobStatus.PARSED)
        job.request_approval(datetime.now(timezone.utc))
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "sre.lead", datetime.now(timezone.utc), "Approved"),
            datetime.now(timezone.utc)
        )

        with self.assertRaises(AuditIntegrityError):
            runner.run(job)

        self.assertFalse(self.engine.invoked, "Engine must NOT be invoked when audit write fails")
        self.assertFalse(self.lock_mgr.is_locked("f5-vip-01"))

    def test_cryptographic_merkle_hash_chain_integrity(self):
        """Verifies consecutive audit records form an immutable SHA256 Merkle chain."""
        runner = AnsibleJobRunner(
            engine_port=self.engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets,
            snow_gateway=self.snow,
            health_probe=self.health
        )
        job = ExecutionJob(
            job_id="j-09",
            correlation_id="EXEC-1009",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.transition_to(JobStatus.PARSED)
        job.request_approval(datetime.now(timezone.utc))
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "sre.lead", datetime.now(timezone.utc), "Approved"),
            datetime.now(timezone.utc)
        )

        runner.run(job)

        self.assertEqual(len(self.audit.ledger), 2)  # EXEC_START, EXEC_SUCCESS
        self.assertTrue(self.audit.verify_chain(), "Merkle chain must be cryptographically valid")

    # -------------------------------------------------------------
    # RULE 5: TARGET MUTEX MUTUAL EXCLUSION & CLEANUP
    # -------------------------------------------------------------
    def test_concurrent_run_on_same_resource_blocked(self):
        """Second job on locked resource raises ResourceLockedError."""
        self.lock_mgr.acquire("f5-vip-01")  # Already locked

        runner = AnsibleJobRunner(
            engine_port=self.engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets,
            snow_gateway=self.snow,
            health_probe=self.health
        )
        job = ExecutionJob(
            job_id="j-10",
            correlation_id="EXEC-1010",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.transition_to(JobStatus.PARSED)
        job.request_approval(datetime.now(timezone.utc))
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "sre.lead", datetime.now(timezone.utc), "Approved"),
            datetime.now(timezone.utc)
        )

        with self.assertRaises(ResourceLockedError):
            runner.run(job)
        self.assertFalse(self.engine.invoked)

    def test_secrets_and_mutex_revoked_even_on_unhandled_failure(self):
        """Engine crash guaranteed to invoke lock release and JIT secret lease revocation."""
        failing_engine = FakeExecutionEngine(exit_code=2, stdout_output="Ansible fatal error: host unreachable")
        runner = AnsibleJobRunner(
            engine_port=failing_engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets,
            snow_gateway=self.snow,
            health_probe=self.health
        )
        job = ExecutionJob(
            job_id="j-11",
            correlation_id="EXEC-1011",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.transition_to(JobStatus.PARSED)
        job.request_approval(datetime.now(timezone.utc))
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "sre.lead", datetime.now(timezone.utc), "Approved"),
            datetime.now(timezone.utc)
        )

        with self.assertRaises(RuntimeError):
            runner.run(job)

        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertFalse(self.lock_mgr.is_locked("f5-vip-01"))
        self.assertEqual(len(self.secrets.revoked_leases), 1)

    # -------------------------------------------------------------
    # RULE 6: POST-FLIGHT SEMANTIC HEALTH VERIFICATION (EXIT 0 != SUCCESS)
    # -------------------------------------------------------------
    def test_exit_zero_with_degraded_probes_fails_job(self):
        """Engine returns 0, but health probe fails -> job transitions to DEGRADED."""
        unhealthy_probe = InMemoryHealthProbeGateway(healthy=False)
        runner = AnsibleJobRunner(
            engine_port=self.engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets,
            snow_gateway=self.snow,
            health_probe=unhealthy_probe
        )
        job = ExecutionJob(
            job_id="j-12",
            correlation_id="EXEC-1012",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.transition_to(JobStatus.PARSED)
        job.request_approval(datetime.now(timezone.utc))
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "sre.lead", datetime.now(timezone.utc), "Approved"),
            datetime.now(timezone.utc)
        )

        with self.assertRaises(HealthProbeDegradedError):
            runner.run(job)

        self.assertEqual(job.status, JobStatus.DEGRADED)
        self.assertFalse(self.lock_mgr.is_locked("f5-vip-01"))

    # -------------------------------------------------------------
    # RULE 7: LOW RISK BYPASS & REJECTION FLOWS
    # -------------------------------------------------------------
    def test_low_risk_job_bypasses_maker_checker(self):
        """Low risk automations (e.g. Dev read/drain) proceed directly to QUEUED without approval."""
        low_risk_item = CatalogItem(
            id="cat-02",
            identifier="dev-cache-flush",
            name="Flush Redis Cache in Dev",
            engine=ExecutionEngineType.ANSIBLE,
            git_repo="git@github.com:pnc/dev-playbooks.git",
            git_commit_sha="b2c3d4e5f67890123456789abcdef01234567890",
            playbook_or_module_path="playbooks/flush_cache.yml",
            risk_tier=RiskTier.LOW,
            requires_maker_checker=False,
            requires_chg=False,
            input_schema={"type": "object", "required": [], "properties": {}}
        )
        job = ExecutionJob(
            job_id="j-13",
            correlation_id="EXEC-1013",
            catalog_item=low_risk_item,
            requester_id="junior.dev",
            target_resource_id="dev-redis-01",
            parameters={}
        )
        job.parse()
        job.transition_to(JobStatus.QUEUED, "Low risk bypasses Maker-Checker gate")
        self.assertEqual(job.status, JobStatus.QUEUED)

        runner = AnsibleJobRunner(
            engine_port=self.engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets
        )
        runner.run(job)
        self.assertEqual(job.status, JobStatus.SUCCESS)

    def test_maker_checker_rejection_marks_job_rejected(self):
        """Checker explicitly clicks Deny -> transitions cleanly to REJECTED."""
        job = ExecutionJob(
            job_id="j-14",
            correlation_id="EXEC-1014",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.request_approval(datetime.now(timezone.utc))

        decision = ApprovalDecision(
            decision="REJECT",
            approver_id="sre.lead",
            decided_at=datetime.now(timezone.utc),
            reason="Unapproved port change during freeze period"
        )
        job.apply_approval_decision(decision, datetime.now(timezone.utc))
        self.assertEqual(job.status, JobStatus.REJECTED)

    # -------------------------------------------------------------
    # RULE 8: ILLEGAL STATE TRANSITIONS & MUTABILITY PROTECTION
    # -------------------------------------------------------------
    def test_illegal_state_transition_from_pending_approval_directly_to_running(self):
        """Direct transition from PENDING_APPROVAL to RUNNING without QUEUED/LOCKED fails."""
        job = ExecutionJob(
            job_id="j-15",
            correlation_id="EXEC-1015",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001"
        )
        job.request_approval(datetime.now(timezone.utc))
        with self.assertRaises(StateTransitionError):
            job.transition_to(JobStatus.RUNNING, "Illegal bypass attempt")

    def test_parameter_missing_required_field_rejected(self):
        """Missing required parameter rejected during parameter validation."""
        bad_params = {"hostname": "f5-edge-01.pnc.com"}  # Missing vip_ip and cert_valid_days
        with self.assertRaises(ParameterValidationError) as ctx:
            ExecutionJob(
                job_id="j-16",
                correlation_id="EXEC-1016",
                catalog_item=self.catalog_item,
                requester_id="lavkush.kumar",
                target_resource_id="f5-vip-01",
                parameters=bad_params
            )
        self.assertIn("Missing required parameter", str(ctx.exception))

    def test_parameter_type_mismatch_rejected(self):
        """String supplied where integer is required rejected immediately."""
        bad_params = self.valid_params.copy()
        bad_params["cert_valid_days"] = "NINETY_DAYS"  # Expected integer
        with self.assertRaises(ParameterValidationError) as ctx:
            ExecutionJob(
                job_id="j-17",
                correlation_id="EXEC-1017",
                catalog_item=self.catalog_item,
                requester_id="lavkush.kumar",
                target_resource_id="f5-vip-01",
                parameters=bad_params
            )
        self.assertIn("must be numeric", str(ctx.exception))

    def test_storage_artifact_checksum_mismatch_aborts_run(self):
        """10GB artifact with invalid SHA256 checksum aborts execution prior to lock."""
        runner = AnsibleJobRunner(
            engine_port=self.engine,
            lock_manager=self.lock_mgr,
            audit_logger=self.audit,
            secret_provider=self.secrets,
            snow_gateway=self.snow,
            health_probe=self.health,
            storage_gateway=self.storage
        )
        job = ExecutionJob(
            job_id="j-18",
            correlation_id="EXEC-1018",
            catalog_item=self.catalog_item,
            requester_id="lavkush.kumar",
            target_resource_id="f5-vip-01",
            parameters=self.valid_params,
            servicenow_chg="CHG001",
            storage_artifact_uri="s3://bucket/rhel9.iso",
            storage_artifact_sha256="bad_corrupted_hash_000000000000000000000000"
        )
        job.parse()
        job.request_approval(datetime.now(timezone.utc))
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "sre.lead", datetime.now(timezone.utc), "Approved"),
            datetime.now(timezone.utc)
        )

        with self.assertRaises(ParameterValidationError) as ctx:
            runner.run(job)
        self.assertIn("checksum mismatch", str(ctx.exception))
        self.assertFalse(self.lock_mgr.is_locked("f5-vip-01"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
