"""
Project Vulcan: AgentOS Ultra Kernel - WorkflowContext & Deterministic State Machine (AGENT-01)
Author: Architectural Review Board & AgentOS Core Team

Defines:
1. WorkflowState: 22 legal progression states and 13 failure/intervention states.
2. WorkflowContext: Canonical, versioned, persisted runtime envelope.
3. AgentOSStateMachine: Strict deterministic transition validator rejecting illegal agent jumps.
4. WorkflowEvent: Cryptographically chained transition ledger record.
5. OptimisticLockError & StateTransitionError domain exceptions.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Set


class WorkflowState(str, enum.Enum):
    """Deterministic finite state machine states for AgentOS Ultra."""
    # Standard progression
    RECEIVED = "RECEIVED"
    UNDERSTANDING = "UNDERSTANDING"
    DISCOVERING = "DISCOVERING"
    PLANNING = "PLANNING"
    COMPOSING = "COMPOSING"
    GENERATING = "GENERATING"
    RESOLVING_RESOURCES = "RESOLVING_RESOURCES"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    WAITING_FOR_RESOURCE = "WAITING_FOR_RESOURCE"
    WAITING_FOR_SECRET = "WAITING_FOR_SECRET"
    VALIDATING = "VALIDATING"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    TESTING = "TESTING"
    CRITIC_REVIEW = "CRITIC_REVIEW"
    POLICY_CHECK = "POLICY_CHECK"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    EXECUTION_READY = "EXECUTION_READY"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    CURATING = "CURATING"
    EVALUATING = "EVALUATING"

    # Failure / Interruption states
    INTENT_UNCERTAIN = "INTENT_UNCERTAIN"
    DISCOVERY_FAILED = "DISCOVERY_FAILED"
    PLAN_REJECTED = "PLAN_REJECTED"
    GENERATION_FAILED = "GENERATION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SECURITY_REJECTED = "SECURITY_REJECTED"
    TEST_FAILED = "TEST_FAILED"
    POLICY_DENIED = "POLICY_DENIED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFY_FAILED = "VERIFY_FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    MANUAL_INTERVENTION_REQUIRED = "MANUAL_INTERVENTION_REQUIRED"


class AgentOSError(Exception):
    """Base error for AgentOS operations."""
    pass


class StateTransitionError(AgentOSError):
    """Raised when an illegal state machine transition is attempted."""
    def __init__(self, from_state: str, to_state: str, reason: str = ""):
        super().__init__(f"Illegal transition from '{from_state}' to '{to_state}'. {reason}".strip())
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason


class OptimisticLockError(AgentOSError):
    """Raised when a stale agent write attempts to overwrite newer state."""
    def __init__(self, workflow_id: str, expected_version: int, actual_version: int):
        super().__init__(
            f"Optimistic lock conflict on workflow '{workflow_id}': "
            f"expected version {expected_version}, but current version is {actual_version}."
        )
        self.workflow_id = workflow_id
        self.expected_version = expected_version
        self.actual_version = actual_version


@dataclass
class WorkflowEvent:
    """Cryptographically chained event for state transitions."""
    workflow_id: str
    correlation_id: str
    from_state: WorkflowState
    to_state: WorkflowState
    actor: str
    agent_name: Optional[str] = None
    agent_version: Optional[str] = None
    reason: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = "0" * 64
    current_hash: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.current_hash:
            self.current_hash = self.compute_hash(
                self.workflow_id,
                self.correlation_id,
                self.from_state.value if isinstance(self.from_state, WorkflowState) else str(self.from_state),
                self.to_state.value if isinstance(self.to_state, WorkflowState) else str(self.to_state),
                self.actor,
                self.prev_hash,
                self.timestamp.isoformat(),
                self.payload
            )

    @staticmethod
    def compute_hash(
        workflow_id: str,
        correlation_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        prev_hash: str,
        timestamp_str: str,
        payload: Dict[str, Any]
    ) -> str:
        body = {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "from_state": from_state,
            "to_state": to_state,
            "actor": actor,
            "prev_hash": prev_hash,
            "timestamp": timestamp_str,
            "payload": payload,
        }
        raw = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "from_state": self.from_state.value if isinstance(self.from_state, WorkflowState) else str(self.from_state),
            "to_state": self.to_state.value if isinstance(self.to_state, WorkflowState) else str(self.to_state),
            "actor": self.actor,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "reason": self.reason,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "current_hash": self.current_hash,
            "timestamp": self.timestamp.isoformat(),
        }


class AgentOSStateMachine:
    """
    Deterministic transition table.
    Enforces that only legal workflow transitions occur and records audit events.
    """

    TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
        WorkflowState.RECEIVED: {
            WorkflowState.UNDERSTANDING,
            WorkflowState.INTENT_UNCERTAIN,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.UNDERSTANDING: {
            WorkflowState.DISCOVERING,
            WorkflowState.WAITING_FOR_INPUT,
            WorkflowState.INTENT_UNCERTAIN,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.WAITING_FOR_INPUT: {
            WorkflowState.UNDERSTANDING,
            WorkflowState.INTENT_UNCERTAIN,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.INTENT_UNCERTAIN: {
            WorkflowState.UNDERSTANDING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.DISCOVERING: {
            WorkflowState.PLANNING,
            WorkflowState.DISCOVERY_FAILED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.DISCOVERY_FAILED: {
            WorkflowState.DISCOVERING,
            WorkflowState.PLANNING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.PLANNING: {
            WorkflowState.COMPOSING,
            WorkflowState.GENERATING,
            WorkflowState.PLAN_REJECTED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.COMPOSING: {
            WorkflowState.RESOLVING_RESOURCES,
            WorkflowState.GENERATING,
            WorkflowState.PLAN_REJECTED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.GENERATING: {
            WorkflowState.RESOLVING_RESOURCES,
            WorkflowState.GENERATION_FAILED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.GENERATION_FAILED: {
            WorkflowState.GENERATING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.RESOLVING_RESOURCES: {
            WorkflowState.VALIDATING,
            WorkflowState.WAITING_FOR_RESOURCE,
            WorkflowState.WAITING_FOR_SECRET,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.WAITING_FOR_RESOURCE: {
            WorkflowState.RESOLVING_RESOURCES,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.WAITING_FOR_SECRET: {
            WorkflowState.RESOLVING_RESOURCES,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.VALIDATING: {
            WorkflowState.SECURITY_REVIEW,
            WorkflowState.VALIDATION_FAILED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.VALIDATION_FAILED: {
            WorkflowState.GENERATING,
            WorkflowState.PLANNING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.SECURITY_REVIEW: {
            WorkflowState.TESTING,
            WorkflowState.CRITIC_REVIEW,
            WorkflowState.SECURITY_REJECTED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.SECURITY_REJECTED: {
            WorkflowState.PLANNING,
            WorkflowState.GENERATING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.TESTING: {
            WorkflowState.CRITIC_REVIEW,
            WorkflowState.TEST_FAILED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.TEST_FAILED: {
            WorkflowState.GENERATING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.CRITIC_REVIEW: {
            WorkflowState.POLICY_CHECK,
            WorkflowState.PLAN_REJECTED,
            WorkflowState.GENERATING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.PLAN_REJECTED: {
            WorkflowState.PLANNING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.POLICY_CHECK: {
            WorkflowState.WAITING_FOR_APPROVAL,
            WorkflowState.EXECUTION_READY,
            WorkflowState.POLICY_DENIED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.POLICY_DENIED: {
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.WAITING_FOR_APPROVAL: {
            WorkflowState.EXECUTION_READY,
            WorkflowState.POLICY_DENIED,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.EXECUTION_READY: {
            WorkflowState.EXECUTING,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.EXECUTING: {
            WorkflowState.VERIFYING,
            WorkflowState.EXECUTION_FAILED,
            WorkflowState.ROLLING_BACK,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.EXECUTION_FAILED: {
            WorkflowState.ROLLING_BACK,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.VERIFYING: {
            WorkflowState.SUCCESS,
            WorkflowState.VERIFY_FAILED,
            WorkflowState.ROLLING_BACK,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.VERIFY_FAILED: {
            WorkflowState.ROLLING_BACK,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.ROLLING_BACK: {
            WorkflowState.ROLLED_BACK,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.ROLLED_BACK: {
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
        },
        WorkflowState.SUCCESS: {
            WorkflowState.CURATING,
            WorkflowState.EVALUATING,
        },
        WorkflowState.CURATING: {
            WorkflowState.EVALUATING,
            WorkflowState.SUCCESS,
        },
        WorkflowState.EVALUATING: set(),
        WorkflowState.MANUAL_INTERVENTION_REQUIRED: {
            WorkflowState.UNDERSTANDING,
            WorkflowState.DISCOVERING,
            WorkflowState.PLANNING,
            WorkflowState.GENERATING,
            WorkflowState.RESOLVING_RESOURCES,
            WorkflowState.VALIDATING,
            WorkflowState.EXECUTING,
            WorkflowState.ROLLING_BACK,
        },
    }

    @classmethod
    def can_transition(cls, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        allowed = cls.TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def validate_transition(cls, from_state: WorkflowState, to_state: WorkflowState, reason: str = "") -> None:
        if not cls.can_transition(from_state, to_state):
            raise StateTransitionError(
                from_state=from_state.value,
                to_state=to_state.value,
                reason=reason or f"Allowed target states from {from_state.value} are: {[s.value for s in cls.TRANSITIONS.get(from_state, set())]}"
            )


@dataclass
class WorkflowContext:
    """
    Canonical persisted envelope representing an AgentOS Ultra execution lifecycle.
    Survives restarts, crashes, node migrations, and long approval/resource waits.
    """
    workflow_id: str
    correlation_id: str
    requester_id: str
    original_request: str
    environment: str = "PROD"
    current_state: WorkflowState = WorkflowState.RECEIVED
    version: int = 1

    # Structured domains
    normalized_intent: Dict[str, Any] = field(default_factory=dict)
    desired_state: Dict[str, Any] = field(default_factory=dict)
    risk_classification: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    discovered_assets: List[Dict[str, Any]] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    automation_plan: Dict[str, Any] = field(default_factory=dict)
    generated_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    required_resources: List[Dict[str, Any]] = field(default_factory=list)
    resolved_resources: Dict[str, Any] = field(default_factory=dict)
    secret_references: List[str] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    security_findings: List[Dict[str, Any]] = field(default_factory=list)
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    critic_findings: List[Dict[str, Any]] = field(default_factory=list)
    policy_decision: Dict[str, Any] = field(default_factory=dict)
    approval_records: List[Dict[str, Any]] = field(default_factory=list)
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    execution_result: Dict[str, Any] = field(default_factory=dict)
    postcondition_verification: Dict[str, Any] = field(default_factory=dict)
    rollback_state: Dict[str, Any] = field(default_factory=dict)
    curation_state: Dict[str, Any] = field(default_factory=dict)
    eval_result: Dict[str, Any] = field(default_factory=dict)

    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def transition_to(
        self,
        new_state: WorkflowState,
        actor: str = "deterministic_kernel",
        agent_name: Optional[str] = None,
        agent_version: Optional[str] = None,
        reason: str = "",
        payload: Optional[Dict[str, Any]] = None,
        prev_hash: str = "0" * 64,
    ) -> WorkflowEvent:
        """
        Commit a state machine transition deterministically.
        Rejects illegal state hops and emits an immutable WorkflowEvent.
        """
        AgentOSStateMachine.validate_transition(self.current_state, new_state, reason=reason)
        from_state = self.current_state
        self.current_state = new_state
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1

        event = WorkflowEvent(
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            from_state=from_state,
            to_state=new_state,
            actor=actor,
            agent_name=agent_name,
            agent_version=agent_version,
            reason=reason,
            payload=payload or {},
            prev_hash=prev_hash,
            timestamp=self.updated_at,
        )
        return event

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "requester_id": self.requester_id,
            "environment": self.environment,
            "current_state": self.current_state.value if isinstance(self.current_state, WorkflowState) else str(self.current_state),
            "version": self.version,
            "original_request": self.original_request,
            "normalized_intent": copy.deepcopy(self.normalized_intent),
            "desired_state": copy.deepcopy(self.desired_state),
            "risk_classification": copy.deepcopy(self.risk_classification),
            "assumptions": copy.deepcopy(self.assumptions),
            "unresolved_questions": copy.deepcopy(self.unresolved_questions),
            "discovered_assets": copy.deepcopy(self.discovered_assets),
            "provenance": copy.deepcopy(self.provenance),
            "automation_plan": copy.deepcopy(self.automation_plan),
            "generated_artifacts": copy.deepcopy(self.generated_artifacts),
            "required_resources": copy.deepcopy(self.required_resources),
            "resolved_resources": copy.deepcopy(self.resolved_resources),
            "secret_references": copy.deepcopy(self.secret_references),
            "validation_results": copy.deepcopy(self.validation_results),
            "security_findings": copy.deepcopy(self.security_findings),
            "test_results": copy.deepcopy(self.test_results),
            "critic_findings": copy.deepcopy(self.critic_findings),
            "policy_decision": copy.deepcopy(self.policy_decision),
            "approval_records": copy.deepcopy(self.approval_records),
            "execution_plan": copy.deepcopy(self.execution_plan),
            "execution_result": copy.deepcopy(self.execution_result),
            "postcondition_verification": copy.deepcopy(self.postcondition_verification),
            "rollback_state": copy.deepcopy(self.rollback_state),
            "curation_state": copy.deepcopy(self.curation_state),
            "eval_result": copy.deepcopy(self.eval_result),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkflowContext:
        ctx = cls(
            workflow_id=data["workflow_id"],
            correlation_id=data["correlation_id"],
            requester_id=data.get("requester_id", "anonymous"),
            original_request=data.get("original_request", ""),
            environment=data.get("environment", "PROD"),
            current_state=WorkflowState(data.get("current_state", "RECEIVED")),
            version=int(data.get("version", 1)),
            normalized_intent=data.get("normalized_intent", {}),
            desired_state=data.get("desired_state", {}),
            risk_classification=data.get("risk_classification", {}),
            assumptions=data.get("assumptions", []),
            unresolved_questions=data.get("unresolved_questions", []),
            discovered_assets=data.get("discovered_assets", []),
            provenance=data.get("provenance", {}),
            automation_plan=data.get("automation_plan", {}),
            generated_artifacts=data.get("generated_artifacts", []),
            required_resources=data.get("required_resources", []),
            resolved_resources=data.get("resolved_resources", {}),
            secret_references=data.get("secret_references", []),
            validation_results=data.get("validation_results", []),
            security_findings=data.get("security_findings", []),
            test_results=data.get("test_results", []),
            critic_findings=data.get("critic_findings", []),
            policy_decision=data.get("policy_decision", {}),
            approval_records=data.get("approval_records", []),
            execution_plan=data.get("execution_plan", {}),
            execution_result=data.get("execution_result", {}),
            postcondition_verification=data.get("postcondition_verification", {}),
            rollback_state=data.get("rollback_state", {}),
            curation_state=data.get("curation_state", {}),
            eval_result=data.get("eval_result", {}),
            error_message=data.get("error_message"),
        )
        if "created_at" in data:
            ctx.created_at = datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"]
        if "updated_at" in data:
            ctx.updated_at = datetime.fromisoformat(data["updated_at"]) if isinstance(data["updated_at"], str) else data["updated_at"]
        return ctx
