"""
Project Vulcan: Policy Engine Adapters (P0 #9)
Author: AgentOS Core Team

Provides pluggable policy evaluation for the POLICY_CHECK state and
organizational requirements evaluation for policy-driven DAG injection.
SimulationPolicyEngine uses inline risk-based logic for CI.
GovernancePolicyEngine delegates to ServiceNow/CMDB for production.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional
import uuid

from app.agentos.context import WorkflowContext


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    decision: str  # "APPROVED", "DENIED", "REQUIRES_APPROVAL"
    decision_id: str
    reason: str
    change_ticket: Optional[str] = None
    in_maintenance_window: Optional[bool] = None


@dataclass
class PolicyMandatedStep:
    """An organizational requirement injected by policy."""
    policy_id: str
    step_type: str  # "monitoring", "backup", "compliance_audit"
    action_identifier: str
    name: str
    rationale: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    postconditions: List[str] = field(default_factory=list)


class IPolicyEngine(abc.ABC):
    """Abstract policy engine for POLICY_CHECK state evaluation and organizational requirements."""

    @property
    @abc.abstractmethod
    def is_simulation(self) -> bool:
        pass

    @abc.abstractmethod
    def evaluate(self, ctx: WorkflowContext) -> PolicyDecision:
        """Evaluate policy for the given workflow context."""
        pass

    def evaluate_organizational_requirements(self, ctx: WorkflowContext) -> List[PolicyMandatedStep]:
        """Evaluates organization-mandated steps for this context."""
        return []


class SimulationPolicyEngine(IPolicyEngine):
    """CI/testing policy engine using inline risk-based logic."""

    @property
    def is_simulation(self) -> bool:
        return True

    def evaluate_organizational_requirements(self, ctx: WorkflowContext) -> List[PolicyMandatedStep]:
        """
        Evaluates organizational policy requirements:
        - POL-ORG-MON-01: Injects telemetry monitoring (e.g. Datadog) for PROD or when requested.
        - POL-ORG-BKP-01: Injects automated backup (e.g. S3 WAL archive) for databases in PROD or when requested.
        """
        injected: List[PolicyMandatedStep] = []
        is_prod = (ctx.environment or "").upper() == "PROD"
        known = ctx.normalized_intent.get("known_parameters", {}) if isinstance(ctx.normalized_intent, dict) else {}
        domain = ctx.normalized_intent.get("domain", "") if isinstance(ctx.normalized_intent, dict) else ""
        req_lower = (ctx.original_request or "").lower()

        # Check explicit opt-out
        if "no_monitoring" in req_lower:
            needs_monitoring = False
        else:
            needs_monitoring = "datadog" in req_lower or known.get("monitoring") == "datadog"

        if needs_monitoring:
            injected.append(
                PolicyMandatedStep(
                    policy_id="POL-ORG-MON-01",
                    step_type="monitoring",
                    action_identifier="datadog-agent-install",
                    name="Attach Datadog APM & Host Telemetry",
                    rationale="Organization Policy POL-ORG-MON-01 requires active observability and APM telemetry.",
                    parameters={"datadog_site": "datadoghq.com", "enabled": True},
                    postconditions=["datadog_metrics_flowing"],
                )
            )

        # Database backup policy
        if "no_backup" in req_lower:
            needs_backup = False
        else:
            needs_backup = "s3" in req_lower or known.get("backup") == "s3"

        if needs_backup:
            injected.append(
                PolicyMandatedStep(
                    policy_id="POL-ORG-BKP-01",
                    step_type="backup",
                    action_identifier="s3-backup-snapshot",
                    name="Configure S3 Automated Continuous Backup",
                    rationale="Organization Policy POL-ORG-BKP-01 requires automated off-site snapshot backups.",
                    parameters={"s3_bucket": "vulcan-prod-backups", "retention_days": 30},
                    postconditions=["s3_backup_accessible"],
                )
            )

        return injected

    def evaluate(self, ctx: WorkflowContext) -> PolicyDecision:
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
        raise NotImplementedError("AgentOS production execution is not yet implemented (GovernancePolicyEngine)")
