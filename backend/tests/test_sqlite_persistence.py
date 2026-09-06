"""
Project Vulcan: SQLite Persistence & Recovery Tests
Tests durable persistence of ExecutionJob, Merkle Audit Ledger, and Catalog
verifying zero data loss across simulated process restarts.
"""
import os
import tempfile
import uuid
from datetime import datetime, timezone
import pytest

from app.adapters.sqlite_repositories import (
    SQLiteAuditLedgerRepository,
    SQLiteCatalogRepository,
    SQLiteJobRepository,
)
from app.catalog_data import get_catalog_items
from app.domain.entities import (
    ApprovalDecision,
    AuditRecord,
    CatalogItem,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
)


class TestSQLitePersistence:
    """Verifies that all repositories persist and recover data accurately."""

    @pytest.fixture
    def temp_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_catalog_repository_seed_and_retrieve(self, temp_db):
        repo = SQLiteCatalogRepository(db_path=temp_db)
        catalog = get_catalog_items()
        seeded = repo.seed_if_empty(catalog)
        assert seeded == len(catalog)

        # Re-seeding should be idempotent (0 inserted)
        assert repo.seed_if_empty(catalog) == 0

        # Retrieve all items
        items = repo.list_all()
        assert len(items) == len(catalog)

        # Retrieve specific item
        item = repo.get_by_identifier("net-f5-cert-renew")
        assert item is not None
        assert item.name == "F5 BIG-IP SSL Certificate Renewal"
        assert item.risk_tier == RiskTier.HIGH
        assert item.engine == ExecutionEngineType.ANSIBLE
        assert item.requires_maker_checker is True

    def test_job_repository_save_and_restart_recovery(self, temp_db):
        catalog = get_catalog_items()
        cat_item = next(i for i in catalog if i.identifier == "net-f5-cert-renew")

        # Instance 1: Create and save job
        repo1 = SQLiteJobRepository(db_path=temp_db, catalog=catalog)
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        corr_id = f"EXEC-{uuid.uuid4().hex[:6].upper()}"

        job = ExecutionJob(
            job_id=job_id,
            correlation_id=corr_id,
            catalog_item=cat_item,
            requester_id="eng.alice",
            target_resource_id="f5-vip-01.pnc.com",
            parameters={"hostname": "f5-vip-01.pnc.com", "vip_ip": "10.200.1.50", "cert_valid_days": 90},
            servicenow_chg="CHG001",
            environment="PROD",
        )
        job.parse()
        job.request_approval(datetime.now(timezone.utc))
        repo1.save(job)

        # Instance 2 (Simulate process restart with fresh repository instance)
        repo2 = SQLiteJobRepository(db_path=temp_db, catalog=catalog)
        recovered = repo2.get_by_id(job_id)

        assert recovered is not None
        assert recovered.id == job_id
        assert recovered.correlation_id == corr_id
        assert recovered.status == JobStatus.PENDING_APPROVAL
        assert recovered.requester_id == "eng.alice"
        assert recovered.target_resource_id == "f5-vip-01.pnc.com"
        assert recovered.parameters["cert_valid_days"] == 90
        assert recovered.servicenow_chg == "CHG001"

        # Also retrieve by correlation_id
        by_corr = repo2.get_by_id(corr_id)
        assert by_corr is not None
        assert by_corr.id == job_id

        # Apply approval and verify update persists
        decision = ApprovalDecision(
            decision="APPROVE",
            approver_id="lead.bob",
            decided_at=datetime.now(timezone.utc),
            reason="Verified maintenance window",
            chg_number="CHG001",
        )
        recovered.apply_approval_decision(decision, datetime.now(timezone.utc), timeout_seconds=900)
        repo2.save(recovered)

        # Instance 3 (Another restart): verify approved status persists
        repo3 = SQLiteJobRepository(db_path=temp_db, catalog=catalog)
        approved_job = repo3.get_by_id(job_id)
        assert approved_job is not None
        assert approved_job.status == JobStatus.QUEUED
        assert approved_job.approver_id == "lead.bob"

    def test_audit_ledger_merkle_chain_integrity_and_tamper_detection(self, temp_db):
        repo = SQLiteAuditLedgerRepository(db_path=temp_db)

        # Append 3 valid records forming a hash chain
        genesis = "0" * 64
        r1_hash = AuditRecord.compute_hash("EXEC-1", "2026-09-06T12:00:00Z", "eng.alice", "SUBMIT", {"action": "create"}, genesis)
        r1 = AuditRecord(1, "EXEC-1", "2026-09-06T12:00:00Z", "eng.alice", "SUBMIT", {"action": "create"}, genesis, r1_hash)
        repo.append(r1)

        r2_hash = AuditRecord.compute_hash("EXEC-1", "2026-09-06T12:01:00Z", "lead.bob", "APPROVE", {"reason": "ok"}, r1_hash)
        r2 = AuditRecord(2, "EXEC-1", "2026-09-06T12:01:00Z", "lead.bob", "APPROVE", {"reason": "ok"}, r1_hash, r2_hash)
        repo.append(r2)

        r3_hash = AuditRecord.compute_hash("EXEC-1", "2026-09-06T12:02:00Z", "runner", "EXEC_START", {"engine": "ansible"}, r2_hash)
        r3 = AuditRecord(3, "EXEC-1", "2026-09-06T12:02:00Z", "runner", "EXEC_START", {"engine": "ansible"}, r2_hash, r3_hash)
        repo.append(r3)

        # Verify chain integrity
        assert repo.verify_integrity() is True
        chain = repo.get_chain("EXEC-1")
        assert len(chain) == 3

        # Tamper detection: modify a record directly in SQLite
        conn = repo._conn
        with repo._lock:
            conn.execute("UPDATE audit_ledger SET payload = ? WHERE id = 2", ('{"tampered": true}',))
            conn.commit()

        # Integrity verification must now FAIL
        assert repo.verify_integrity() is False
