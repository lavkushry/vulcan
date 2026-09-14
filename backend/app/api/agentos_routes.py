"""
Project Vulcan: AgentOS Ultra REST Endpoints (Section 46 & AGENT-13)
Author: Architectural Review Board & AgentOS Core Team

APIs for:
- Workflows lifecycle management (create, step, auto-run, input, resume, approve, rollback)
- Immutable event and audit log retrieval
- Specialist agent versions, release stages, and telemetry inspection
- Multi-tier evaluations and benchmark trigger
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.agentos.context import OptimisticLockError, StateTransitionError, WorkflowState
from app.agentos.eval_platform import AgentOSEvalPlatform

logger = logging.getLogger("vulcan.agentos_routes")
router = APIRouter(prefix="/agentos", tags=["AgentOS Ultra"])


class CreateWorkflowRequest(BaseModel):
    original_request: str = Field(..., min_length=3, description="Natural language infrastructure requirement")
    environment: str = Field(default="PROD", description="Target environment: PROD, STAGE, or DEV")
    auto_prepare: bool = Field(default=False, description="Automatically advance preparation through discovery, planning, composition, build, validation, and security")


class SupplyInputRequest(BaseModel):
    operator_input: Dict[str, Any] = Field(..., description="Key-value parameters resolving missing questions")


class ApproveWorkflowRequest(BaseModel):
    reason: str = Field(default="Approved for production execution", description="Business justification")


class RunEvalRequest(BaseModel):
    tier: int = Field(default=0, ge=0, le=7, description="Evaluation Tier (0 to 7)")


def _get_kernel(request: Request):
    container = getattr(request.app.state, "container", None)
    if container and hasattr(container, "agentos_kernel"):
        return container.agentos_kernel
    from app.config import container as default_container
    return default_container.agentos_kernel


from app.adapters.policy_manager import policy_manager
from app.domain.roles_and_policies import Permission

def _enforce_permission(request: Request, permission: Permission):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required: no user_id in request state.")
    if not policy_manager.check_user_permission(user_id, permission):
        raise HTTPException(
            status_code=403, 
            detail=f"RBAC Policy Violation: User [{user_id}] lacks required permission [{permission.value}]."
        )


def generate_plan_summary(ctx) -> Dict[str, Any]:
    intent = ctx.normalized_intent or {}
    params = intent.get("known_parameters", {})
    software = params.get("software") or intent.get("desired_outcome") or "service"
    target = params.get("target_host") or params.get("target_resource_id") or params.get("hostname")
    port = params.get("port")
    mem = params.get("maxmemory_mb")
    
    plan = ctx.automation_plan or {}
    selected = plan.get("selected_assets", [])
    asset_name = selected[0] if selected else "Ansible Playbook"

    # Human-readable synopsis
    parts = [f"The plan configures {str(software).title()}"]
    if mem:
        parts.append(f"with a {mem} MB memory limit" if mem < 1024 else f"with a {round(mem/1024, 1)} GB memory limit")
    if port:
        parts.append(f"on port {port}")
    if target:
        parts.append(f"on `{target}`.")
    else:
        parts.append("(target server pending).")
    synopsis = " ".join(parts)

    next_action = "Review and deploy"
    if ctx.current_state == WorkflowState.WAITING_FOR_INPUT:
        missing = ctx.unresolved_questions or ["target host"]
        next_action = f"Which development server should I use? (Required: {', '.join(missing)})"
    elif ctx.current_state == WorkflowState.WAITING_FOR_RESOURCE:
        missing_res = [r.get("provider") for r in ctx.required_resources if not r.get("is_available")]
        next_action = f"Connect your execution environment to continue. [Add connection: {', '.join(missing_res)}]"
    elif ctx.current_state in (WorkflowState.WAITING_FOR_APPROVAL, WorkflowState.EXECUTION_READY):
        next_action = "Review and deploy"
    elif ctx.current_state == WorkflowState.SUCCESS:
        next_action = "Completed and verified"
    elif ctx.current_state == WorkflowState.EXECUTION_FAILED:
        next_action = "Execution failed — Rollback available"
    elif ctx.current_state == WorkflowState.VERIFY_FAILED:
        next_action = "Verification failed — Rollback available"

    # Probes info
    probes_summary = []
    if ctx.postcondition_verification and "probes" in ctx.postcondition_verification:
        probes_summary = ctx.postcondition_verification.get("probes", [])
    elif port:
        probes_summary = [
            {"probe_type": "port_open", "target": target or "server", "expected": f"Port {port} open"},
            {"probe_type": "service_status", "target": target or "server", "expected": f"{software} active"},
        ]

    # Execution outcome summary
    execution_summary = None
    if ctx.execution_result:
        exec_res = ctx.execution_result
        stdout = exec_res.get("stdout", "")
        execution_summary = {
            "exit_code": exec_res.get("exit_code", 0),
            "what_ran": f"Playbook for {asset_name}",
            "what_changed": "Host configuration applied successfully" if ("changed: [" in stdout or "changed=" in stdout) else "No changes needed",
            "verification_established": "All dynamic probes passed" if (ctx.postcondition_verification or {}).get("all_passed") else "Verification pending or failed",
            "stdout": stdout,
        }

    return {
        "synopsis": synopsis,
        "software": software,
        "target_host": target,
        "parameters": params,
        "asset": asset_name,
        "environment": ctx.environment,
        "risk_tier": ctx.risk_classification.get("risk_tier", "TIER_2") if ctx.risk_classification else "TIER_2",
        "next_action": next_action,
        "probes": probes_summary,
        "execution_summary": execution_summary,
    }


def _workflow_response(ctx) -> Dict[str, Any]:
    out = ctx.to_dict()
    out["plan_summary"] = generate_plan_summary(ctx)
    return out


@router.post("/workflows")
def create_workflow(req: CreateWorkflowRequest, request: Request):
    """Creates and persists a new canonical WorkflowContext, advancing through preparation if auto_prepare=True."""
    _enforce_permission(request, Permission.WORKFLOW_CREATE)
    requester_id = getattr(request.state, "user_id", None)
    
    kernel = _get_kernel(request)
    corr_id = getattr(request.state, "correlation_id", None)
    try:
        ctx = kernel.create_workflow(
            original_request=req.original_request,
            requester_id=requester_id,
            environment=req.environment,
            correlation_id=corr_id,
        )

        if req.auto_prepare:
            # Advance automatically until paused (WAITING_FOR_INPUT, WAITING_FOR_RESOURCE, WAITING_FOR_APPROVAL, EXECUTION_READY) or terminal
            max_steps = 15
            for _ in range(max_steps):
                prev_state = ctx.current_state
                ctx = kernel.step(ctx.workflow_id)
                if ctx.current_state in (
                    WorkflowState.WAITING_FOR_INPUT,
                    WorkflowState.WAITING_FOR_RESOURCE,
                    WorkflowState.WAITING_FOR_APPROVAL,
                    WorkflowState.EXECUTION_READY,
                    WorkflowState.SUCCESS,
                    WorkflowState.EXECUTION_FAILED,
                    WorkflowState.VERIFY_FAILED,
                    WorkflowState.POLICY_DENIED,
                    WorkflowState.ROLLED_BACK,
                ) or ctx.current_state == prev_state:
                    break

        return _workflow_response(ctx)
    except Exception as e:
        logger.error("Error creating workflow: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows")
def list_workflows(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    state: Optional[str] = Query(default=None),
):
    """Lists AgentOS workflows with pagination and state filtering."""
    _enforce_permission(request, Permission.WORKFLOW_READ_ALL)
    kernel = _get_kernel(request)
    workflows = kernel.repository.list_workflows(limit=limit, offset=offset, state=state)
    return [w.to_dict() for w in workflows]


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, request: Request):
    """Retrieves full WorkflowContext by workflow_id with plan summary."""
    _enforce_permission(request, Permission.WORKFLOW_READ_ALL)
    kernel = _get_kernel(request)
    ctx = kernel.repository.get_workflow(workflow_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return _workflow_response(ctx)


@router.post("/workflows/{workflow_id}/step")
def step_workflow(workflow_id: str, request: Request):
    """Advances workflow execution by one specialist agent step."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    kernel = _get_kernel(request)
    try:
        ctx = kernel.step(workflow_id)
        return _workflow_response(ctx)
    except StateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OptimisticLockError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Step execution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/auto-run")
def auto_run_workflow(workflow_id: str, request: Request, max_steps: int = Query(default=15, ge=1, le=50)):
    """Automatically advances workflow until it pauses (WAITING_*) or completes."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    kernel = _get_kernel(request)
    ctx = kernel.repository.get_workflow(workflow_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

    steps_taken = 0
    while steps_taken < max_steps:
        prev_state = ctx.current_state
        ctx = kernel.step(workflow_id)
        steps_taken += 1

        # Pause or terminal condition
        if ctx.current_state in (
            WorkflowState.WAITING_FOR_INPUT,
            WorkflowState.WAITING_FOR_RESOURCE,
            WorkflowState.WAITING_FOR_APPROVAL,
            WorkflowState.EXECUTION_READY,
            WorkflowState.SUCCESS,
            WorkflowState.EVALUATING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
            WorkflowState.POLICY_DENIED,
            WorkflowState.ROLLED_BACK,
            WorkflowState.EXECUTION_FAILED,
            WorkflowState.VERIFY_FAILED,
        ) or ctx.current_state == prev_state:
            break

    return {
        "workflow": _workflow_response(ctx),
        "steps_taken": steps_taken,
        "is_paused": ctx.current_state.value.startswith("WAITING_"),
        "is_terminal": ctx.current_state in (
            WorkflowState.SUCCESS,
            WorkflowState.EVALUATING,
            WorkflowState.ROLLED_BACK,
            WorkflowState.POLICY_DENIED,
        ),
    }


@router.post("/workflows/{workflow_id}/input")
def supply_input(workflow_id: str, req: SupplyInputRequest, request: Request, auto_advance: bool = Query(default=True)):
    """Supplies operator inputs to a workflow paused in WAITING_FOR_INPUT and automatically resumes preparation."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    user_id = getattr(request.state, "user_id", None)
    logger.info(f"Operator {user_id} supplying input for workflow {workflow_id}")
    
    kernel = _get_kernel(request)
    try:
        ctx = kernel.supply_input(workflow_id, req.operator_input)
        if auto_advance:
            for _ in range(15):
                prev_state = ctx.current_state
                ctx = kernel.step(workflow_id)
                if ctx.current_state in (
                    WorkflowState.WAITING_FOR_INPUT,
                    WorkflowState.WAITING_FOR_RESOURCE,
                    WorkflowState.WAITING_FOR_APPROVAL,
                    WorkflowState.EXECUTION_READY,
                    WorkflowState.SUCCESS,
                    WorkflowState.EXECUTION_FAILED,
                    WorkflowState.VERIFY_FAILED,
                    WorkflowState.POLICY_DENIED,
                    WorkflowState.ROLLED_BACK,
                ) or ctx.current_state == prev_state:
                    break
        return _workflow_response(ctx)
    except StateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/resume")
def resume_workflow(workflow_id: str, request: Request, auto_advance: bool = Query(default=True)):
    """Resumes a workflow paused in WAITING_FOR_RESOURCE after external resource configuration."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    user_id = getattr(request.state, "user_id", None)
    logger.info(f"Operator {user_id} resuming workflow {workflow_id}")
    
    kernel = _get_kernel(request)
    try:
        ctx = kernel.resume_after_resource_config(workflow_id)
        if auto_advance:
            for _ in range(15):
                prev_state = ctx.current_state
                ctx = kernel.step(workflow_id)
                if ctx.current_state in (
                    WorkflowState.WAITING_FOR_INPUT,
                    WorkflowState.WAITING_FOR_RESOURCE,
                    WorkflowState.WAITING_FOR_APPROVAL,
                    WorkflowState.EXECUTION_READY,
                    WorkflowState.SUCCESS,
                    WorkflowState.EXECUTION_FAILED,
                    WorkflowState.VERIFY_FAILED,
                    WorkflowState.POLICY_DENIED,
                    WorkflowState.ROLLED_BACK,
                ) or ctx.current_state == prev_state:
                    break
        return _workflow_response(ctx)
    except StateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/approve")
def approve_workflow(workflow_id: str, req: ApproveWorkflowRequest, request: Request):
    """Records human Maker-Checker approval and validates separation of duties."""
    _enforce_permission(request, Permission.WORKFLOW_APPROVE)
    approver_id = getattr(request.state, "user_id", None)
        
    kernel = _get_kernel(request)
    try:
        ctx = kernel.approve_workflow(workflow_id, approver_id=approver_id, reason=req.reason)
        return _workflow_response(ctx)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except StateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/deploy", summary="Authorize and execute prepared workflow")
def deploy_workflow(workflow_id: str, request: Request, reason: str = Query(default="Authorized deployment")):
    """Authorizes an execution-ready workflow, executes it, and independently verifies desired state."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    kernel = _get_kernel(request)
    ctx = kernel.repository.get_workflow(workflow_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

    user_id = getattr(request.state, "user_id", None) or "admin.dave"

    # If waiting for approval, approving requires WORKFLOW_APPROVE permission
    if ctx.current_state == WorkflowState.WAITING_FOR_APPROVAL:
        _enforce_permission(request, Permission.WORKFLOW_APPROVE)
        try:
            ctx = kernel.approve_workflow(workflow_id, approver_id=user_id, reason=reason)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    if ctx.current_state == WorkflowState.EXECUTION_READY:
        # Step to EXECUTING -> VERIFYING
        ctx = kernel.step(workflow_id)
        # Step to VERIFYING -> SUCCESS
        if ctx.current_state == WorkflowState.VERIFYING:
            ctx = kernel.step(workflow_id)

    return _workflow_response(ctx)


@router.post("/workflows/{workflow_id}/rollback")
def rollback_workflow(workflow_id: str, request: Request):
    """Triggers pre-validated automated rollback playbook."""
    _enforce_permission(request, Permission.WORKFLOW_ROLLBACK)
    user_id = getattr(request.state, "user_id", None)
    logger.info(f"Operator {user_id} triggering rollback for workflow {workflow_id}")
    
    kernel = _get_kernel(request)
    try:
        ctx = kernel.trigger_rollback(workflow_id)
        return ctx.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/{workflow_id}/events")
def get_workflow_events(workflow_id: str, request: Request):
    """Returns the cryptographic SHA-256 transition audit trail for the workflow."""
    _enforce_permission(request, Permission.WORKFLOW_READ_ALL)
    kernel = _get_kernel(request)
    events = kernel.repository.get_events(workflow_id)
    return [e.to_dict() for e in events]


@router.get("/agents")
def list_agents(request: Request):
    """Lists registered specialist agents, active versions, release stages, and eval scores."""
    _enforce_permission(request, Permission.WORKFLOW_READ_ALL)
    kernel = _get_kernel(request)
    return kernel.repository.list_agent_versions()


@router.get("/evals")
def list_evals(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    """Lists historical evaluation benchmarks and bootstrap statistics."""
    _enforce_permission(request, Permission.WORKFLOW_READ_ALL)
    kernel = _get_kernel(request)
    return kernel.repository.list_eval_runs(limit=limit)


@router.post("/evals/run")
def run_eval(req: RunEvalRequest, request: Request):
    """Triggers an evaluation benchmark run across the designated tier."""
    _enforce_permission(request, Permission.EVAL_RUN)
    kernel = _get_kernel(request)
    summary = AgentOSEvalPlatform.run_tier_eval(tier=req.tier)
    record = {
        "tier": summary.tier,
        "suite_name": summary.suite_name,
        "total_scenarios": summary.total_scenarios,
        "passed_scenarios": summary.passed_scenarios,
        "failed_scenarios": summary.failed_scenarios,
        "pass_rate_pct": summary.pass_rate_pct,
        "bootstrap_ci_95": summary.bootstrap_ci_95,
        "risk_weighted_score": summary.risk_weighted_score,
        "domain_breakdown": summary.domain_breakdown,
        "duration_ms": summary.duration_ms,
    }
    kernel.repository.record_eval_run(record)
    return record
