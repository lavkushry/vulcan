"""
Project Vulcan: Operator Console Vertical Slice End-to-End Tests
Verifies the integration contracts expected by the Next.js Operator Console:
1. POST /api/v1/intent/resolve with { text } returning READY, match, ParamSpec[], confidence, servicenow_chg
2. POST /api/v1/jobs with { identifier, parameters, requester_id, servicenow_chg }
3. Anti-Self-Approval gate: Alice cannot approve Alice -> HTTP 403
4. Checker Sign-off: Bob approves Alice -> HTTP 200 QUEUED
5. Execution Dispatch: POST /api/v1/jobs/{id}/execute -> HTTP 200
6. Rejection Gate: POST /api/v1/jobs/{id}/reject -> HTTP 200 REJECTED
7. WebSocket Hub Event schema: { seq, type, data: { line, ... }, timestamp }
"""
import time
import unittest
from fastapi.testclient import TestClient

from app.api.server import app
from app.api.websockets import ws_hub
from app.config import container
from app.domain.entities import JobStatus


class TestOperatorConsoleVerticalSlice(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_intent_resolution_operator_console_contract(self):
        """Resolves prompt text into structured match, parameters, and ParamSpec array."""
        payload = {
            "text": "Renew SSL certificate for f5-edge-01.pnc.com on VIP 10.200.1.50 with validity 90 days"
        }
        res = self.client.post("/api/v1/intent/resolve", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "READY")
        self.assertIsNotNone(data["match"])
        self.assertEqual(data["match"]["identifier"], "net-f5-cert-renew")
        self.assertTrue(data["match"]["requires_maker_checker"])
        self.assertTrue(data["match"]["requires_chg"])
        self.assertGreaterEqual(len(data["match"]["params"]), 3)
        self.assertEqual(data["parameters"]["vip_ip"], "10.200.1.50")
        self.assertEqual(data["parameters"]["hostname"], "f5-edge-01.pnc.com")
        self.assertIsNotNone(data["servicenow_chg"])
        self.assertGreater(data["confidence"], 0.8)

    def test_full_operator_console_lifecycle(self):
        """End-to-end lifecycle: Alice submits -> Alice tries self-approval (fails) -> Bob approves -> Executes."""
        # 1. Alice creates high-risk job
        create_payload = {
            "identifier": "net-f5-cert-renew",
            "requester_id": "eng.alice",
            "parameters": {
                "hostname": "f5-edge-01.pnc.com",
                "vip_ip": "10.200.1.50",
                "cert_valid_days": 90
            },
            "servicenow_chg": "CHG-DEMO-001"
        }
        create_res = self.client.post("/api/v1/jobs", json=create_payload)
        self.assertEqual(create_res.status_code, 200)
        job = create_res.json()
        job_id = job["id"]
        corr_id = job["correlation_id"]

        self.assertEqual(job["status"], "PENDING_APPROVAL")
        self.assertEqual(job["requester_id"], "eng.alice")
        self.assertEqual(job["identifier"], "net-f5-cert-renew")

        # 2. Alice attempts to approve her own change -> MUST FAIL WITH 403
        alice_approval = {
            "approver_id": "eng.alice"
        }
        self_res = self.client.post(f"/api/v1/jobs/{job_id}/approve", json=alice_approval)
        self.assertEqual(self_res.status_code, 403)
        self.assertIn("Separation of Duties Violation", self_res.json()["detail"])

        # 3. Bob approves Alice's change -> 200 OK
        bob_approval = {
            "approver_id": "lead.bob"
        }
        bob_res = self.client.post(f"/api/v1/jobs/{job_id}/approve", json=bob_approval)
        self.assertEqual(bob_res.status_code, 200)
        approved_job = bob_res.json()
        self.assertEqual(approved_job["status"], "QUEUED")
        self.assertEqual(approved_job["approver_id"], "lead.bob")

        # 4. Trigger execution
        exec_res = self.client.post(f"/api/v1/jobs/{corr_id}/execute")
        self.assertEqual(exec_res.status_code, 200)

        # Allow worker thread to complete execution with polling
        final_job = None
        for _ in range(15):
            time.sleep(0.2)
            final_job = self.client.get(f"/api/v1/jobs/{corr_id}").json()
            if final_job["status"] in ("SUCCESS", "FAILED"):
                break

        # 5. Verify final status is SUCCESS
        self.assertIsNotNone(final_job)
        self.assertEqual(final_job["status"], "SUCCESS")
        self.assertEqual(final_job["exit_code"], 0)

    def test_rejection_lifecycle(self):
        """Checker can reject a job and transition status to REJECTED."""
        create_payload = {
            "identifier": "net-f5-cert-renew",
            "requester_id": "eng.alice",
            "parameters": {
                "hostname": "f5-edge-01.pnc.com",
                "vip_ip": "10.200.1.50",
                "cert_valid_days": 90
            },
            "servicenow_chg": "CHG-DEMO-002"
        }
        job = self.client.post("/api/v1/jobs", json=create_payload).json()
        job_id = job["id"]

        reject_payload = {
            "approver_id": "lead.bob",
            "reason": "Risk posture elevated during emergency window"
        }
        rej_res = self.client.post(f"/api/v1/jobs/{job_id}/reject", json=reject_payload)
        self.assertEqual(rej_res.status_code, 200)
        rej_job = rej_res.json()
        self.assertEqual(rej_job["status"], "REJECTED")
        self.assertEqual(rej_job["approver_id"], "lead.bob")

    def test_websocket_hub_event_format(self):
        """ws_hub.publish produces { seq, type, data: { line, ... }, timestamp } conforming to WsEvent."""
        test_corr_id = "EXEC-TEST-WS-01"
        ws_hub.emit_log(test_corr_id, "Test stdout line 1")
        ws_hub.publish(test_corr_id, "status", {"status": "RUNNING", "message": "Worker running"})
        ws_hub.publish(test_corr_id, "diagnostic", {"root_cause": "Test failure root cause"})

        buf = ws_hub.buffers[test_corr_id]
        self.assertEqual(len(buf), 3)

        # Event 1: stdout
        self.assertEqual(buf[0]["seq"], 1)
        self.assertEqual(buf[0]["type"], "stdout")
        self.assertIn("line", buf[0]["data"])
        self.assertEqual(buf[0]["data"]["line"], "Test stdout line 1")

        # Event 2: status
        self.assertEqual(buf[1]["seq"], 2)
        self.assertEqual(buf[1]["type"], "status")
        self.assertEqual(buf[1]["data"]["status"], "RUNNING")

        # Event 3: diagnostic
        self.assertEqual(buf[2]["seq"], 3)
        self.assertEqual(buf[2]["type"], "diagnostic")
        self.assertEqual(buf[2]["data"]["root_cause"], "Test failure root cause")


if __name__ == "__main__":
    unittest.main()
