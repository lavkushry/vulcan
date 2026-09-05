"""
Project Vulcan: REST API Presentation Routes
Author: Alex Xu & Uncle Bob
Exposes enterprise endpoints for Intent Resolution, Job Orchestration, Maker-Checker, and 10GB S3 Storage.
"""
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.api.websockets import ws_hub
from app.config import container
from app.domain.entities import ExecutionJob, JobStatus, RiskTier
from app.domain.exceptions import (
    ApprovalTimeoutError,
    DomainError,
    MakerCheckerViolationError,
    ParameterValidationError,
    ResourceLockedError,
    SecretLintError,
    StateTransitionError,
)

router = APIRouter(prefix="/api/v1")


# =====================================================================
# PYDANTIC SCHEMAS (PRESENTATION BOUNDARY)
# =====================================================================

class ResolveIntentRequest(BaseModel):
    prompt: str
    ambient_params: Optional[Dict[str, Any]] = None

class CreateJobRequest(BaseModel):
    catalog_identifier: str
    target_resource_id: str
    requester_id: str
    parameters: Dict[str, Any]
    servicenow_chg: Optional[str] = None
    storage_artifact_uri: Optional[str] = None
    storage_artifact_sha256: Optional[str] = None

class ApproveJobRequest(BaseModel):
    approver_id: str
    decision: str = "APPROVE"  # "APPROVE" | "REJECT"
    reason: str = "Authorized by Checker"
    chg_number: Optional[str] = None

class MultipartInitiateRequest(BaseModel):
    file_name: str
    file_size_bytes: int
    sha256_checksum: str
    job_id: str

class MultipartCompleteRequest(BaseModel):
    upload_id: str
    s3_key: str
    parts: List[Dict[str, Any]]


# =====================================================================
# ROUTES
# =====================================================================

@router.get("/health")
def get_health():
    """System Health & Audit Integrity Check."""
    is_audit_valid = container.audit_logger.verify_chain()
    return {
        "status": "OPERATIONAL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "catalog_size": len(container.catalog),
        "active_jobs_count": len(container.jobs),
        "audit_chain_valid": is_audit_valid,
        "audit_tip_hash": container.audit_logger.get_last_hash(),
    }


@router.get("/catalog")
def list_catalog():
    """Returns list of immutable playbooks in the enterprise catalog."""
    return [
        {
            "id": item.id,
            "identifier": item.identifier,
            "name": item.name,
            "engine": item.engine.value,
            "git_repo": item.git_repo,
            "git_commit_sha": item.git_commit_sha,
            "risk_tier": item.risk_tier.value,
            "requires_maker_checker": item.requires_maker_checker,
            "requires_chg": item.requires_chg,
            "input_schema": item.input_schema,
        }
        for item in container.catalog
    ]


@router.post("/intent/resolve")
def resolve_intent(req: ResolveIntentRequest):
    """
    AI Reasoning Subsystem (The LLM OS):
    Hybrid RRF Retrieval + Pydantic Slot Filling within 2,500 token budget.
    """
    result = container.intent_resolver.resolve(req.prompt, req.ambient_params)
    return result.to_dict()


@router.get("/jobs")
def list_jobs():
    """List all jobs in the control plane."""
    return [
        {
            "id": job.id,
            "correlation_id": job.correlation_id,
            "playbook_identifier": job.catalog_item.identifier,
            "playbook_name": job.catalog_item.name,
            "requester_id": job.requester_id,
            "approver_id": job.approver_id,
            "target_resource_id": job.target_resource_id,
            "status": job.status.value,
            "risk_tier": job.catalog_item.risk_tier.value,
            "servicenow_chg": job.servicenow_chg,
            "parameters": job.parameters,
            "exit_code": job.exit_code,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
        }
        for job in container.jobs.values()
    ]


@router.post("/jobs")
def create_job(req: CreateJobRequest):
    """
    Submits an automation job.
    Applies deterministic parameter regex, bounds, and secret scanning upon entry.
    """
    catalog_item = next((i for i in container.catalog if i.identifier == req.catalog_identifier), None)
    if not catalog_item:
        raise HTTPException(status_code=404, detail=f"Catalog item '{req.catalog_identifier}' not found.")

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    correlation_id = f"EXEC-{uuid.uuid4().hex[:6].upper()}"

    try:
        job = ExecutionJob(
            job_id=job_id,
            correlation_id=correlation_id,
            catalog_item=catalog_item,
            requester_id=req.requester_id,
            target_resource_id=req.target_resource_id,
            parameters=req.parameters,
            servicenow_chg=req.servicenow_chg,
            storage_artifact_uri=req.storage_artifact_uri,
            storage_artifact_sha256=req.storage_artifact_sha256
        )
    except SecretLintError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ParameterValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Governance Routing: Maker-Checker vs Direct Queue
    if catalog_item.risk_tier == RiskTier.LOW and not catalog_item.requires_maker_checker:
        job.parse()
        job.transition_to(JobStatus.QUEUED, "Low-risk automation bypasses Maker-Checker gate.")
    else:
        job.request_approval(datetime.now(timezone.utc))

    container.jobs[correlation_id] = job

    return {
        "job_id": job.id,
        "correlation_id": job.correlation_id,
        "status": job.status.value,
        "target_resource_id": job.target_resource_id,
        "requires_approval": job.status == JobStatus.PENDING_APPROVAL
    }


@router.get("/jobs/{correlation_id}")
def get_job(correlation_id: str):
    """Fetch job state and execution progress."""
    job = container.jobs.get(correlation_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "id": job.id,
        "correlation_id": job.correlation_id,
        "playbook_identifier": job.catalog_item.identifier,
        "playbook_name": job.catalog_item.name,
        "requester_id": job.requester_id,
        "approver_id": job.approver_id,
        "target_resource_id": job.target_resource_id,
        "status": job.status.value,
        "risk_tier": job.catalog_item.risk_tier.value,
        "servicenow_chg": job.servicenow_chg,
        "parameters": job.parameters,
        "exit_code": job.exit_code,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    }


@router.post("/jobs/{correlation_id}/approve")
def approve_job(correlation_id: str, req: ApproveJobRequest):
    """
    Maker-Checker Sign-off Gate:
    Enforces Maker != Checker inequality and 15-minute fail-closed timeout.
    """
    job = container.jobs.get(correlation_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    from app.domain.entities import ApprovalDecision

    decision = ApprovalDecision(
        decision=req.decision.upper(),
        approver_id=req.approver_id,
        decided_at=datetime.now(timezone.utc),
        reason=req.reason,
        chg_number=req.chg_number or job.servicenow_chg
    )

    try:
        job.apply_approval_decision(decision, datetime.now(timezone.utc), timeout_seconds=900)
    except MakerCheckerViolationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ApprovalTimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "correlation_id": job.correlation_id,
        "status": job.status.value,
        "approver_id": job.approver_id,
        "decision": decision.decision
    }


@router.post("/jobs/{correlation_id}/execute")
def trigger_execution(correlation_id: str):
    """
    Triggers BaseJobRunner Template Method in background thread with live WebSocket streaming.
    """
    job = container.jobs.get(correlation_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status not in (JobStatus.QUEUED, JobStatus.PARSED):
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot execute in status [{job.status.value}]. Must be QUEUED or PARSED."
        )

    runner = container.create_runner(log_event_stream=ws_hub.emit_log)

    def run_worker():
        try:
            runner.run(job)
        except Exception as e:
            ws_hub.emit_log(correlation_id, f"\033[1;31m[EXECUTION ERROR]\033[0m {str(e)}", "stderr")

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    return {"status": "EXECUTION_DISPATCHED", "correlation_id": correlation_id}


@router.post("/jobs/{correlation_id}/diagnose")
def diagnose_job_failure(correlation_id: str):
    """
    AI SRE Failure Diagnostic Subsystem:
    Extracts 50-line log window and provides root-cause analysis in <3.0s.
    """
    job = container.jobs.get(correlation_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # Retrieve stdout from ring buffer
    buffer_lines = ws_hub.buffers.get(correlation_id, [])
    full_stdout = "\n".join(item["data"] for item in buffer_lines)
    if not full_stdout and job.error_message:
        full_stdout = job.error_message

    diag = container.diagnostic_engine.diagnose(full_stdout, job.catalog_item.identifier)
    return diag.to_dict()


# =====================================================================
# S3 10GB MULTIPART UPLOAD ROUTES
# =====================================================================

@router.post("/storage/multipart/initiate")
def initiate_multipart(req: MultipartInitiateRequest):
    """Generates 50MB chunk presigned PUT URLs for direct S3 upload."""
    return container.storage_gateway.initiate_multipart_upload(
        file_name=req.file_name,
        file_size_bytes=req.file_size_bytes,
        sha256_checksum=req.sha256_checksum,
        job_id=req.job_id
    )


@router.post("/storage/multipart/complete")
def complete_multipart(req: MultipartCompleteRequest):
    """Assembles multipart parts into finished S3 object pointer."""
    uri = container.storage_gateway.complete_multipart_upload(
        upload_id=req.upload_id,
        s3_key=req.s3_key,
        parts=req.parts
    )
    return {"status": "SUCCESS", "artifact_uri": uri}


# =====================================================================
# WEBSOCKET REAL-TIME STREAMING ENDPOINT
# =====================================================================

@router.websocket("/ws/jobs/{correlation_id}")
async def job_websocket_endpoint(websocket: WebSocket, correlation_id: str, last_seq: int = Query(0)):
    """
    Real-time log streaming backplane for xterm.js terminal.
    Replays missed logs for late joiners and streams subsequent live lines.
    """
    await ws_hub.register(websocket, correlation_id, last_seq=last_seq)
    try:
        while True:
            # Keepalive listener
            data = await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        ws_hub.unregister(websocket, correlation_id)
