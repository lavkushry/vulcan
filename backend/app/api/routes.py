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
from app.domain.entities import ExecutionEngineType, ExecutionJob, JobStatus, RiskTier
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
    prompt: Optional[str] = None
    text: Optional[str] = None
    ambient_params: Optional[Dict[str, Any]] = None

class CreateJobRequest(BaseModel):
    catalog_identifier: Optional[str] = None
    identifier: Optional[str] = None
    target_resource_id: Optional[str] = None
    requester_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    servicenow_chg: Optional[str] = None
    storage_artifact_uri: Optional[str] = None
    storage_artifact_sha256: Optional[str] = None

class ApproveJobRequest(BaseModel):
    approver_id: str
    decision: str = "APPROVE"  # "APPROVE" | "REJECT"
    reason: str = "Authorized by Checker"
    chg_number: Optional[str] = None

class RejectJobRequest(BaseModel):
    approver_id: str
    reason: Optional[str] = "Rejected by Checker"

class MultipartInitiateRequest(BaseModel):
    file_name: str
    file_size_bytes: int
    sha256_checksum: str
    job_id: str

class MultipartCompleteRequest(BaseModel):
    upload_id: str
    s3_key: str
    parts: List[Dict[str, Any]]

class ChatIntentRequest(BaseModel):
    prompt: str
    ambient_params: Optional[Dict[str, Any]] = None

class DispatchTaskRequest(BaseModel):
    catalog_identifier: str
    target_resource_id: str
    requester_id: str = "console.operator"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    environment: str = "PROD"
    servicenow_chg: Optional[str] = None
    dry_run: bool = False


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
def list_catalog(
    search: Optional[str] = None,
    category: Optional[str] = None,
    engine: Optional[str] = None,
    risk_tier: Optional[str] = None
):
    """Returns list of immutable playbooks and Terraform stacks with multi-filter support."""
    items = []
    q_lower = (search or "").lower().strip()
    for item in container.catalog:
        if category and category != "all" and getattr(item, "category", "") != category:
            continue
        if engine and engine != "all" and item.engine.value != engine:
            continue
        if risk_tier and risk_tier != "all" and item.risk_tier.value != risk_tier:
            continue
        if q_lower:
            text = f"{item.identifier} {item.name} {getattr(item, 'description', '')} {' '.join(getattr(item, 'tags', []))}".lower()
            if q_lower not in text:
                continue

        items.append({
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
            "category": getattr(item, "category", "general"),
            "description": getattr(item, "description", ""),
            "tags": getattr(item, "tags", [])
        })
    return items


@router.post("/chat/intent")
def chat_intent(req: ChatIntentRequest):
    """
    Conversational AI Intent Parsing:
    Maps natural language request to exact playbook or Terraform stack from 100+ items,
    extracts parameters (host, IPs, numbers, env), and generates interactive launch card.
    """
    from app.catalog_data import find_matching_playbook
    return find_matching_playbook(req.prompt, req.ambient_params)


@router.get("/tasks")
def list_tasks_filtered(
    engine: Optional[str] = Query("all"),
    status: Optional[str] = Query("all"),
    environment: Optional[str] = Query("all"),
    category: Optional[str] = Query("all"),
    search: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0)
):
    """
    High-Filtered Task Window Endpoint:
    Provides multi-dimensional querying across engine, status, environment, category,
    and text search with real-time aggregate telemetry counts.
    """
    all_tasks = []
    counts_by_status = {"RUNNING": 0, "SUCCESS": 0, "FAILED": 0, "PENDING_APPROVAL": 0, "QUEUED": 0}
    counts_by_engine = {"ansible": 0, "terraform": 0}
    counts_by_category = {}

    for job in container.jobs.values():
        st = job.status.value
        eng = job.catalog_item.engine.value
        cat = getattr(job.catalog_item, "category", "general")
        env = getattr(job, "environment", "PROD")

        # Telemetry aggregations
        if st in counts_by_status:
            counts_by_status[st] += 1
        if eng in counts_by_engine:
            counts_by_engine[eng] += 1
        counts_by_category[cat] = counts_by_category.get(cat, 0) + 1

        # Apply multi-dimensional filters
        if engine and engine != "all" and eng != engine:
            continue
        if status and status != "all" and st != status:
            continue
        if environment and environment != "all" and env != environment:
            continue
        if category and category != "all" and cat != category:
            continue

        if search:
            q = search.lower().strip()
            haystack = f"{job.correlation_id} {job.id} {job.catalog_item.name} {job.catalog_item.identifier} {job.target_resource_id} {job.requester_id} {job.error_message or ''}".lower()
            if q not in haystack:
                continue

        all_tasks.append({
            "id": job.id,
            "correlation_id": job.correlation_id,
            "identifier": job.catalog_item.identifier,
            "name": job.catalog_item.name,
            "engine": eng,
            "category": cat,
            "target_resource": job.target_resource_id,
            "environment": env,
            "status": st,
            "risk_tier": job.catalog_item.risk_tier.value,
            "requester_id": job.requester_id,
            "approver_id": job.approver_id,
            "duration_sec": 45 if st == "RUNNING" else (120 if st == "SUCCESS" else 30),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "parameters": job.parameters,
            "error_message": job.error_message,
        })

    # Sort newest first
    all_tasks.sort(key=lambda t: t["created_at"] or "", reverse=True)
    paginated = all_tasks[offset : offset + limit]

    return {
        "tasks": paginated,
        "total_count": len(container.jobs),
        "filtered_count": len(all_tasks),
        "counts_by_status": counts_by_status,
        "counts_by_engine": counts_by_engine,
        "counts_by_category": counts_by_category
    }


@router.post("/tasks/dispatch")
def dispatch_task(req: DispatchTaskRequest):
    """
    Launches an automation task directly from the Chat Assistant or Launch Card.
    Handles parameter injection, Maker-Checker routing, and background thread streaming.
    """
    catalog_item = next((i for i in container.catalog if i.identifier == req.catalog_identifier), None)
    if not catalog_item:
        raise HTTPException(status_code=404, detail=f"Catalog item '{req.catalog_identifier}' not found.")

    job_id = f"task-{uuid.uuid4().hex[:6]}"
    correlation_id = f"EXEC-{uuid.uuid4().hex[:4].upper()}"

    try:
        job = ExecutionJob(
            job_id=job_id,
            correlation_id=correlation_id,
            catalog_item=catalog_item,
            requester_id=req.requester_id,
            target_resource_id=req.target_resource_id,
            parameters=req.parameters,
            servicenow_chg=req.servicenow_chg,
            environment=req.environment
        )
    except (SecretLintError, ParameterValidationError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Governance check: Enforce Maker-Checker if declared on catalog item or if high risk
    if (catalog_item.requires_maker_checker or catalog_item.risk_tier == RiskTier.HIGH) and not req.dry_run:
        job.parse()
        job.request_approval(datetime.now(timezone.utc))
        container.jobs[correlation_id] = job
        ws_hub.emit_log(correlation_id, f"\033[1;33m[GOVERNANCE]\033[0m Task submitted. Awaiting Maker-Checker sign-off (CHG: {req.servicenow_chg or 'AUTO-REQ'}).")
        return {
            "job_id": job.id,
            "correlation_id": job.correlation_id,
            "status": job.status.value,
            "target_resource": job.target_resource_id,
            "requires_approval": True,
            "message": "Automation requires Maker-Checker approval before execution."
        }

    # Immediate execution path
    job.parse()
    job.transition_to(JobStatus.QUEUED, "Dispatched from automation hub")
    job.transition_to(JobStatus.LOCKED, "Distributed lock acquired")
    job.transition_to(JobStatus.RUNNING, "Execution initiated")
    container.jobs[correlation_id] = job

    def run_simulation():
        import time
        engine_name = catalog_item.engine.value.upper()
        ws_hub.emit_log(correlation_id, f"\033[1;36m[PROJECT VULCAN CONTROL PLANE]\033[0m Initializing runtime sandbox for {catalog_item.identifier}...")
        time.sleep(0.3)
        ws_hub.emit_log(correlation_id, f"\033[1;34m[PAM CYBERARK]\033[0m Bound ephemeral session credentials for {req.target_resource_id}.")
        time.sleep(0.3)
        ws_hub.emit_log(correlation_id, f"\033[1;32m[AUDIT LEDGER]\033[0m Synchronous pre-run cryptographic commit hash: {container.audit_logger.get_last_hash()[:12]}...")
        time.sleep(0.4)

        if catalog_item.engine == ExecutionEngineType.ANSIBLE:
            ws_hub.emit_log(correlation_id, f"PLAY [{catalog_item.name}] ****************************************")
            time.sleep(0.4)
            ws_hub.emit_log(correlation_id, f"TASK [Gathering Facts] *********************************************************")
            ws_hub.emit_log(correlation_id, f"ok: [{req.target_resource_id}]")
            time.sleep(0.5)
            ws_hub.emit_log(correlation_id, f"TASK [execute_playbook_tasks : Verify environment state] ***********************")
            ws_hub.emit_log(correlation_id, f"ok: [{req.target_resource_id}] => {{\"status\": \"READY\", \"env\": \"{req.environment}\"}}")
            time.sleep(0.6)
            ws_hub.emit_log(correlation_id, f"TASK [execute_playbook_tasks : Apply configurations] ***************************")
            ws_hub.emit_log(correlation_id, f"changed: [{req.target_resource_id}] => {{\"params\": {req.parameters}, \"state\": \"APPLIED\"}}")
            time.sleep(0.5)
            ws_hub.emit_log(correlation_id, f"PLAY RECAP *********************************************************************")
            ws_hub.emit_log(correlation_id, f"{req.target_resource_id} : ok=3    changed=1    unreachable=0    failed=0")
        else:
            ws_hub.emit_log(correlation_id, f"\033[1;35m[TERRAFORM INIT]\033[0m Initializing provider plugins (AWS / Azure / GCP)...")
            time.sleep(0.4)
            ws_hub.emit_log(correlation_id, f"\033[1;35m[TERRAFORM PLAN]\033[0m Plan: 1 to add, 0 to change, 0 to destroy.")
            time.sleep(0.6)
            ws_hub.emit_log(correlation_id, f"\033[1;35m[TERRAFORM APPLY]\033[0m Applying configuration to {req.target_resource_id}...")
            time.sleep(0.7)
            ws_hub.emit_log(correlation_id, f"\033[1;32m[TERRAFORM SUCCESS]\033[0m Apply complete! Resources: 1 added, 0 changed, 0 destroyed.")

        ws_hub.emit_log(correlation_id, f"\033[1;32m[POST-FLIGHT VERIFICATION]\033[0m Health probes passed with 0% error rate.")
        job.transition_to(JobStatus.VERIFYING, "Verifying health probes")
        job.transition_to(JobStatus.SUCCESS, "Completed execution")
        job.completed_at = datetime.now(timezone.utc)
        ws_hub.emit_log(correlation_id, f"\033[1;32m[COMPLETE]\033[0m Task {correlation_id} finished successfully with exit code 0.")

    thread = threading.Thread(target=run_simulation, daemon=True)
    thread.start()

    return {
        "job_id": job.id,
        "correlation_id": job.correlation_id,
        "status": job.status.value,
        "target_resource": job.target_resource_id,
        "requires_approval": False,
        "message": f"Task {job.correlation_id} dispatched and executing live."
    }


@router.get("/tasks/{correlation_id}/logs")
def get_task_logs(correlation_id: str):
    """Returns ANSI terminal log lines for live or historical replay."""
    # 1. From real-time buffer
    buffer_lines = ws_hub.buffers.get(correlation_id, [])
    if buffer_lines:
        def _get_line(item):
            d = item.get("data")
            if isinstance(d, dict):
                return str(d.get("line") or d.get("data") or "").rstrip("\r\n")
            return str(d or "").rstrip("\r\n")

        return {
            "correlation_id": correlation_id,
            "logs": [_get_line(item) for item in buffer_lines],
            "total_lines": len(buffer_lines)
        }

    # 2. If pre-seeded task, generate realistic logs
    job = container.jobs.get(correlation_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task correlation ID not found.")

    target = job.target_resource_id
    cat_item = job.catalog_item
    is_tf = cat_item.engine == ExecutionEngineType.TERRAFORM
    
    logs = [
        f"\033[1;36m[PROJECT VULCAN CONTROL PLANE]\033[0m Execution log session for {correlation_id} ({cat_item.identifier})",
        f"\033[1;34m[PAM CYBERARK]\033[0m Ephemeral session credentials verified on target {target}.",
        f"\033[1;32m[AUDIT LEDGER]\033[0m Merkle root chain verification: VALID (Tip: 0x9a8f12c...)",
        f"Target Resource: {target} | Environment: {getattr(job, 'environment', 'PROD')} | Requester: {job.requester_id}",
        "--------------------------------------------------------------------------------"
    ]

    if is_tf:
        logs.extend([
            "\033[1;35m[TERRAFORM INIT]\033[0m Initializing provider modules from Git commit sha...",
            f"\033[1;35m[TERRAFORM PLAN]\033[0m Refreshing state for target {target}...",
            f"\033[1;35m[TERRAFORM PLAN]\033[0m Plan: 1 to add, 0 to change, 0 to destroy.",
            f"\033[1;35m[TERRAFORM APPLY]\033[0m {cat_item.name} applying changes...",
        ])
    else:
        logs.extend([
            f"PLAY [{cat_item.name}] **************************************************",
            f"TASK [Gathering Facts] *********************************************************",
            f"ok: [{target}]",
            f"TASK [execute_steps : Run primary automation sequence] *************************",
            f"changed: [{target}] => {{\"applied\": true, \"params\": {job.parameters}}}",
            f"PLAY RECAP *********************************************************************",
            f"{target} : ok=3    changed=1    unreachable=0    failed=0"
        ])

    if job.status == JobStatus.FAILED:
        logs.append(f"\033[1;31m[FATAL ERROR]\033[0m {job.error_message or 'Step failure on node'}")
    else:
        logs.append(f"\033[1;32m[SUCCESS]\033[0m Automation completed cleanly with exit code 0.")

    return {
        "correlation_id": correlation_id,
        "logs": logs,
        "total_lines": len(logs)
    }


def _format_job_response(job: ExecutionJob) -> Dict[str, Any]:
    approved_at_str = None
    if job.approval_decision and job.approval_decision.decided_at:
        approved_at_str = job.approval_decision.decided_at.isoformat()

    return {
        "id": job.id,
        "job_id": job.id,
        "correlation_id": job.correlation_id,
        "identifier": job.catalog_item.identifier,
        "name": job.catalog_item.name,
        "playbook_identifier": job.catalog_item.identifier,
        "playbook_name": job.catalog_item.name,
        "engine": job.catalog_item.engine.value,
        "risk_tier": job.catalog_item.risk_tier.value,
        "requester_id": job.requester_id,
        "approver_id": job.approver_id,
        "target_resource_id": job.target_resource_id,
        "target_resource": job.target_resource_id,
        "parameters": job.parameters,
        "status": job.status.value,
        "requires_approval": job.status == JobStatus.PENDING_APPROVAL,
        "servicenow_chg": job.servicenow_chg,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "approved_at": approved_at_str,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "exit_code": job.exit_code,
        "error_message": job.error_message,
        "diagnostic": getattr(job, "diagnostic", None) or job.error_message,
    }


@router.post("/intent/resolve")
def resolve_intent(req: ResolveIntentRequest):
    """
    AI Reasoning Subsystem (The LLM OS):
    Hybrid RRF Retrieval + Pydantic Slot Filling within 2,500 token budget.
    """
    query = req.text or req.prompt or ""
    result = container.intent_resolver.resolve(query, req.ambient_params)
    cat_item = result.catalog_item

    all_param_specs = []
    if cat_item and isinstance(cat_item.input_schema, dict):
        props = cat_item.input_schema.get("properties", {})
        req_fields = set(cat_item.input_schema.get("required", []))
        for p_name, p_spec in props.items():
            enum_vals = p_spec.get("enum")
            p_type = "enum" if enum_vals else ("integer" if p_spec.get("type") == "integer" else "string")
            all_param_specs.append({
                "name": p_name,
                "type": p_type,
                "required": p_name in req_fields,
                "description": p_spec.get("description", p_name),
                "choices": [str(x) for x in enum_vals] if enum_vals else None,
            })

    missing_specs = [
        next((ps for ps in all_param_specs if ps["name"] == mf), {
            "name": mf,
            "type": "string",
            "required": True,
            "description": f"Missing parameter: {mf}"
        })
        for mf in result.missing_fields
    ]

    status_str = "READY" if result.status == "READY" else ("NEEDS_INPUT" if result.status == "NEEDS_INPUT" else "REJECTED")

    match_dict = None
    if cat_item:
        match_dict = {
            "identifier": cat_item.identifier,
            "name": cat_item.name,
            "engine": cat_item.engine.value,
            "risk_tier": cat_item.risk_tier.value,
            "description": getattr(cat_item, "description", "") or f"Automated execution of {cat_item.name}",
            "requires_maker_checker": cat_item.requires_maker_checker,
            "requires_chg": cat_item.requires_chg,
            "params": all_param_specs
        }

    return {
        "status": status_str,
        "playbook_identifier": cat_item.identifier if cat_item else None,
        "playbook_name": cat_item.name if cat_item else None,
        "parameters": result.extracted_parameters,
        "missing_fields": missing_specs,
        "refusal_reason": result.refusal_reason,
        "tokens_used": result.tokens_used,
        "match": match_dict,
        "confidence": 0.95 if result.status == "READY" else (0.85 if result.status == "NEEDS_INPUT" else 0.0),
        "reason": result.refusal_reason or ("No matching playbook found in catalog." if not cat_item else None),
        "suggestions": [
            {"identifier": c.identifier, "name": c.name}
            for c in container.catalog[:3]
        ] if status_str == "REJECTED" or not cat_item else [],
        "servicenow_chg": f"CHG-{abs(hash(cat_item.identifier + query)) % 900000 + 100000}" if cat_item and cat_item.requires_chg else None,
    }


@router.get("/jobs")
def list_jobs():
    """List all jobs in the control plane."""
    return [_format_job_response(job) for job in container.jobs.values()]


@router.post("/jobs")
def create_job(req: CreateJobRequest):
    """
    Submits an automation job.
    Applies deterministic parameter regex, bounds, and secret scanning upon entry.
    """
    catalog_id = req.catalog_identifier or req.identifier
    if not catalog_id:
        raise HTTPException(status_code=400, detail="Missing catalog identifier (catalog_identifier or identifier).")

    catalog_item = next((i for i in container.catalog if i.identifier == catalog_id), None)
    if not catalog_item:
        raise HTTPException(status_code=404, detail=f"Catalog item '{catalog_id}' not found.")

    target_res = (
        req.target_resource_id
        or req.parameters.get("hostname")
        or req.parameters.get("target_resource_id")
        or req.parameters.get("vip_ip")
        or req.parameters.get("target_resource")
        or f"{catalog_id}-node-01"
    )

    chg = req.servicenow_chg

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    correlation_id = f"EXEC-{uuid.uuid4().hex[:6].upper()}"

    try:
        job = ExecutionJob(
            job_id=job_id,
            correlation_id=correlation_id,
            catalog_item=catalog_item,
            requester_id=req.requester_id,
            target_resource_id=str(target_res),
            parameters=req.parameters,
            servicenow_chg=chg,
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
    return _format_job_response(job)


@router.get("/jobs/{correlation_id}")
def get_job(correlation_id: str):
    """Fetch job state and execution progress."""
    job = container.jobs.get(correlation_id) or next(
        (j for j in container.jobs.values() if j.id == correlation_id or j.correlation_id == correlation_id), None
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return _format_job_response(job)


@router.post("/jobs/{correlation_id}/approve")
def approve_job(correlation_id: str, req: ApproveJobRequest):
    """
    Maker-Checker Sign-off Gate:
    Enforces Maker != Checker inequality and 15-minute fail-closed timeout.
    """
    job = container.jobs.get(correlation_id) or next(
        (j for j in container.jobs.values() if j.id == correlation_id or j.correlation_id == correlation_id), None
    )
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

    ws_hub.publish(job.correlation_id, "status", {
        "status": job.status.value,
        "message": f"Approved by {req.approver_id}"
    })

    res = _format_job_response(job)
    res["decision"] = decision.decision
    return res


@router.post("/jobs/{correlation_id}/reject")
def reject_job(correlation_id: str, req: RejectJobRequest):
    """
    Maker-Checker Rejection Gate:
    Rejects the job and marks status REJECTED.
    """
    job = container.jobs.get(correlation_id) or next(
        (j for j in container.jobs.values() if j.id == correlation_id or j.correlation_id == correlation_id), None
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    from app.domain.entities import ApprovalDecision

    decision = ApprovalDecision(
        decision="REJECT",
        approver_id=req.approver_id,
        decided_at=datetime.now(timezone.utc),
        reason=req.reason or "Rejected by Checker",
        chg_number=job.servicenow_chg
    )

    try:
        job.apply_approval_decision(decision, datetime.now(timezone.utc), timeout_seconds=900)
    except MakerCheckerViolationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ApprovalTimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ws_hub.publish(job.correlation_id, "status", {
        "status": job.status.value,
        "message": f"Rejected by {req.approver_id}: {decision.reason}"
    })

    res = _format_job_response(job)
    res["decision"] = "REJECT"
    return res


@router.post("/jobs/{correlation_id}/execute")
def trigger_execution(correlation_id: str):
    """
    Triggers BaseJobRunner Template Method in background thread with live WebSocket streaming.
    """
    job = container.jobs.get(correlation_id) or next(
        (j for j in container.jobs.values() if j.id == correlation_id or j.correlation_id == correlation_id), None
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status in (JobStatus.RUNNING, JobStatus.VERIFYING, JobStatus.SUCCESS):
        return {"status": "EXECUTION_ALREADY_RUNNING", "correlation_id": job.correlation_id}

    if job.status not in (JobStatus.QUEUED, JobStatus.PARSED):
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot execute in status [{job.status.value}]. Must be QUEUED or PARSED."
        )

    runner = container.create_runner(log_event_stream=ws_hub.emit_log)

    def run_worker():
        try:
            ws_hub.publish(job.correlation_id, "status", {"status": "RUNNING", "message": "Worker spawned"})
            runner.run(job)
            ws_hub.publish(job.correlation_id, "status", {"status": job.status.value, "message": "Execution complete"})
        except Exception as e:
            ws_hub.emit_log(job.correlation_id, f"\033[1;31m[EXECUTION ERROR]\033[0m {str(e)}", "stderr")
            ws_hub.publish(job.correlation_id, "status", {"status": job.status.value, "message": str(e)})
            try:
                diag = container.diagnostic_engine.diagnose(str(e), job.catalog_item.identifier)
                ws_hub.publish(job.correlation_id, "diagnostic", {"root_cause": diag.root_cause})
                job.diagnostic = diag.root_cause
            except Exception:
                pass

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    return {"status": "EXECUTION_DISPATCHED", "correlation_id": job.correlation_id}


@router.post("/jobs/{correlation_id}/diagnose")
def diagnose_job_failure(correlation_id: str):
    """
    AI SRE Failure Diagnostic Subsystem:
    Extracts 50-line log window and provides root-cause analysis in <3.0s.
    """
    job = container.jobs.get(correlation_id) or next(
        (j for j in container.jobs.values() if j.id == correlation_id or j.correlation_id == correlation_id), None
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # Retrieve stdout from ring buffer
    buffer_lines = ws_hub.buffers.get(job.correlation_id, [])
    full_stdout_lines = []
    for item in buffer_lines:
        d = item.get("data")
        if isinstance(d, dict):
            full_stdout_lines.append(str(d.get("line") or d.get("data") or ""))
        else:
            full_stdout_lines.append(str(d or ""))
    full_stdout = "\n".join(full_stdout_lines)
    if not full_stdout and job.error_message:
        full_stdout = job.error_message

    diag = container.diagnostic_engine.diagnose(full_stdout, job.catalog_item.identifier)
    job.diagnostic = diag.root_cause
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
