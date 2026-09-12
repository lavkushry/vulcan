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
        import uuid
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
        raise NotImplementedError(
            "GovernancePolicyEngine requires IServiceNowGateway to be configured. "
            "Use SimulationPolicyEngine for CI/testing."
        )
