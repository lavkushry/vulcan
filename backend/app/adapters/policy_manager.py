"""
Project Vulcan: Policy Manager Adapter
Provides API interface for querying enterprise roles, active guardrail policies,
and executing real-time policy evaluation simulations.
"""

from typing import Any, Dict, List, Optional
from app.domain.roles_and_policies import (
    UserRole,
    Permission,
    ROLE_PERMISSIONS,
    PolicyRule,
    PolicyEngine,
    PolicyEvaluationResult,
    EnforcementLevel
)


class PolicyManager:
    def __init__(self):
        self.engine = PolicyEngine()
        self.demo_users = [
            {
                "id": "eng.alice",
                "name": "Alice Cooper",
                "role": UserRole.OPERATOR.value,
                "title": "Senior Infrastructure Engineer",
                "department": "Platform Reliability",
                "allowed_actions": ["catalog:read", "job:request", "dry_run:execute"]
            },
            {
                "id": "lead.bob",
                "name": "Bob Martin",
                "role": UserRole.APPROVING_LEAD.value,
                "title": "Lead SRE / Approving Officer",
                "department": "Core Banking Ops",
                "allowed_actions": ["catalog:read", "job:request", "job:approve", "job:reject", "workflow:dispatch"]
            },
            {
                "id": "sec.carol",
                "name": "Carol Danvers",
                "role": UserRole.SECURITY_ADMIN.value,
                "title": "Information Security & Compliance Lead",
                "department": "Enterprise InfoSec",
                "allowed_actions": ["audit:verify", "policy:manage", "compliance:export"]
            },
            {
                "id": "admin.dave",
                "name": "Dave Bowman",
                "role": UserRole.PLATFORM_ADMIN.value,
                "title": "Platform Engineering Principal",
                "department": "Cloud & Automation Systems",
                "allowed_actions": ["* (All Capabilities, bounded by Maker-Checker)"]
            },
            {
                "id": "audit.emma",
                "name": "Emma Watson",
                "role": UserRole.AUDITOR.value,
                "title": "Senior Regulatory SOX Auditor",
                "department": "Internal Audit & Risk Oversight",
                "allowed_actions": ["audit:verify", "compliance:export (Read-Only)"]
            }
        ]

    def list_roles(self) -> List[Dict[str, Any]]:
        roles_output = []
        for role in UserRole:
            perms = [p.value for p in ROLE_PERMISSIONS.get(role, [])]
            roles_output.append({
                "role": role.value,
                "name": role.name.replace("_", " ").title(),
                "permissions": perms,
                "total_permissions": len(perms),
                "description": self._role_description(role)
            })
        return roles_output

    def _role_description(self, role: UserRole) -> str:
        descs = {
            UserRole.OPERATOR: "Discovers playbooks, triggers dry-runs, and requests executions. High-risk executions require Lead approval.",
            UserRole.APPROVING_LEAD: "Reviews and approves Tier-1 changes. Bound by Four-Eyes Principle (cannot self-approve).",
            UserRole.SECURITY_ADMIN: "Inspects cryptographic Merkle chain logs, audits SoD violations, and manages policy definitions.",
            UserRole.PLATFORM_ADMIN: "Configures connectors, content packs, distributed cron jobs, and global automation policies.",
            UserRole.AUDITOR: "Read-only access for internal audit and regulatory review (OCC / Federal Reserve)."
        }
        return descs.get(role, "")

    def list_demo_users(self) -> List[Dict[str, Any]]:
        return self.demo_users

    def check_user_permission(self, user_id: str, permission: Permission) -> bool:
        """
        Evaluates whether a given user identity possesses a specific granular permission.
        Matches against demo users or evaluates user_id as a role directly.
        """
        user = next((u for u in self.demo_users if u["id"] == user_id), None)
        if user:
            role = UserRole(user["role"])
            if role == UserRole.PLATFORM_ADMIN:
                return True
            return permission in ROLE_PERMISSIONS.get(role, [])

        # Role aliases / demo user fallback
        role_map = {
            "lead.bob": UserRole.APPROVING_LEAD,
            "eng.alice": UserRole.OPERATOR,
            "engineer.alice": UserRole.OPERATOR,
            "sec.carol": UserRole.SECURITY_ADMIN,
            "admin.dave": UserRole.PLATFORM_ADMIN,
            "audit.emma": UserRole.AUDITOR
        }
        mapped_role = role_map.get(user_id)
        if mapped_role:
            if mapped_role == UserRole.PLATFORM_ADMIN:
                return True
            return permission in ROLE_PERMISSIONS.get(mapped_role, [])

        try:
            role = UserRole(user_id)
            if role == UserRole.PLATFORM_ADMIN:
                return True
            return permission in ROLE_PERMISSIONS.get(role, [])
        except ValueError:
            return False

    def list_policies(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.engine.policies.values()]

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        p = self.engine.policies.get(policy_id)
        return p.to_dict() if p else None

    def toggle_policy(self, policy_id: str) -> Dict[str, Any]:
        p = self.engine.policies.get(policy_id)
        if not p:
            return {"ok": False, "message": f"Policy [{policy_id}] not found."}
        
        # PolicyRule is frozen dataclass, recreate with toggled state
        updated = PolicyRule(
            policy_id=p.policy_id,
            name=p.name,
            description=p.description,
            enforcement_level=p.enforcement_level,
            rego_definition=p.rego_definition,
            is_active=not p.is_active,
            tags=p.tags
        )
        self.engine.policies[policy_id] = updated
        state = "ENABLED" if updated.is_active else "DISABLED"
        return {"ok": True, "policy_id": policy_id, "is_active": updated.is_active, "message": f"Policy [{p.name}] is now {state}."}

    def evaluate_execution(
        self,
        user_id: str,
        action_identifier: str,
        environment: str,
        parameters: Dict[str, Any],
        risk_tier: str = "HIGH",
        servicenow_chg: Optional[str] = None,
        is_freeze_active: bool = False,
        is_emergency: bool = False,
        approver_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Determine user role from demo users
        matched_user = next((u for u in self.demo_users if u["id"] == user_id), None)
        user_role = UserRole(matched_user["role"]) if matched_user else UserRole.OPERATOR

        result = self.engine.evaluate(
            user_id=user_id,
            user_role=user_role,
            action_identifier=action_identifier,
            risk_tier=risk_tier,
            environment=environment,
            parameters=parameters,
            servicenow_chg=servicenow_chg,
            is_freeze_active=is_freeze_active,
            is_emergency=is_emergency,
            approver_id=approver_id,
        )
        return result.to_dict()


# Singleton instance
policy_manager = PolicyManager()
