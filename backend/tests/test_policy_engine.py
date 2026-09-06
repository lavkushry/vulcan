"""Unit tests for Vulcan Enterprise Roles & Policies (RBAC/ABAC Engine)."""

import unittest
from app.domain.roles_and_policies import (
    UserRole,
    Permission,
    ROLE_PERMISSIONS,
    PolicyEngine,
    PolicyDecision
)
from app.adapters.policy_manager import policy_manager


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyEngine()

    def test_role_permissions_hierarchy(self):
        # Operator cannot approve jobs
        op_perms = ROLE_PERMISSIONS[UserRole.OPERATOR]
        self.assertIn(Permission.JOB_REQUEST, op_perms)
        self.assertNotIn(Permission.JOB_APPROVE, op_perms)

        # Lead can approve jobs
        lead_perms = ROLE_PERMISSIONS[UserRole.APPROVING_LEAD]
        self.assertIn(Permission.JOB_APPROVE, lead_perms)

        # Security Admin can manage policies
        sec_perms = ROLE_PERMISSIONS[UserRole.SECURITY_ADMIN]
        self.assertIn(Permission.POLICY_MANAGE, sec_perms)
        self.assertNotIn(Permission.JOB_APPROVE, sec_perms)

        # Auditor is read-only
        audit_perms = ROLE_PERMISSIONS[UserRole.AUDITOR]
        self.assertIn(Permission.AUDIT_VERIFY, audit_perms)
        self.assertNotIn(Permission.JOB_REQUEST, audit_perms)

    def test_pol_001_maker_checker_self_approval_blocked(self):
        # Alice requests and attempts to approve her own job -> DENY
        result = self.engine.evaluate(
            user_id="eng.alice",
            user_role=UserRole.OPERATOR,
            action_identifier="net-f5-cert-renew",
            risk_tier="HIGH",
            environment="PROD",
            parameters={"hostname": "f5-edge-01.internal"},
            servicenow_chg="CHG-2026-0001",
            approver_id="eng.alice"  # Self-approval attempt!
        )
        self.assertEqual(result.decision, PolicyDecision.DENY)
        self.assertIn("POL-001", result.denied_policies)

    def test_pol_001_maker_checker_separate_approver_allowed(self):
        # Alice requests, Bob approves -> ALLOW
        result = self.engine.evaluate(
            user_id="eng.alice",
            user_role=UserRole.OPERATOR,
            action_identifier="net-f5-cert-renew",
            risk_tier="HIGH",
            environment="PROD",
            parameters={"hostname": "f5-edge-01.internal"},
            servicenow_chg="CHG-2026-0001",
            approver_id="lead.bob"  # Distinct lead approver!
        )
        self.assertEqual(result.decision, PolicyDecision.ALLOW)
        self.assertIn("POL-001", result.passed_policies)

    def test_pol_002_servicenow_chg_required_in_prod(self):
        # PROD execution without CHG -> DENY
        result = self.engine.evaluate(
            user_id="eng.alice",
            user_role=UserRole.OPERATOR,
            action_identifier="net-f5-cert-renew",
            risk_tier="HIGH",
            environment="PROD",
            parameters={"hostname": "f5-edge-01.internal"},
            servicenow_chg=None
        )
        self.assertEqual(result.decision, PolicyDecision.DENY)
        self.assertIn("POL-002", result.denied_policies)

        # Non-PROD (DEV) execution without CHG -> ALLOW
        dev_result = self.engine.evaluate(
            user_id="eng.alice",
            user_role=UserRole.OPERATOR,
            action_identifier="net-f5-cert-renew",
            risk_tier="HIGH",
            environment="DEV",
            parameters={"hostname": "f5-edge-01.internal"},
            servicenow_chg=None
        )
        self.assertEqual(dev_result.decision, PolicyDecision.ALLOW)

    def test_pol_003_plaintext_secret_linting(self):
        # Parameters containing private key -> DENY
        result = self.engine.evaluate(
            user_id="eng.alice",
            user_role=UserRole.OPERATOR,
            action_identifier="os-rhel-kernel-patch",
            risk_tier="LOW",
            environment="DEV",
            parameters={"token": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0..."}
        )
        self.assertEqual(result.decision, PolicyDecision.DENY)
        self.assertIn("POL-003", result.denied_policies)

    def test_pol_005_operational_freeze_window(self):
        # PROD run during active freeze without emergency flag -> DENY
        result = self.engine.evaluate(
            user_id="eng.alice",
            user_role=UserRole.OPERATOR,
            action_identifier="net-f5-cert-renew",
            risk_tier="HIGH",
            environment="PROD",
            parameters={"hostname": "f5-edge-01.internal"},
            servicenow_chg="CHG-2026-0001",
            is_freeze_active=True,
            is_emergency=False
        )
        self.assertEqual(result.decision, PolicyDecision.DENY)
        self.assertIn("POL-005", result.denied_policies)

        # With Emergency flag -> ALLOW
        emerg_result = self.engine.evaluate(
            user_id="eng.alice",
            user_role=UserRole.OPERATOR,
            action_identifier="net-f5-cert-renew",
            risk_tier="HIGH",
            environment="PROD",
            parameters={"hostname": "f5-edge-01.internal"},
            servicenow_chg="CHG-2026-0001",
            is_freeze_active=True,
            is_emergency=True,
            approver_id="lead.bob"
        )
        self.assertEqual(emerg_result.decision, PolicyDecision.ALLOW)

    def test_policy_manager_evaluate_endpoint(self):
        res = policy_manager.evaluate_execution(
            user_id="eng.alice",
            action_identifier="net-f5-cert-renew",
            environment="PROD",
            parameters={"hostname": "f5-edge-01.internal"},
            risk_tier="HIGH",
            servicenow_chg="CHG-2026-9901"
        )
        # Without approver, High-Risk PROD change requires approval
        self.assertEqual(res["decision"], "REQUIRE_APPROVAL")
        self.assertIn("POL-001", res["gated_policies"])

    def test_servicenow_adapter_fail_closed_on_unknown_and_expired_tickets(self):
        """BKND-16 / CHAT-16: Unknown or expired tickets fail closed."""
        from app.adapters.servicenow_adapter import ServiceNowGateway
        from datetime import datetime, timezone

        snow = ServiceNowGateway(mock_mode=True)
        # Unknown ticket must fail closed
        unknown = snow.validate_chg("CHG-NONEXISTENT-999")
        self.assertFalse(unknown["is_valid"])
        self.assertEqual(unknown["state"], "Invalid")
        self.assertIsNone(unknown["approved_by"])

        # Unknown ticket maintenance window must be False
        now = datetime.now(timezone.utc)
        self.assertFalse(snow.is_within_maintenance_window("CHG-NONEXISTENT-999", now))

        # Expired ticket maintenance window must be False
        self.assertFalse(snow.is_within_maintenance_window("CHG-EXPIRED", now))


if __name__ == "__main__":
    unittest.main()

