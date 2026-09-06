"""
Tests for API Key Authentication Middleware and Execution RBAC (Phase 4 / Gap 2).
Verifies:
1. 503 fail-closed when unconfigured (no tokens, auth not disabled).
2. 401 when token missing or invalid.
3. 200 on exempt endpoints (/healthz, /ready, /metrics) without auth.
4. 403 on execute when caller lacks workflow:dispatch (eng.alice).
5. 200 on execute when caller has workflow:dispatch (lead.bob) + audit row recorded.
6. Spoofing immunity: client-supplied identity header X-Vulcan-User is ignored when token is present.
"""
import os
import unittest
from fastapi.testclient import TestClient

from app.api.auth import APIKeyMiddleware
from app.api.server import create_app
from app.config import container
from app.domain.entities import ExecutionJob, RiskTier, JobStatus


class TestAuthAndExecutionRBAC(unittest.TestCase):
    def setUp(self):
        container.jobs.clear()
        self._orig_env = dict(os.environ)
        self.tokens = {
            "token-alice-12345": "eng.alice",
            "token-bob-67890": "lead.bob",
            "token-admin-99999": "admin.dave"
        }

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_unconfigured_auth_fails_closed_with_503(self):
        """When tokens are empty and allow_disabled=False, server must return 503."""
        os.environ.pop("VULCAN_AUTH_DISABLED", None)
        os.environ.pop("VULCAN_API_TOKENS", None)
        os.environ.pop("VULCAN_API_TOKEN", None)

        app = create_app()
        client = TestClient(app)
        res = client.get("/api/v1/jobs")
        self.assertEqual(res.status_code, 503)
        data = res.json()
        self.assertEqual(data.get("error_code"), "ERR_VULCAN_AUTH_NOT_CONFIGURED")

    def test_exempt_endpoints_accessible_without_auth(self):
        """Exempt endpoints (/healthz, /ready, /metrics) must succeed without auth."""
        app = create_app()
        client = TestClient(app)
        for path in ["/healthz", "/ready", "/metrics"]:
            res = client.get(path)
            self.assertIn(res.status_code, (200, 503))
            self.assertNotIn(res.status_code, (401, 403))

    def test_token_auth_missing_token_returns_401(self):
        """When tokens are configured, unauthenticated requests return 401."""
        app = create_app()
        for m in app.user_middleware:
            if m.cls == APIKeyMiddleware:
                m.kwargs["token_map"] = self.tokens
                m.kwargs["allow_disabled"] = False
        app.middleware_stack = app.build_middleware_stack()

        client = TestClient(app)
        res = client.get("/api/v1/jobs")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("error_code"), "ERR_VULCAN_UNAUTHENTICATED")

    def test_token_auth_invalid_token_returns_401(self):
        """Invalid bearer token returns 401."""
        app = create_app()
        for m in app.user_middleware:
            if m.cls == APIKeyMiddleware:
                m.kwargs["token_map"] = self.tokens
                m.kwargs["allow_disabled"] = False
        app.middleware_stack = app.build_middleware_stack()

        client = TestClient(app)
        res = client.get("/api/v1/jobs", headers={"Authorization": "Bearer bad-token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("error_code"), "ERR_VULCAN_UNAUTHENTICATED")

    def test_execute_rbac_alice_forbidden_bob_allowed(self):
        """
        eng.alice lacks workflow:dispatch -> 403 on execute.
        lead.bob has workflow:dispatch -> 200 on execute + audit record created.
        """
        app = create_app()
        for m in app.user_middleware:
            if m.cls == APIKeyMiddleware:
                m.kwargs["token_map"] = self.tokens
                m.kwargs["allow_disabled"] = False
        app.middleware_stack = app.build_middleware_stack()

        client = TestClient(app)

        cat_item = next(c for c in container.catalog if c.identifier == "net-f5-cert-renew")
        job = ExecutionJob(
            job_id="JOB-AUTH-001",
            correlation_id="CORR-AUTH-001",
            catalog_item=cat_item,
            requester_id="eng.alice",
            target_resource_id="f5-vip-01",
            parameters={"hostname": "f5-edge-01.pnc.com", "vip_ip": "10.200.1.50", "cert_valid_days": 90},
            servicenow_chg="CHG-2026-0001"
        )
        job.status = JobStatus.QUEUED
        container.job_repo.save(job)
        corr_id = job.correlation_id

        # 1. eng.alice tries to execute -> MUST 403
        alice_headers = {"Authorization": "Bearer token-alice-12345"}
        res_alice = client.post(f"/api/v1/jobs/{corr_id}/execute", headers=alice_headers)
        self.assertEqual(res_alice.status_code, 403)
        self.assertIn("ERR_VULCAN_RBAC", str(res_alice.json()))
        self.assertIn("workflow:dispatch", str(res_alice.json()))

        # 2. eng.alice attempts identity spoofing with header -> STILL 403 (token defines identity)
        spoof_headers = {
            "Authorization": "Bearer token-alice-12345",
            "X-Vulcan-User": "lead.bob"
        }
        res_spoof = client.post(f"/api/v1/jobs/{corr_id}/execute", headers=spoof_headers)
        self.assertEqual(res_spoof.status_code, 403)
        self.assertIn("eng.alice", str(res_spoof.json()))

        # 3. lead.bob executes -> 200 DISPATCHED
        bob_headers = {"Authorization": "Bearer token-bob-67890"}
        res_bob = client.post(f"/api/v1/jobs/{corr_id}/execute", headers=bob_headers)
        self.assertEqual(res_bob.status_code, 200)
        self.assertEqual(res_bob.json()["status"], "EXECUTION_DISPATCHED")

        # 4. Verify synchronous audit record committed before execution
        audit_records = [r for r in container.audit_logger.ledger if r.correlation_id == corr_id]
        exec_triggers = [r for r in audit_records if r.action == "EXECUTION_TRIGGERED"]
        self.assertGreaterEqual(len(exec_triggers), 1)
        self.assertEqual(exec_triggers[0].actor, "lead.bob")

        # 5. Verify dispatched_by attribution on job entity
        saved_job = container.job_repo.get_by_correlation_id(corr_id)
        self.assertIsNotNone(saved_job)
        self.assertEqual(saved_job.dispatched_by, "lead.bob")

