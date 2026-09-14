"""
Project Vulcan: Policy Engine Adapters (P0 #9)
Author: AgentOS Core Team

Provides pluggable policy evaluation for the POLICY_CHECK state.
SimulationPolicyEngine uses inline risk-based logic for CI.
GovernancePolicyEngine delegates to ServiceNow/CMDB for production.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional

from app.agentos.context import WorkflowContext


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    decision: str  # "APPROVED", "DENIED", "REQUIRES_APPROVAL"
    decision_id: str
    reason: str
    change_ticket: Optional[str] = None
    in_maintenance_window: Optional[bool] = None


class IPolicyEngine(abc.ABC):
    """Abstract policy engine for POLICY_CHECK state evaluation."""

    @property
    @abc.abstractmethod
    def is_simulation(self) -> bool:
        pass

    @abc.abstractmethod
    def evaluate(self, ctx: WorkflowContext) -> PolicyDecision:
        """Evaluate policy for the given workflow context."""
        pass


class SimulationPolicyEngine(IPolicyEngine):
    """CI/testing policy engine using inline risk-based logic."""

    @property
    def is_simulation(self) -> bool:
        return True

    def evaluate(self, ctx: WorkflowContext) -> PolicyDecision:
        import os
        import uuid

        # 1. Maintenance / Freeze Window Enforcement
        freeze_active = (
            os.environ.get("AGENTOS_SIMULATE_FREEZE") == "1"
            or any("freeze" in str(a).lower() for a in ctx.assumptions)
            or bool(ctx.risk_classification.get("freeze_window_active"))
        )
        if freeze_active:
            return PolicyDecision(
                decision="DENIED",
                decision_id=f"pol-freeze-{uuid.uuid4().hex[:8]}",
                reason="Changes blocked: Active change freeze window enforced.",
                in_maintenance_window=False,
            )

        # 2. Destructive Operations & Security Policy Violations
        req_lower = (ctx.original_request or "").lower()
        destructive_or_malicious = (
            "drop database" in req_lower
            or "rm -rf" in req_lower
            or "/etc/shadow" in req_lower
            or "/etc/passwd" in req_lower
            or ("curl" in req_lower and "evil" in req_lower)
            or ("wget" in req_lower and "evil" in req_lower)
        )
        has_blocker_findings = any(
            f.get("severity") in ("CRITICAL", "BLOCKER") for f in (ctx.security_findings or [])
        )

        if destructive_or_malicious or has_blocker_findings:
            return PolicyDecision(
                decision="DENIED",
                decision_id=f"pol-deny-{uuid.uuid4().hex[:8]}",
                reason="Security policy violation: Destructive operations, credential exfiltration, or untrusted payload injection detected.",
            )

        risk = ctx.risk_classification.get("risk_tier", "MEDIUM")
        req_mc = ctx.risk_classification.get("requires_maker_checker", True)

        if req_mc or ctx.environment == "PROD":
            return PolicyDecision(
                decision="REQUIRES_APPROVAL",
                decision_id=f"pol-sim-{uuid.uuid4().hex[:8]}",
                reason="Production or High Risk requires explicit human Maker-Checker sign-off.",
            )
        else:
            return PolicyDecision(
                decision="APPROVED",
                decision_id=f"pol-sim-{uuid.uuid4().hex[:8]}",
                reason="Low risk non-prod policy check passed automatically.",
            )


class GovernancePolicyEngine(IPolicyEngine):
    """Production policy engine skeleton. Delegates to ServiceNow/CMDB."""

    def __init__(self, servicenow_gateway=None):
        self._servicenow = servicenow_gateway

    @property
    def is_simulation(self) -> bool:
        return False

    def evaluate(self, ctx: WorkflowContext) -> PolicyDecision:
        # TODO: Wire to IServiceNowGateway for change-window validation
        raise NotImplementedError("AgentOS production execution is not yet implemented (GovernancePolicyEngine)")
