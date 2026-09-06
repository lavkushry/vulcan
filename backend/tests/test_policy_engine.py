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

    def test_pre_dispatch_maintenance_window_blocked_transitions_to_failed(self):
        """Pre-dispatch invariant: Execution blocked by closed maintenance window fails closed to FAILED."""
        from fastapi.testclient import TestClient
        from app.api.server import create_app
        from app.config import container
        from app.domain.entities import ExecutionJob, JobStatus

        app = create_app()
        client = TestClient(app)

        cat_item = next(c for c in container.catalog if c.identifier == "sec-system-hardening")
        job = ExecutionJob(
            job_id="job-window-test-01",
            correlation_id="EXEC-WINDOW-FAIL-01",
            catalog_item=cat_item,
            requester_id="eng.alice",
            target_resource_id="f5-vip-01",
            parameters={"port": 22, "auto_updates": True},
            servicenow_chg="CHG-EXPIRED"
        )
        job.status = JobStatus.QUEUED
        container.job_repo.save(job)
        container.jobs[job.correlation_id] = job

        bob_headers = {"Authorization": "Bearer vlc_test_bob"}
        res = client.post(f"/api/v1/jobs/{job.correlation_id}/execute", headers=bob_headers)
        self.assertEqual(res.status_code, 409)
        detail = res.json().get("detail", {})
        err_code = detail.get("error_code") if isinstance(detail, dict) else str(detail)
        self.assertIn("ERR_VULCAN_MAINTENANCE_WINDOW_CLOSED", err_code)

        # Verify job is strictly in FAILED status, NOT QUEUED, and NEVER reached RUNNING
        saved_job = container.job_repo.get_by_correlation_id(job.correlation_id)
        self.assertIsNotNone(saved_job)
        self.assertEqual(saved_job.status, JobStatus.FAILED)
        self.assertIn("Outside approved maintenance window", saved_job.error_message)

        # Verify EXEC_BLOCKED audit record
        records = [r for r in container.audit_logger.ledger if r.correlation_id == job.correlation_id]
        blocked = [r for r in records if r.action == "EXEC_BLOCKED"]
        self.assertGreaterEqual(len(blocked), 1)
        self.assertEqual(blocked[0].payload.get("reason"), "MAINTENANCE_WINDOW_CLOSED")

    def test_runner_maintenance_window_block_never_enters_running(self):
        """Runner-level invariant: maintenance window block transitions QUEUED→FAILED, never RUNNING.

        Regression test for the RUNNING→QUEUED state regression observed in WS stream.
        The runner's window check fires BEFORE the RUNNING transition (step 2 vs step 7),
        so a blocked job must go directly to FAILED without burning a worker slot or
        entering the RUNNING state.
        """
        from unittest.mock import MagicMock
        from app.config import container
        from app.domain.entities import ExecutionJob, JobStatus
        from app.domain.exceptions import MaintenanceWindowClosedError

        cat_item = next(c for c in container.catalog if c.identifier == "sec-system-hardening")
        job = ExecutionJob(
            job_id="job-runner-window-01",
            correlation_id="EXEC-RUNNER-WINDOW-01",
            catalog_item=cat_item,
            requester_id="eng.alice",
            target_resource_id="runner-test-host-01",
            parameters={"port": 22, "auto_updates": True},
            servicenow_chg="CHG-EXPIRED"
        )
        job.status = JobStatus.QUEUED

        # Track all status events emitted by the runner
        status_events = []

        def capture_status(corr_id, status, message):
            status_events.append({"correlation_id": corr_id, "status": status, "message": message})

        runner = container.create_runner(
            log_event_stream=None,
            status_event_stream=capture_status
        )

        # The runner must raise MaintenanceWindowClosedError and never reach RUNNING
        with self.assertRaises(MaintenanceWindowClosedError):
            runner.run(job)

        # Job must be in FAILED state — not QUEUED, not RUNNING
        self.assertEqual(job.status, JobStatus.FAILED,
            f"Expected FAILED but got {job.status.value}. "
            "Blocked jobs must fail-close, never remain dispatchable in QUEUED.")

        # No RUNNING status event should have been emitted
        running_events = [e for e in status_events if e["status"] == "RUNNING"]
        self.assertEqual(len(running_events), 0,
            "Runner emitted a RUNNING status event before the maintenance window check. "
            "This is the RUNNING→QUEUED regression: WS clients see RUNNING, then the job "
            "reverts to a non-RUNNING terminal state.")

        # Verify error message contains window information
        self.assertIn("outside the approved", job.error_message.lower(),
            "Error message should explain the maintenance window block.")

        # Verify completed_at is set (terminal state)
        self.assertIsNotNone(job.completed_at,
            "FAILED jobs must have completed_at set.")


if __name__ == "__main__":
    unittest.main()

