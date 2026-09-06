"""
Project Vulcan: State Machine & Governance Mutation Test Suite (BKND-02 / INV-01)
Authority: Robert C. Martin ("Uncle Bob") & Platform Safety Committee

Asserts that no code mutation, transition matrix tweak, or parameter bypass
can violate banking invariants:
1. Universal Maker-Checker: Self-approval is mathematically impossible.
2. Complete Transition Closure: All illegal state transitions fail-closed.
3. Fail-Closed Approval Sweeper: Expired approval windows reject permanently.
4. Post-Flight Health Integrity: Degraded probes NEVER result in SUCCESS.
5. Steel Cage INV-1: CANDIDATE modules cannot be executed.
6. Maintenance Window Lock: Out-of-window executions block without RUNNING.
7. Terminal State Immutability: Once finished, jobs can never change state.
8. Double-Approval Replay: Already approved jobs cannot be re-approved.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import pytest

from app.domain.entities import (
    ApprovalDecision,
    AuditRecord,
    CatalogItem,
    CurationStatus,
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
    PolicyViolationError,
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
from app.use_cases.runner import AnsibleJobRunner


# =====================================================================
# TEST FIXTURES & DOUBLES
# =====================================================================

def make_catalog_item(
    identifier: str = "net-f5-cert-renew",
    risk_tier: RiskTier = RiskTier.HIGH,
    curation_status: CurationStatus = CurationStatus.CURATED,
    git_commit_sha: str = "a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e"
) -> CatalogItem:
    return CatalogItem(
        id="item-001",
        identifier=identifier,
        name="F5 SSL Certificate Renewal",
        engine=ExecutionEngineType.ANSIBLE,
        git_repo="git@github.internal.bank.com:automation/playbooks.git",
        git_commit_sha=git_commit_sha,
        playbook_or_module_path="playbooks/renew_f5_cert.yml",
        risk_tier=risk_tier,
        requires_maker_checker=True,
        requires_chg=True,
        input_schema={
            "type": "object",
            "properties": {
                "vip_ip": {"type": "string", "pattern": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"},
                "hostname": {"type": "string"},
                "cert_valid_days": {"type": "integer", "minimum": 1, "maximum": 365}
            },
            "required": ["vip_ip", "hostname", "cert_valid_days"]
        },
        category="network",
        curation_status=curation_status,
        tags=["f5", "ssl", "network"]
    )


def make_job(
    catalog_item: Optional[CatalogItem] = None,
    requester_id: str = "alice_dev",
    target_resource_id: str = "f5-edge-01.pnc.com",
    parameters: Optional[Dict[str, Any]] = None
) -> ExecutionJob:
    item = catalog_item or make_catalog_item()
    params = parameters or {
        "vip_ip": "10.0.1.50",
        "hostname": "vip-edge.pnc.com",
        "cert_valid_days": 90
    }
    return ExecutionJob(
        job_id="job-mut-001",
        correlation_id="corr-mut-001",
        catalog_item=item,
        requester_id=requester_id,
        target_resource_id=target_resource_id,
        parameters=params,
        servicenow_chg="CHG0099881",
        environment="PROD"
    )


class StubLockManager(ILockManager):
    def __init__(self):
        self._locks = set()
    def acquire(self, resource_id: str, ttl_seconds: int = 1800, owner_token: Optional[str] = None) -> bool:
        if resource_id in self._locks:
            return False
        self._locks.add(resource_id)
        return True
    def release(self, resource_id: str, owner_token: Optional[str] = None) -> bool:
        self._locks.discard(resource_id)
        return True
    def is_locked(self, resource_id: str) -> bool:
        return resource_id in self._locks


class StubAuditLogger(IAuditLogger):
    def __init__(self):
        self.ledger: List[AuditRecord] = []
        self._last_hash = "0" * 64
    def record(self, job: ExecutionJob, action: str, payload: Dict[str, Any], actor: Optional[str] = None) -> AuditRecord:
        rec_id = len(self.ledger) + 1
        now_str = datetime.now(timezone.utc).isoformat()
        actor_id = actor or getattr(job, "dispatched_by", None) or job.requester_id
        current_hash = AuditRecord.compute_hash(
            job.correlation_id, now_str, actor_id, action, payload, self._last_hash
        )
        rec = AuditRecord(
            id=rec_id,
            correlation_id=job.correlation_id,
            timestamp=now_str,
            actor=actor_id,
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
        return True


class StubSecretProvider(ISecretProvider):
    def checkout_ephemeral_secret(self, target: str) -> EphemeralSecretLease:
        return EphemeralSecretLease(
            lease_id="lease-001",
            secrets={"DYNAMIC_SSH_KEY": "privkey-mock-data"},
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
    def revoke_ephemeral_secret(self, lease: EphemeralSecretLease) -> None:
        pass


class StubServiceNowGateway(IServiceNowGateway):
    def __init__(self, window_open: bool = True):
        self.window_open = window_open
    def validate_chg(self, chg_number: str) -> Dict[str, Any]:
        return {"chg_number": chg_number, "state": "Scheduled"}
    def is_within_maintenance_window(self, chg_number: str, check_time: datetime) -> bool:
        return self.window_open
    def update_work_notes(self, chg_number: str, notes: str, new_state: Optional[str] = None) -> None:
        pass


class StubExecutionEngine(IExecutionEngine):
    def __init__(self, exit_code: int = 0, stdout: str = "PLAY RECAP: ok=3 changed=1 failed=0"):
        self.exit_code = exit_code
        self.stdout = stdout
    def execute(self, job: ExecutionJob, event_callback: Any, secrets: Dict[str, str]) -> EngineExecutionResult:
        if event_callback:
            event_callback(self.stdout)
        return EngineExecutionResult(status="SUCCESS" if self.exit_code == 0 else "FAILED", exit_code=self.exit_code, stdout=self.stdout)


class StubHealthProbeGateway(IHealthProbeGateway):
    def __init__(self, is_healthy: bool = True):
        self.is_healthy = is_healthy
    def probe(self, job: ExecutionJob) -> HealthCheckResult:
        return HealthCheckResult(
            is_healthy=self.is_healthy,
            latency_ms=12.5 if self.is_healthy else 999.0,
            error_rate=0.0 if self.is_healthy else 0.85,
            details={"probe": "ok"} if self.is_healthy else {"probe": "failed", "error": "Endpoint unhealthy"}
        )


# =====================================================================
# MUTATION TESTS
# =====================================================================

class TestStateMachineMutations:
    """Rigorous mutation testing of state machine and domain invariants."""

    def test_mutation_self_approval_bypass_rejected(self):
        """Mutation 1: Self-approval must be blocked unconditionally."""
        job = make_job(requester_id="alice_dev")
        now = datetime.now(timezone.utc)
        job.request_approval(now)

        # Mutation: Requester attempts to approve own execution via apply_approval_decision
        decision = ApprovalDecision(
            decision="APPROVE",
            approver_id="alice_dev",  # Mutated to self
            decided_at=now,
            reason="Self approval attempt"
        )
        with pytest.raises(MakerCheckerViolationError) as exc:
            job.apply_approval_decision(decision, evaluated_at=now)
        assert "Separation of Duties Violation" in str(exc.value)
        assert job.status == JobStatus.PENDING_APPROVAL

        # Mutation: Requester attempts to approve own execution via enforce_maker_checker
        with pytest.raises(MakerCheckerViolationError) as exc2:
            job.enforce_maker_checker("alice_dev", decided_at=now)
        assert "cannot approve own execution" in str(exc2.value)
        assert job.status == JobStatus.PENDING_APPROVAL

    def test_mutation_all_illegal_state_transitions_rejected(self):
        """Mutation 2: Complete Transition Closure — every illegal (from, to) pair must fail."""
        legal_transitions = ExecutionJob._TRANSITIONS
        all_statuses = list(JobStatus)
        illegal_tested = 0

        for source in all_statuses:
            allowed = legal_transitions.get(source, [])
            for target in all_statuses:
                if target not in allowed:
                    # Construct a job and force its initial status to source
                    job = make_job()
                    job.status = source

                    with pytest.raises(StateTransitionError) as exc:
                        job.transition_to(target, reason="Fuzz mutation test")
                    assert f"Illegal state transition from [{source.value}] to [{target.value}]" in str(exc.value)
                    assert job.status == source  # Status must remain uncorrupted
                    illegal_tested += 1

        # There are 14 states, each with at most 3-4 legal transitions; >150 illegal pairs must be verified
        assert illegal_tested >= 150, f"Expected >= 150 illegal transition pairs tested, got {illegal_tested}"

    def test_mutation_approval_timeout_bypass_rejected(self):
        """Mutation 3: Approval timeout after 900s must reject fail-closed."""
        job = make_job(requester_id="alice_dev")
        t0 = datetime.now(timezone.utc)
        job.request_approval(t0)

        # Mutation: Checker signs off at T0 + 901s (past 15-minute window)
        t_expired = t0 + timedelta(seconds=901)
        decision = ApprovalDecision(
            decision="APPROVE",
            approver_id="bob_lead",
            decided_at=t_expired,
            reason="Approved but late"
        )
        with pytest.raises(ApprovalTimeoutError) as exc:
            job.apply_approval_decision(decision, evaluated_at=t_expired, timeout_seconds=900)

        assert "Approval window expired" in str(exc.value)
        assert job.status == JobStatus.TIMEOUT_DENIED

        # Subsequent approval attempt must be rejected because TIMEOUT_DENIED is terminal
        with pytest.raises(StateTransitionError):
            job.apply_approval_decision(decision, evaluated_at=t_expired)

    def test_mutation_skip_approval_straight_to_running_rejected(self):
        """Mutation 4: Direct jumps from SUBMITTED or PENDING_APPROVAL to RUNNING or SUCCESS."""
        job = make_job()
        assert job.status == JobStatus.SUBMITTED

        # Try jumping directly to RUNNING
        with pytest.raises(StateTransitionError):
            job.transition_to(JobStatus.RUNNING)

        # Try jumping directly to SUCCESS
        with pytest.raises(StateTransitionError):
            job.transition_to(JobStatus.SUCCESS)

        # Move to PENDING_APPROVAL
        job.request_approval(datetime.now(timezone.utc))
        assert job.status == JobStatus.PENDING_APPROVAL

        # Try jumping directly to RUNNING without QUEUED / LOCKED
        with pytest.raises(StateTransitionError):
            job.transition_to(JobStatus.RUNNING)

    def test_mutation_candidate_execution_blocked_under_inv1(self):
        """Mutation 5: Candidate modules cannot execute under INV-1."""
        candidate_item = make_catalog_item(
            identifier="candidate.terraform.aws.vpc-deploy-12",
            curation_status=CurationStatus.CANDIDATE
        )
        assert candidate_item.can_execute() is False

        # Attempt to run a candidate item via AnsibleJobRunner
        job = make_job(catalog_item=candidate_item)
        now = datetime.now(timezone.utc)
        job.request_approval(now)
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "bob_lead", now, "Signed off"),
            evaluated_at=now
        )
        assert job.status == JobStatus.QUEUED

        runner = AnsibleJobRunner(
            engine_port=StubExecutionEngine(),
            lock_manager=StubLockManager(),
            audit_logger=StubAuditLogger(),
            secret_provider=StubSecretProvider(),
            snow_gateway=StubServiceNowGateway(),
            health_probe=StubHealthProbeGateway()
        )

        with pytest.raises(PolicyViolationError) as exc:
            runner.run(job)
        assert "INV-1" in str(exc.value) or "CANDIDATE" in str(exc.value) or "not authorized for execution" in str(exc.value)

    def test_mutation_post_flight_probe_failure_blocks_success(self):
        """Mutation 6: Probe failure must trigger DEGRADED / FAILED, never SUCCESS."""
        job = make_job()
        now = datetime.now(timezone.utc)
        job.request_approval(now)
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "bob_lead", now, "Signed off"),
            evaluated_at=now
        )
        assert job.status == JobStatus.QUEUED

        # Engine succeeds (exit 0) but health probe fails
        runner = AnsibleJobRunner(
            engine_port=StubExecutionEngine(exit_code=0),
            lock_manager=StubLockManager(),
            audit_logger=StubAuditLogger(),
            secret_provider=StubSecretProvider(),
            snow_gateway=StubServiceNowGateway(),
            health_probe=StubHealthProbeGateway(is_healthy=False)
        )

        with pytest.raises(HealthProbeDegradedError):
            runner.run(job)

        # Crucial invariant: Must NOT be SUCCESS
        assert job.status in [JobStatus.DEGRADED, JobStatus.FAILED, JobStatus.REVERTED]
        assert job.status != JobStatus.SUCCESS

    def test_mutation_maintenance_window_bypass_blocked(self):
        """Mutation 7: Maintenance window closed must block execution before RUNNING."""
        job = make_job()
        now = datetime.now(timezone.utc)
        job.request_approval(now)
        job.apply_approval_decision(
            ApprovalDecision("APPROVE", "bob_lead", now, "Signed off"),
            evaluated_at=now
        )
        assert job.status == JobStatus.QUEUED

        # ServiceNow reports window is closed
        runner = AnsibleJobRunner(
            engine_port=StubExecutionEngine(),
            lock_manager=StubLockManager(),
            audit_logger=StubAuditLogger(),
            secret_provider=StubSecretProvider(),
            snow_gateway=StubServiceNowGateway(window_open=False),
            health_probe=StubHealthProbeGateway()
        )

        with pytest.raises(MaintenanceWindowClosedError):
            runner.run(job)

        # Job must be in QUEUED (or FAILED), never progressed to RUNNING or SUCCESS
        assert job.status != JobStatus.RUNNING
        assert job.status != JobStatus.SUCCESS

    def test_mutation_terminal_state_immutability(self):
        """Mutation 8: Terminal states (SUCCESS, FAILED, TIMEOUT_DENIED, REJECTED, REVERTED) cannot transition."""
        terminal_states = [
            JobStatus.SUCCESS,
            JobStatus.FAILED,
            JobStatus.TIMEOUT_DENIED,
            JobStatus.REJECTED,
            JobStatus.REVERTED,
        ]
        all_statuses = list(JobStatus)

        for term in terminal_states:
            job = make_job()
            job.status = term
            assert ExecutionJob._TRANSITIONS[term] == [], f"Terminal state {term} has non-empty transitions"

            for target in all_statuses:
                with pytest.raises(StateTransitionError):
                    job.transition_to(target, reason="Attempted transition from terminal state")
                assert job.status == term

    def test_mutation_double_approval_blocked(self):
        """Mutation 9: An already approved/queued job cannot accept a second approval decision."""
        job = make_job(requester_id="alice_dev")
        now = datetime.now(timezone.utc)
        job.request_approval(now)

        decision1 = ApprovalDecision("APPROVE", "bob_lead", now, "First approval")
        job.apply_approval_decision(decision1, evaluated_at=now)
        assert job.status == JobStatus.QUEUED

        decision2 = ApprovalDecision("APPROVE", "charlie_lead", now + timedelta(seconds=10), "Second approval")
        with pytest.raises(StateTransitionError) as exc:
            job.apply_approval_decision(decision2, evaluated_at=now + timedelta(seconds=10))
        assert "Cannot apply approval decision in status [QUEUED]" in str(exc.value)
        assert job.approver_id == "bob_lead"
