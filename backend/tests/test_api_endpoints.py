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

        # 2b. RBAC Unauthorized Checker Verification (Unprivileged user lacks Permission.JOB_APPROVE)
        unauth_payload = {
            "approver_id": "operator.charlie",
            "decision": "APPROVE",
            "reason": "Unprivileged approval attempt"
        }
        unauth_res = self.client.post(f"/api/v1/jobs/{corr_id}/approve", json=unauth_payload)
        self.assertEqual(unauth_res.status_code, 403)
        self.assertIn("RBAC Policy Violation", unauth_res.json()["detail"])

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
        for _ in range(30):
            time.sleep(0.1)
            get_res = self.client.get(f"/api/v1/jobs/{corr_id}")
            if get_res.status_code == 200 and get_res.json().get("status") == "SUCCESS":
                break

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

    def test_chat_intent_endpoint(self):
        """POST /api/v1/chat/intent maps free-text to catalog item and parameters."""
        res = self.client.post("/api/v1/chat/intent", json={"prompt": "Renew SSL cert on f5-edge-01.internal for 90 days"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["matched"])
        self.assertEqual(data["identifier"], "net-f5-cert-renew")
        self.assertEqual(data["engine"], "ansible")
        self.assertIn("hostname", data["suggested_parameters"])

    def test_high_filtered_tasks_endpoint(self):
        """GET /api/v1/tasks supports filtering by engine, status, environment, and search."""
        # 1. Base list
        res = self.client.get("/api/v1/tasks")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data["total_count"], 10)
        self.assertIn("counts_by_status", data)
        self.assertIn("counts_by_engine", data)

        # 2. Filter by engine=terraform
        res_tf = self.client.get("/api/v1/tasks?engine=terraform")
        self.assertEqual(res_tf.status_code, 200)
        for t in res_tf.json()["tasks"]:
            self.assertEqual(t["engine"], "terraform")

        # 3. Filter by status=SUCCESS
        res_succ = self.client.get("/api/v1/tasks?status=SUCCESS")
        self.assertEqual(res_succ.status_code, 200)
        for t in res_succ.json()["tasks"]:
            self.assertEqual(t["status"], "SUCCESS")

    def test_task_dispatch_and_logs(self):
        """POST /api/v1/tasks/dispatch dispatches run and GET /api/v1/tasks/{id}/logs returns logs."""
        payload = {
            "catalog_identifier": "cloud-s3-kms-bucket-provision",
            "target_resource_id": "analytics-bucket-test",
            "parameters": {"bucket_name": "analytics-bucket-test", "retention_days": 90},
            "environment": "UAT"
        }
        disp_res = self.client.post("/api/v1/tasks/dispatch", json=payload)
        self.assertEqual(disp_res.status_code, 200)
        disp_data = disp_res.json()
        corr_id = disp_data["correlation_id"]

        # Check logs
        time.sleep(0.5)
        logs_res = self.client.get(f"/api/v1/tasks/{corr_id}/logs")
        self.assertEqual(logs_res.status_code, 200)
        self.assertGreater(len(logs_res.json()["logs"]), 0)

    def test_create_job_missing_required_chg_returns_422(self):
        """POST /api/v1/jobs for a catalog item requiring CHG without CHG fails with 422."""
        payload = {
            "catalog_identifier": "net-f5-cert-renew",  # requires_chg = True
            "target_resource_id": "f5-edge-01.internal",
            "requester_id": "eng.charlie",
            "parameters": {
                "hostname": "f5-edge-01.internal",
                "vip_ip": "10.200.1.50",
                "cert_valid_days": 90
            },
            "servicenow_chg": None  # Missing CHG
        }
        res = self.client.post("/api/v1/jobs", json=payload)
        self.assertEqual(res.status_code, 422)
        self.assertIn("requires a valid ServiceNow Change Request", res.json()["detail"])

    def test_dispatch_task_requires_approval_when_catalog_item_declares_maker_checker(self):
        """POST /api/v1/tasks/dispatch with high-risk item routes to PENDING_APPROVAL."""
        payload = {
            "catalog_identifier": "net-f5-cert-renew",
            "target_resource_id": "f5-edge-01.internal",
            "requester_id": "eng.charlie",
            "parameters": {
                "hostname": "f5-edge-01.internal",
                "vip_ip": "10.200.1.50",
                "cert_valid_days": 90
            },
            "servicenow_chg": "CHG-991122"
        }
        res = self.client.post("/api/v1/tasks/dispatch", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["requires_approval"])
        self.assertEqual(data["status"], "PENDING_APPROVAL")

    def test_observability_probes_and_metrics(self):
        """Validates /healthz, /ready, and Prometheus /metrics endpoints."""
        # 1. Liveness
        res_live = self.client.get("/healthz")
        self.assertEqual(res_live.status_code, 200)
        self.assertEqual(res_live.json()["status"], "ALIVE")

        # 2. Readiness
        res_ready = self.client.get("/ready")
        self.assertEqual(res_ready.status_code, 200)
        self.assertEqual(res_ready.json()["status"], "READY")
        self.assertTrue(res_ready.json()["checks"]["catalog_loaded"])

        # 3. Prometheus Metrics
        res_metrics = self.client.get("/metrics")
        self.assertEqual(res_metrics.status_code, 200)
        text = res_metrics.text
        self.assertIn("vulcan_uptime_seconds", text)
        self.assertIn("vulcan_catalog_items_total", text)
        self.assertIn("vulcan_jobs_total", text)

    def test_consistent_error_envelope(self):
        """Validates consistent error envelope {error_code, message, correlation_id, details} on 404."""
        res = self.client.get("/api/v1/jobs/non-existent-job-999")
        self.assertEqual(res.status_code, 404)
        data = res.json()
        self.assertEqual(data["error_code"], "ERR_404")
        self.assertIn("Job not found", data["message"])
        self.assertIn("correlation_id", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
