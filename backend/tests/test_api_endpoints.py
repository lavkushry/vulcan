"""
Project Vulcan: API Presentation Layer Integration Tests
Author: Alex Xu & Uncle Bob
Verifies FastAPI REST endpoints, JSON serialization, Maker-Checker HTTP 403, and storage routes.
"""
import time
import unittest
from fastapi.testclient import TestClient

from app.api.server import app
from app.config import container


class TestAPIEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        """GET /api/v1/health returns 200 and valid audit chain."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "OPERATIONAL")
        self.assertTrue(data["audit_chain_valid"])
        self.assertGreaterEqual(data["catalog_size"], 4)

    def test_catalog_endpoint(self):
        """GET /api/v1/catalog returns all registered playbooks."""
        response = self.client.get("/api/v1/catalog")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertGreaterEqual(len(items), 4)
        identifiers = [item["identifier"] for item in items]
        self.assertIn("net-f5-cert-renew", identifiers)
        self.assertIn("db-expand-tablespace", identifiers)
        self.assertIn("cloud-vpc-peering", identifiers)
        self.assertIn("os-kernel-patch", identifiers)

    def test_intent_resolution_endpoint(self):
        """POST /api/v1/intent/resolve executes hybrid search and returns structured slots."""
        payload = {
            "prompt": "Renew SSL certificate for f5-edge-01.pnc.com on VIP 10.200.1.50 with validity 90 days"
        }
        response = self.client.post("/api/v1/intent/resolve", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "READY")
        self.assertEqual(data["playbook_identifier"], "net-f5-cert-renew")
        self.assertEqual(data["parameters"]["vip_ip"], "10.200.1.50")

    def test_e2e_job_submission_approval_and_execution_lifecycle(self):
        """Full lifecycle: Submit -> Maker-Checker Approval -> Execution -> Success."""
        # 1. Submit High-Risk Job
        submit_payload = {
            "catalog_identifier": "net-f5-cert-renew",
            "target_resource_id": "f5-vip-api-01",
            "requester_id": "engineer.alice",
            "parameters": {
                "hostname": "f5-edge-01.pnc.com",
                "vip_ip": "10.200.1.50",
                "cert_valid_days": 90
            },
            "servicenow_chg": "CHG001"
        }
        res = self.client.post("/api/v1/jobs", json=submit_payload)
        self.assertEqual(res.status_code, 200)
        job_data = res.json()
        corr_id = job_data["correlation_id"]
        self.assertEqual(job_data["status"], "PENDING_APPROVAL")

        # 2. Maker-Checker Anti-Self-Approval Verification (Alice cannot approve Alice)
        self_approval_payload = {
            "approver_id": "engineer.alice",
            "decision": "APPROVE",
            "reason": "Self-approval test"
        }
        self_res = self.client.post(f"/api/v1/jobs/{corr_id}/approve", json=self_approval_payload)
        self.assertEqual(self_res.status_code, 403)
        self.assertIn("Separation of Duties Violation", self_res.json()["detail"])

        # 3. Checker Signs Off (Bob approves Alice)
        bob_approval_payload = {
            "approver_id": "lead.bob",
            "decision": "APPROVE",
            "reason": "Authorized change review"
        }
        appr_res = self.client.post(f"/api/v1/jobs/{corr_id}/approve", json=bob_approval_payload)
        self.assertEqual(appr_res.status_code, 200)
        self.assertEqual(appr_res.json()["status"], "QUEUED")

        # 4. Trigger Execution
        exec_res = self.client.post(f"/api/v1/jobs/{corr_id}/execute")
        self.assertEqual(exec_res.status_code, 200)

        # Allow background thread worker to complete
        time.sleep(0.5)

        # 5. Verify Job Finished Successfully
        get_res = self.client.get(f"/api/v1/jobs/{corr_id}")
        self.assertEqual(get_res.status_code, 200)
        final_job = get_res.json()
        self.assertEqual(final_job["status"], "SUCCESS")
        self.assertEqual(final_job["exit_code"], 0)

    def test_s3_multipart_endpoints(self):
        """Test multipart initiate and complete endpoints."""
        init_payload = {
            "file_name": "rhel-9-hardened.iso",
            "file_size_bytes": 10737418240,  # 10 GB
            "sha256_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "job_id": "JOB-9901"
        }
        init_res = self.client.post("/api/v1/storage/multipart/initiate", json=init_payload)
        self.assertEqual(init_res.status_code, 200)
        data = init_res.json()
        self.assertEqual(data["total_parts"], 205)

        complete_payload = {
            "upload_id": data["upload_id"],
            "s3_key": data["s3_key"],
            "parts": [{"part_number": 1, "etag": "etag-chunk-1"}]
        }
        comp_res = self.client.post("/api/v1/storage/multipart/complete", json=complete_payload)
        self.assertEqual(comp_res.status_code, 200)
        self.assertEqual(comp_res.json()["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
