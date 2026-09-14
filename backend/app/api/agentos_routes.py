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



@router.post("/workflows")
def create_workflow(req: CreateWorkflowRequest, request: Request):
    """Creates and persists a new canonical WorkflowContext in RECEIVED state."""
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
        return ctx.to_dict()
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
    """Retrieves full WorkflowContext by workflow_id."""
    _enforce_permission(request, Permission.WORKFLOW_READ_ALL)
    kernel = _get_kernel(request)
    ctx = kernel.repository.get_workflow(workflow_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return ctx.to_dict()


@router.post("/workflows/{workflow_id}/step")
def step_workflow(workflow_id: str, request: Request):
    """Advances workflow execution by one specialist agent step."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    kernel = _get_kernel(request)
    try:
        ctx = kernel.step(workflow_id)
        return ctx.to_dict()
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
        "workflow": ctx.to_dict(),
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
def supply_input(workflow_id: str, req: SupplyInputRequest, request: Request):
    """Supplies operator inputs to a workflow paused in WAITING_FOR_INPUT."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    user_id = getattr(request.state, "user_id", None)
    logger.info(f"Operator {user_id} supplying input for workflow {workflow_id}")
    
    kernel = _get_kernel(request)
    try:
        ctx = kernel.supply_input(workflow_id, req.operator_input)
        return ctx.to_dict()
    except StateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/resume")
def resume_workflow(workflow_id: str, request: Request):
    """Resumes a workflow paused in WAITING_FOR_RESOURCE after external resource configuration."""
    _enforce_permission(request, Permission.WORKFLOW_ADVANCE)
    user_id = getattr(request.state, "user_id", None)
    logger.info(f"Operator {user_id} resuming workflow {workflow_id}")
    
    kernel = _get_kernel(request)
    try:
        ctx = kernel.resume_after_resource_config(workflow_id)
        return ctx.to_dict()
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
        return ctx.to_dict()
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except StateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
