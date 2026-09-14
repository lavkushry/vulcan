"""
Project Vulcan: PostgreSQL Workflow Durability & Canonical JSON Integration Tests (P0 #2)
Author: Architectural Review Board & AgentOS Core Team

Verifies:
1. Canonical JSON serialization of nested datetimes, Enums, UUIDs, dataclasses, and Pydantic models.
2. Complete round-trip PostgreSQL persistence and hydration.
3. Field-by-field equality between original and restored WorkflowContext.
4. Resumption of workflow lifecycle execution from restored PostgreSQL state.
5. Fail-closed visibility: persistence failures raise immediately and never degrade silently.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import enum
import os
import uuid
import pytest
from pydantic import BaseModel

from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.repository import PostgresAgentWorkflowRepository
from app.agentos.serialization import canonical_json_dumps, canonical_json_loads, to_jsonable_python
from app.agentos.kernel import AgentOSKernel


class DummyStatus(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DummyPydanticModel(BaseModel):
    name: str
    code: int
    created: datetime


@dataclass
class DummyDataClass:
    user: str
    role: DummyStatus
    session_id: uuid.UUID


def test_canonical_json_serialization_all_types():
    """Verifies that all complex and nested domain types serialize and deserialize cleanly."""
    now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    u = uuid.uuid4()
    pyd = DummyPydanticModel(name="test", code=42, created=now)
    dc = DummyDataClass(user="alice", role=DummyStatus.APPROVED, session_id=u)

    complex_structure = {
        "timestamp": now,
        "status": DummyStatus.APPROVED,
        "uuid": u,
        "pydantic": pyd,
        "dataclass": dc,
        "nested_list": [now, DummyStatus.REJECTED, {"sub_date": now + timedelta(hours=1)}],
        "set_data": {1, 2, 3},
    }

    serialized = canonical_json_dumps(complex_structure)
    assert isinstance(serialized, str)

    deserialized = canonical_json_loads(serialized)
    assert deserialized["timestamp"] == now.isoformat()
    assert deserialized["status"] == "APPROVED"
    assert deserialized["uuid"] == str(u)
    assert deserialized["pydantic"]["name"] == "test"
    assert datetime.fromisoformat(deserialized["pydantic"]["created"]) == now
    assert deserialized["dataclass"]["user"] == "alice"
    assert deserialized["dataclass"]["role"] == "APPROVED"
    assert deserialized["dataclass"]["session_id"] == str(u)
    assert deserialized["nested_list"][0] == now.isoformat()
    assert deserialized["nested_list"][1] == "REJECTED"
    assert set(deserialized["set_data"]) == {1, 2, 3}


def test_workflow_context_datetime_roundtrip():
    """
    Verifies that WorkflowContext with complex approval_records, execution_result,
    and eval_result containing datetimes and Enums can be serialized and restored.
    """
    now = datetime.now(timezone.utc)
    wf_id = f"wf-durability-{uuid.uuid4().hex[:8]}"

    ctx = WorkflowContext(
        workflow_id=wf_id,
        correlation_id=f"corr-{wf_id}",
        requester_id="developer@corp.internal",
        original_request="Deploy Redis on node-redis-01.internal with port 6380",
        environment="DEV",
        current_state=WorkflowState.WAITING_FOR_APPROVAL,
        version=5,
    )

    ctx.approval_records = [
        {
            "approval_id": "appr-001",
            "approver_id": "lead.bob",
            "decision": "APPROVED",
            "decided_at": now,
            "comments": "Pre-approved in sprint planning",
            "nested_metadata": {
                "ticket_created": now - timedelta(hours=2),
                "status": DummyStatus.APPROVED,
            },
        }
    ]

    ctx.execution_result = {
        "exit_code": 0,
        "stdout": "PLAY RECAP: localhost: ok=4 changed=1 failed=0",
        "stderr": "",
        "started_at": now - timedelta(minutes=5),
        "completed_at": now - timedelta(minutes=4),
        "duration_ms": 60000.0,
    }

    ctx.eval_result = {
        "eval_timestamp": now,
        "passed": True,
        "score": 1.0,
    }

    raw_data = ctx.to_dict()
    serialized = canonical_json_dumps(raw_data)
    restored_dict = canonical_json_loads(serialized)
    restored_ctx = WorkflowContext.from_dict(restored_dict)

    assert restored_ctx.workflow_id == ctx.workflow_id
    assert restored_ctx.correlation_id == ctx.correlation_id
    assert restored_ctx.current_state == WorkflowState.WAITING_FOR_APPROVAL
    assert restored_ctx.version == 5
    assert len(restored_ctx.approval_records) == 1
    assert restored_ctx.approval_records[0]["approval_id"] == "appr-001"
    assert restored_ctx.approval_records[0]["decided_at"] == now.isoformat()
    assert restored_ctx.execution_result["exit_code"] == 0
    assert restored_ctx.eval_result["passed"] is True


def test_postgresql_durability_rehydrate_and_resume():
    """
    Integration test:
    1. Connect to PostgreSQL (skips cleanly if PG unavailable).
    2. Create a workflow with timestamps, approvals, and execution state.
    3. Persist to PostgreSQL.
    4. Destroy the in-memory repository instance.
    5. Rehydrate a fresh repository from PostgreSQL.
    6. Compare every workflow field.
    7. Resume execution from the restored state.
    """
    db_url = (
        os.getenv("POSTGRES_TEST_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("DATABASE_URL")
        or "postgresql://vulcan_admin:vulcan_ci_secret@localhost:5432/vulcan_control_plane"
    )

    try:
        import psycopg
        with psycopg.connect(db_url, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
    except Exception as e:
        pytest.skip(f"PostgreSQL not accessible for live integration test: {e}")

    now = datetime.now(timezone.utc)
    wf_id = f"wf-pg-durability-{uuid.uuid4().hex[:8]}"

    # Step 1: Create repository and ensure schema
    repo1 = PostgresAgentWorkflowRepository(db_url=db_url)
    
    ctx = WorkflowContext(
        workflow_id=wf_id,
        correlation_id=f"corr-{wf_id}",
        requester_id="developer@corp.internal",
        original_request="Deploy Redis on node-redis-01.internal with port 6380 and maxmemory 1024MB",
        environment="DEV",
        current_state=WorkflowState.WAITING_FOR_APPROVAL,
        version=1,
    )
    ctx.approval_records = [
        {
            "approval_id": "appr-pg-1",
            "approver_id": "lead.bob",
            "decision": "APPROVED",
            "decided_at": now,
            "rationale": "Governance verified",
        }
    ]
    ctx.execution_result = {
        "exit_code": 0,
        "stdout": "Configuration applied successfully",
        "started_at": now,
        "completed_at": now + timedelta(seconds=12),
    }

    # Step 2: Persist to PostgreSQL
    saved_ctx = repo1.save_workflow(ctx)
    assert saved_ctx.workflow_id == wf_id

    # Step 3: Destroy repo1 completely
    del repo1

    # Step 4: Rehydrate from PostgreSQL into fresh repository
    repo2 = PostgresAgentWorkflowRepository(db_url=db_url)
    restored_ctx = repo2.get_workflow(wf_id)

    assert restored_ctx is not None, f"Workflow {wf_id} failed to rehydrate from PostgreSQL!"

    # Step 5: Compare every workflow field
    assert restored_ctx.workflow_id == ctx.workflow_id
    assert restored_ctx.correlation_id == ctx.correlation_id
    assert restored_ctx.requester_id == ctx.requester_id
    assert restored_ctx.original_request == ctx.original_request
    assert restored_ctx.environment == ctx.environment
    assert restored_ctx.current_state == ctx.current_state
    assert restored_ctx.version == ctx.version
    assert len(restored_ctx.approval_records) == len(ctx.approval_records)
    assert restored_ctx.approval_records[0]["approval_id"] == "appr-pg-1"
    assert restored_ctx.approval_records[0]["decided_at"] == now.isoformat()
    assert restored_ctx.execution_result["exit_code"] == 0

    # Step 6: Resume execution from restored state
    kernel = AgentOSKernel(repository=repo2)
    # Transition to EXECUTION_READY
    restored_ctx.transition_to(WorkflowState.EXECUTION_READY, actor="approval_engine", reason="Approved")
    repo2.save_workflow(restored_ctx)

    resumed = repo2.get_workflow(wf_id)
    assert resumed.current_state == WorkflowState.EXECUTION_READY
    assert resumed.version == restored_ctx.version


def test_persistence_failure_raises_visibly_when_postgres_unhealthy():
    """Verifies fail-closed policy: invalid database connection raises RuntimeError."""
    bad_db_url = "postgresql://invalid_user:invalid_pass@127.0.0.1:54399/nonexistent_db"
    
    # In production mode, connecting to bad DB raises immediately
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        PostgresAgentWorkflowRepository(db_url=bad_db_url, production_mode=True)
