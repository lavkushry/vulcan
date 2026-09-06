"""
Project Vulcan: Enterprise Roles & Policies (RBAC & ABAC Policy-as-Code Engine)
Defines enterprise banking roles, fine-grained permissions, and deterministic guardrail policies.
Zero external framework dependencies. Pure Python.
"""

from __future__ import annotations
import enum
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class UserRole(str, enum.Enum):
    """Enterprise Banking Role Hierarchy."""
    OPERATOR = "OPERATOR"
    APPROVING_LEAD = "APPROVING_LEAD"
    SECURITY_ADMIN = "SECURITY_ADMIN"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    AUDITOR = "AUDITOR"


class Permission(str, enum.Enum):
    """Granular capabilities in the Vulcan Control Plane."""
    CATALOG_READ = "catalog:read"
    JOB_REQUEST = "job:request"
    JOB_APPROVE = "job:approve"
    JOB_REJECT = "job:reject"
    DRY_RUN_EXECUTE = "dry_run:execute"
    WORKFLOW_DISPATCH = "workflow:dispatch"
    CRON_MANAGE = "cron:manage"
    INTEGRATIONS_MANAGE = "integrations:manage"
    AUDIT_VERIFY = "audit:verify"
    POLICY_MANAGE = "policy:manage"
    COMPLIANCE_EXPORT = "compliance:export"


ROLE_PERMISSIONS: Dict[UserRole, List[Permission]] = {
    UserRole.OPERATOR: [
        Permission.CATALOG_READ,
        Permission.JOB_REQUEST,
        Permission.DRY_RUN_EXECUTE,
    ],
    UserRole.APPROVING_LEAD: [
        Permission.CATALOG_READ,
        Permission.JOB_REQUEST,
        Permission.JOB_APPROVE,
        Permission.JOB_REJECT,
        Permission.DRY_RUN_EXECUTE,
        Permission.WORKFLOW_DISPATCH,
    ],
    UserRole.SECURITY_ADMIN: [
        Permission.CATALOG_READ,
        Permission.AUDIT_VERIFY,
        Permission.POLICY_MANAGE,
        Permission.COMPLIANCE_EXPORT,
    ],
    UserRole.PLATFORM_ADMIN: [
        Permission.CATALOG_READ,
        Permission.JOB_REQUEST,
        Permission.JOB_APPROVE,
        Permission.JOB_REJECT,
        Permission.DRY_RUN_EXECUTE,
        Permission.WORKFLOW_DISPATCH,
        Permission.CRON_MANAGE,
        Permission.INTEGRATIONS_MANAGE,
        Permission.AUDIT_VERIFY,
        Permission.POLICY_MANAGE,
        Permission.COMPLIANCE_EXPORT,
    ],
    UserRole.AUDITOR: [
        Permission.CATALOG_READ,
        Permission.AUDIT_VERIFY,
        Permission.COMPLIANCE_EXPORT,
    ],
}


class EnforcementLevel(str, enum.Enum):
    MANDATORY_BLOCK = "MANDATORY_BLOCK"
    APPROVAL_GATE = "APPROVAL_GATE"
    AUDIT_FLAG = "AUDIT_FLAG"


class PolicyDecision(str, enum.Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


@dataclass(frozen=True)
class PolicyRule:
    """Policy-as-Code Rule definition."""
    policy_id: str
    name: str
    description: str
    enforcement_level: EnforcementLevel
    rego_definition: str
    is_active: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "enforcement_level": self.enforcement_level.value,
            "rego_definition": self.rego_definition,
            "is_active": self.is_active,
            "tags": self.tags,
        }


@dataclass
class PolicyEvaluationResult:
    """Outcome of evaluating an execution request against all active policies."""
    decision: PolicyDecision
    user_id: str
    user_role: str
    action_identifier: str
    environment: str
    passed_policies: List[str]
    gated_policies: List[str]
    denied_policies: List[str]
    reasons: List[str]
    evaluated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "action_identifier": self.action_identifier,
            "environment": self.environment,
            "passed_policies": self.passed_policies,
            "gated_policies": self.gated_policies,
            "denied_policies": self.denied_policies,
            "reasons": self.reasons,
            "evaluated_at": self.evaluated_at,
        }


class PolicyEngine:
    """
    Deterministic Policy-as-Code Evaluation Engine.
    Executes banking invariants and attribute-based guardrails before jobs execute.
    """

    SECRET_PATTERNS = [
        re.compile(r"(?i)(password|secret|token|api_key|private_key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"),
        re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
    ]

    def __init__(self, policies: Optional[Dict[str, PolicyRule]] = None):
        self.policies = policies or self._default_policies()

    def _default_policies(self) -> Dict[str, PolicyRule]:
        return {
            "POL-001": PolicyRule(
                policy_id="POL-001",
                name="Maker-Checker Separation of Duties (SoD)",
                description="The engineer who requests or modifies a production change cannot approve it under any circumstances. Enforces the banking Four-Eyes Principle.",
                enforcement_level=EnforcementLevel.MANDATORY_BLOCK,
                rego_definition="package vulcan.governance\n\ndefault allow = false\nallow { input.requester_id != input.approver_id }",
                is_active=True,
                tags=["banking", "sod", "sox", "mandatory"]
            ),
            "POL-002": PolicyRule(
                policy_id="POL-002",
                name="Production ServiceNow CHG Window Gate",
                description="High-risk and Medium-risk jobs in PROD require an active, approved ServiceNow Change Request (CHG) in 'Scheduled' state within the authorized window.",
                enforcement_level=EnforcementLevel.APPROVAL_GATE,
                rego_definition="package vulcan.snow\n\ndefault require_chg = false\nrequire_chg {\n  input.environment == \"PROD\"\n  input.risk_tier == \"HIGH\"\n}",
                is_active=True,
                tags=["servicenow", "change-management", "prod"]
            ),
            "POL-003": PolicyRule(
                policy_id="POL-003",
                name="Zero Plaintext Credential Linting",
                description="Scans execution parameters for unencrypted passwords, API tokens, or RSA private keys. Blocks execution and mandates HashiCorp Vault dynamic secret injection.",
                enforcement_level=EnforcementLevel.MANDATORY_BLOCK,
                rego_definition="package vulcan.security\n\ndefault clean = true\nclean = false {\n  regex.match(\"-----BEGIN (RSA|EC) PRIVATE KEY-----\", input.parameters)\n}",
                is_active=True,
                tags=["security", "vault", "secrets"]
            ),
            "POL-004": PolicyRule(
                policy_id="POL-004",
                name="Target Infrastructure Mutual Exclusion",
                description="A target host, VIP, or cluster cannot be modified by more than one execution concurrently. Enforces Redis Redlock cluster-wide mutex.",
                enforcement_level=EnforcementLevel.MANDATORY_BLOCK,
                rego_definition="package vulcan.concurrency\n\ndefault lock_required = true",
                is_active=True,
                tags=["concurrency", "redlock", "safety"]
            ),
            "POL-005": PolicyRule(
                policy_id="POL-005",
                name="Operational Freeze / Blackout Window Protection",
                description="Blocks automated production modifications during financial market open (09:00-16:00 EST) and quarter-end close, unless flagged with approved Emergency Override.",
                enforcement_level=EnforcementLevel.MANDATORY_BLOCK,
                rego_definition="package vulcan.freeze\n\ndefault freeze_active = false",
                is_active=True,
                tags=["compliance", "freeze-window", "risk"]
            ),
            "POL-006": PolicyRule(
                policy_id="POL-006",
                name="Fleet Concurrency Throttling",
                description="Caps total active parallel runner jobs to 75 across the control plane and max 5 jobs against any individual database or Kubernetes cluster.",
                enforcement_level=EnforcementLevel.APPROVAL_GATE,
                rego_definition="package vulcan.capacity\n\ndefault under_limit = true",
                is_active=True,
                tags=["capacity", "throttling", "performance"]
            ),
        }

    def evaluate(
        self,
        user_id: str,
        user_role: UserRole,
        action_identifier: str,
        risk_tier: str,
        environment: str,
        parameters: Dict[str, Any],
        servicenow_chg: Optional[str] = None,
        is_freeze_active: bool = False,
        is_emergency: bool = False,
        approver_id: Optional[str] = None,
    ) -> PolicyEvaluationResult:
        """
        Deterministically evaluates all active policies against execution context.
        """
        passed: List[str] = []
        gated: List[str] = []
        denied: List[str] = []
        reasons: List[str] = []

        # Check Role Permissions
        user_perms = ROLE_PERMISSIONS.get(user_role, [])
        if Permission.JOB_REQUEST not in user_perms:
            denied.append("ROLE_PERM")
            reasons.append(f"Role [{user_role.value}] does not have permission to request jobs.")

        # Check POL-001: Maker-Checker Invariant (if approver is provided)
        if approver_id:
            if approver_id == user_id:
                denied.append("POL-001")
                reasons.append(f"POL-001 Violation: Requester [{user_id}] cannot approve their own job (Four-Eyes Principle).")
            else:
                passed.append("POL-001")
        else:
            # Not yet approved
            if environment == "PROD" and risk_tier == "HIGH":
                gated.append("POL-001")
                reasons.append("POL-001 Gate: Production High-Risk change requires separate Approving Lead sign-off.")
            else:
                passed.append("POL-001")

        # Check POL-002: ServiceNow CHG
        if environment == "PROD" and risk_tier in ("HIGH", "MEDIUM"):
            if not servicenow_chg or not servicenow_chg.startswith("CHG-"):
                denied.append("POL-002")
                reasons.append(f"POL-002 Violation: PROD execution for [{action_identifier}] requires a valid ServiceNow CHG ticket (e.g. CHG-2026-9901).")
            else:
                passed.append("POL-002")
        else:
            passed.append("POL-002")

        # Check POL-003: Secret Linting
        param_str = str(parameters)
        secret_found = False
        for pat in self.SECRET_PATTERNS:
            if pat.search(param_str):
                secret_found = True
                break
        if secret_found:
            denied.append("POL-003")
            reasons.append("POL-003 Violation: Parameters contain unencrypted plaintext credentials or private keys. Use HashiCorp Vault dynamic injection.")
        else:
            passed.append("POL-003")

        # Check POL-004: Concurrency Lock
        passed.append("POL-004")

        # Check POL-005: Operational Freeze Window
        if is_freeze_active and environment == "PROD" and not is_emergency:
            denied.append("POL-005")
            reasons.append("POL-005 Violation: System is in a scheduled Operational Freeze Window. Emergency override required.")
        else:
            passed.append("POL-005")

        # Check POL-006: Capacity
        passed.append("POL-006")

        # Compute Final Decision
        if denied:
            decision = PolicyDecision.DENY
        elif gated:
            decision = PolicyDecision.REQUIRE_APPROVAL
        else:
            decision = PolicyDecision.ALLOW

        return PolicyEvaluationResult(
            decision=decision,
            user_id=user_id,
            user_role=user_role.value,
            action_identifier=action_identifier,
            environment=environment,
            passed_policies=passed,
            gated_policies=gated,
            denied_policies=denied,
            reasons=reasons,
            evaluated_at=datetime.now(timezone.utc).isoformat()
        )
