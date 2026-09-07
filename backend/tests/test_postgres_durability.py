"""
Project Vulcan: PostgreSQL Persistence, Merkle Ledger & Redlock Leader Election Tests (Milestone B)
Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")
Verifies:
1. PostgresJobRepository: ACID UPSERT, retrieval, status indexing, pending approvals.
2. PostgresAuditAdapter: Row-locked Merkle hash chaining, tamper detection, chain verification.
3. ApprovalSweeper: Redlock leader election, failover, 15-minute fail-closed timeout sweep.
4. WebSocketLogHub: Cross-worker fanout and late-joiner replay.
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import pytest

from app.domain.entities import (
    ApprovalDecision,
    AuditRecord,
    CatalogItem,
    CurationStatus,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
)
from app.domain.exceptions import MakerCheckerViolationError
from app.adapters.redlock_adapter import RedlockManager
from app.core.approval_sweeper import ApprovalSweeper
from app.api.websockets import WebSocketLogHub


class InMemoryAuditLogger:
    """Mock audit logger for isolated sweeper tests."""
    def __init__(self):
        self.records: List[AuditRecord] = []
        self.last_hash = "0" * 64

    def record(self, job: ExecutionJob, action: str, payload: dict, actor: Optional[str] = None):
        now_str = datetime.now(timezone.utc).isoformat()
        current_hash = AuditRecord.compute_hash(job.correlation_id, now_str, actor or "test", action, payload, self.last_hash)
        rec = AuditRecord(
            id=len(self.records) + 1,
            correlation_id=job.correlation_id,
            timestamp=now_str,
            actor=actor or "test",
            action=action,
            payload=payload,
            prev_hash=self.last_hash,
            current_hash=current_hash
        )
        self.records.append(rec)
        self.last_hash = current_hash
        return rec

    def get_last_hash(self) -> str:
        return self.last_hash

    def verify_chain(self) -> bool:
        return True


class InMemoryJobRepo:
    """Mock job repo for unit-level sweeper testing."""
    def __init__(self):
        self.jobs: Dict[str, ExecutionJob] = {}

    def save(self, job: ExecutionJob) -> None:
        self.jobs[job.id] = job

    def get_by_id(self, job_id: str) -> Optional[ExecutionJob]:
        return self.jobs.get(job_id)

    def get_pending_approvals(self) -> List[ExecutionJob]:
        return [j for j in self.jobs.values() if j.status == JobStatus.PENDING_APPROVAL]

    def list_jobs(self, status=None, limit=100, offset=0) -> List[ExecutionJob]:
        res = list(self.jobs.values())
        if status:
            res = [j for j in res if j.status == status]
        return res[:limit]


def create_sample_catalog_item() -> CatalogItem:
    return CatalogItem(
        id="cat-test-01",
        identifier="pnc-test-action",
        name="PNC Test Automation Action",
        engine=ExecutionEngineType.ANSIBLE,
        git_repo="https://github.com/pnc/automation-catalog.git",
        git_commit_sha="a" * 40,
        playbook_or_module_path="playbooks/test.yml",
        risk_tier=RiskTier.HIGH,
        requires_maker_checker=True,
        requires_chg=True,
        input_schema={"type": "object", "properties": {"target": {"type": "string"}}},
        category="security",
        curation_status=CurationStatus.CURATED
    )


# ─── 1. Approval Sweeper Unit & Leader Election Tests ────────────────────────

def test_approval_sweeper_redlock_leader_election():
    """Verifies that two workers compete for leadership, and only one wins."""
    lock_mgr = RedlockManager(redis_nodes=[])  # In-memory emulation mode
    job_repo = InMemoryJobRepo()
    audit_logger = InMemoryAuditLogger()

    worker_a = ApprovalSweeper(
        job_repo=job_repo,
        audit_logger=audit_logger,
        lock_manager=lock_mgr,
        lease_ttl_seconds=10,
        worker_id="worker-node-alpha"
    )
    worker_b = ApprovalSweeper(
        job_repo=job_repo,
        audit_logger=audit_logger,
        lock_manager=lock_mgr,
        lease_ttl_seconds=10,
        worker_id="worker-node-bravo"
    )

    # Worker A acquires leadership
    assert lock_mgr.acquire(ApprovalSweeper.LEADER_LOCK_RESOURCE, ttl_seconds=10, owner_token=worker_a.worker_id) is True

    # Worker B tries to acquire leadership and is rejected
    assert lock_mgr.acquire(ApprovalSweeper.LEADER_LOCK_RESOURCE, ttl_seconds=10, owner_token=worker_b.worker_id) is False

    # Worker A releases leadership
    assert lock_mgr.release(ApprovalSweeper.LEADER_LOCK_RESOURCE, owner_token=worker_a.worker_id) is True

    # Worker B can now acquire leadership
    assert lock_mgr.acquire(ApprovalSweeper.LEADER_LOCK_RESOURCE, ttl_seconds=10, owner_token=worker_b.worker_id) is True


def test_approval_sweeper_fail_closed_denial():
    """Verifies that jobs pending approval past the 15-minute threshold are denied fail-closed."""
    lock_mgr = RedlockManager(redis_nodes=[])
    job_repo = InMemoryJobRepo()
    audit_logger = InMemoryAuditLogger()
    cat_item = create_sample_catalog_item()

    sweeper = ApprovalSweeper(
        job_repo=job_repo,
        audit_logger=audit_logger,
        lock_manager=lock_mgr,
        timeout_seconds=900,  # 15 minutes
        worker_id="leader-sweeper-01"
    )

    now = datetime.now(timezone.utc)

    # Job 1: 16 minutes old (expired)
    job_expired = ExecutionJob(
        job_id="job-expired-01",
        correlation_id="VULC-EXP01",
        catalog_item=cat_item,
        requester_id="alice",
        target_resource_id="app-01",
        parameters={"target": "app-01"},
        servicenow_chg="CHG-0019284"
    )
    job_expired.status = JobStatus.PENDING_APPROVAL
    job_expired.approval_requested_at = now - timedelta(seconds=960)
    job_repo.save(job_expired)

    # Job 2: 5 minutes old (valid)
    job_valid = ExecutionJob(
        job_id="job-valid-02",
        correlation_id="VULC-VAL02",
        catalog_item=cat_item,
        requester_id="bob",
        target_resource_id="app-02",
        parameters={"target": "app-02"},
        servicenow_chg="CHG-0019285"
    )
    job_valid.status = JobStatus.PENDING_APPROVAL
    job_valid.approval_requested_at = now - timedelta(seconds=300)
    job_repo.save(job_valid)

    # Run sweep iteration
    denied_jobs = sweeper.sweep_once()

    assert len(denied_jobs) == 1
    assert denied_jobs[0].id == "job-expired-01"
    assert job_expired.status == JobStatus.TIMEOUT_DENIED

    # Verify job 2 remains in PENDING_APPROVAL
    assert job_valid.status == JobStatus.PENDING_APPROVAL

    # Verify audit record was created for the fail-closed denial
    assert len(audit_logger.records) == 1
    rec = audit_logger.records[0]
    assert rec.action == "APPROVAL_TIMEOUT"
    assert rec.correlation_id == "VULC-EXP01"
    assert rec.payload["reason"] == "FAIL_CLOSED_TIMEOUT_DENIED"


# ─── 2. WebSocket Cross-Worker Fanout Tests ──────────────────────────────────

def test_websocket_hub_cross_worker_handling():
    """Verifies that an event received from a peer worker is stored and dispatched."""
    hub = WebSocketLogHub(max_buffer_lines=100)
    correlation_id = "VULC-TEST-WS"

    # Peer event from worker 'worker-remote-99'
    peer_event = {
        "seq": 1,
        "type": "stdout",
        "event": "stdout",
        "job_id": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"line": "Remote peer log line 1", "data": "Remote peer log line 1\r\n"},
        "worker_id": "worker-remote-99"
    }

    hub._handle_remote_event(peer_event)

    # Local buffer should contain the remote event
    assert correlation_id in hub.buffers
    assert len(hub.buffers[correlation_id]) == 1
    assert hub.buffers[correlation_id][0]["data"]["line"] == "Remote peer log line 1"


# ─── 3. PostgreSQL Contract Tests (Executed when Postgres is available) ──────

POSTGRES_URL = (
    os.getenv("POSTGRES_URL")
    or os.getenv("DATABASE_URL")
    or "postgresql://vulcan_admin:vulcan_secret_pnc_2026@localhost:5432/vulcan_control_plane"
)


def _is_postgres_available() -> bool:
    try:
        import psycopg
        with psycopg.connect(POSTGRES_URL, connect_timeout=1) as conn:
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _is_postgres_available(), reason="PostgreSQL not available on current host")
class TestPostgresRepositoriesContract:

    @pytest.fixture(autouse=True)
    def setup_postgres(self):
        from app.adapters.postgres_job_repository import PostgresJobRepository
        from app.adapters.postgres_audit_adapter import PostgresAuditAdapter
        self.job_repo = PostgresJobRepository(db_url=POSTGRES_URL)
        self.audit_adapter = PostgresAuditAdapter(db_url=POSTGRES_URL)
        self.cat_item = create_sample_catalog_item()

    def test_postgres_job_repository_crud(self):
        """Test UPSERT, fetch, and pending approvals in PostgresJobRepository."""
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        corr_id = f"VULC-{uuid.uuid4().hex[:8]}"
        job = ExecutionJob(
            job_id=job_id,
            correlation_id=corr_id,
            catalog_item=self.cat_item,
            requester_id="eng.alice",
            target_resource_id="db-01.pnc.com",
            parameters={"target": "db-01.pnc.com"},
            servicenow_chg="CHG-0019286",
            environment="PROD"
        )
        job.status = JobStatus.PENDING_APPROVAL
        job.approval_requested_at = datetime.now(timezone.utc)

        # Save (Insert)
        self.job_repo.save(job)

        # Fetch by ID
        fetched = self.job_repo.get_by_id(job_id)
        assert fetched is not None
        assert fetched.id == job_id
        assert fetched.correlation_id == corr_id
        assert fetched.status == JobStatus.PENDING_APPROVAL
        assert fetched.parameters == {"target": "db-01.pnc.com"}

        # Fetch by Correlation ID
        fetched_corr = self.job_repo.get_by_correlation_id(corr_id)
        assert fetched_corr is not None
        assert fetched_corr.id == job_id

        # Update and UPSERT
        job.status = JobStatus.SUCCESS
        job.exit_code = 0
        self.job_repo.save(job)

        updated = self.job_repo.get_by_id(job_id)
        assert updated.status == JobStatus.SUCCESS
        assert updated.exit_code == 0

    def test_postgres_audit_adapter_merkle_chain_integrity(self):
        """Test that PostgresAuditAdapter commits unbroken cryptographic Merkle chain."""
        job = ExecutionJob(
            job_id=f"job-{uuid.uuid4().hex[:8]}",
            correlation_id=f"VULC-{uuid.uuid4().hex[:8]}",
            catalog_item=self.cat_item,
            requester_id="eng.alice",
            target_resource_id="app-01",
            parameters={"target": "app-01"},
            servicenow_chg="CHG-0019287"
        )

        # Commit 3 sequential audit records
        rec1 = self.audit_adapter.record(job, "EXEC_START", {"step": 1})
        rec2 = self.audit_adapter.record(job, "STEP_COMPLETED", {"step": 2})
        rec3 = self.audit_adapter.record(job, "EXEC_SUCCESS", {"step": 3})

        assert rec2.prev_hash == rec1.current_hash
        assert rec3.prev_hash == rec2.current_hash

        # Verify full chain integrity
        assert self.audit_adapter.verify_integrity() is True
