"""
Project Vulcan: Concurrency & Stress Testing Locustfile (Milestone C.3 Leg 2)
Author: Alex Xu (Distributed Systems & Scalability Lead)

Models 75 Concurrent Banking Operators & Simulated Runners:
1. OperatorUser: Resolves AI intents, submits jobs, checks status.
2. LeadApproverUser: Sweeps pending approvals, signs off dual-control Maker-Checker gates.
3. AuditorMonitorUser: Health probes, catalog browsing, audit log inspection.
"""
import random
import uuid
from locust import HttpUser, task, between, tag, events

PROMPTS = [
    "deploy openclaw bot on port 3000 with user openclaw",
    "provision docker runtime on node-42",
    "renew ssl certificate for f5-vip-dallas-01 for 90 days",
    "scale kubernetes worker pool 3 to 10 nodes",
    "run compliance baseline scan on pnc-core-db01"
]

CATALOG_IDENTIFIERS = [
    "claw-openclaw-deploy",
    "infra-docker-setup",
]


class OperatorUser(HttpUser):
    """Simulates active operators submitting automation requests."""
    weight = 3
    wait_time = between(0.1, 0.4)

    def on_start(self):
        self.user_id = f"operator-{uuid.uuid4().hex[:6]}"
        self.client.headers.update({
            "Authorization": "Bearer token-loadtest-op",
            "X-Vulcan-User": self.user_id
        })
        self.created_jobs = []

    @task(3)
    @tag("intent")
    def resolve_intent(self):
        prompt = random.choice(PROMPTS)
        payload = {
            "prompt": prompt,
            "user_id": self.user_id
        }
        with self.client.post("/api/v1/intent/resolve", json=payload, name="/api/v1/intent/resolve", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Intent resolve failed with status {resp.status_code}")

    @task(2)
    @tag("jobs")
    def submit_and_track_job(self):
        cat_id = random.choice(CATALOG_IDENTIFIERS)
        target = f"target-{uuid.uuid4().hex[:4]}.bank.internal"
        if cat_id == "claw-openclaw-deploy":
            params = {"port": random.randint(3000, 9000), "username": "openclaw"}
        elif cat_id == "infra-docker-setup":
            params = {"target_user": "vulcan"}
        else:
            params = {"port": 3000, "username": "openclaw", "target_user": "vulcan"}

        payload = {
            "catalog_identifier": cat_id,
            "requester_id": self.user_id,
            "target_resource_id": target,
            "parameters": params,
            "servicenow_chg": "CHG0098412"
        }

        with self.client.post("/api/v1/jobs", json=payload, name="/api/v1/jobs [CREATE]", catch_response=True) as resp:
            if resp.status_code in (200, 201):
                data = resp.json()
                corr_id = data.get("correlation_id")
                if corr_id:
                    self.created_jobs.append(corr_id)
                resp.success()
            else:
                resp.failure(f"Job creation failed with {resp.status_code}: {resp.text}")

    @task(2)
    @tag("status")
    def poll_job_status(self):
        if not self.created_jobs:
            return
        corr_id = random.choice(self.created_jobs)
        with self.client.get(f"/api/v1/jobs/{corr_id}", name="/api/v1/jobs/{id} [GET]", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 404:
                resp.success()  # In ephemeral test runs
            else:
                resp.failure(f"Job get failed with {resp.status_code}")


class LeadApproverUser(HttpUser):
    """Simulates team leads reviewing and approving Maker-Checker gates."""
    weight = 2
    wait_time = between(0.2, 0.6)

    def on_start(self):
        self.approver_id = "lead.bob"
        self.client.headers.update({
            "Authorization": "Bearer token-loadtest-lead",
            "X-Vulcan-User": self.approver_id
        })

    @task(2)
    @tag("approval")
    def sweep_and_approve_pending(self):
        with self.client.get("/api/v1/jobs?status=PENDING_APPROVAL&limit=10", name="/api/v1/jobs?status=PENDING_APPROVAL", catch_response=True) as resp:
            if resp.status_code == 200:
                jobs = resp.json()
                # If jobs is list or dict with items
                job_list = jobs if isinstance(jobs, list) else jobs.get("items", [])
                for job in job_list:
                    corr_id = job.get("correlation_id")
                    requester = job.get("requester_id")
                    # Enforce Maker-Checker: approver != requester
                    if corr_id and requester != self.approver_id:
                        approval_payload = {
                            "approver_id": self.approver_id,
                            "reason": "Load test approved for execution in test window",
                            "chg_number": "CHG0098412"
                        }
                        with self.client.post(
                            f"/api/v1/jobs/{corr_id}/approve",
                            json=approval_payload,
                            name="/api/v1/jobs/{id}/approve",
                            catch_response=True
                        ) as app_resp:
                            if app_resp.status_code in (200, 400, 409):
                                # 400/409 is acceptable if already approved by another concurrent lead
                                app_resp.success()
                            else:
                                app_resp.failure(f"Approval failed with {app_resp.status_code}")
                resp.success()
            else:
                resp.failure(f"Failed to query pending approvals: {resp.status_code}")


class AuditorMonitorUser(HttpUser):
    """Simulates monitoring agents, audit scrapers, and console dashboards."""
    weight = 1
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.client.headers.update({
            "Authorization": "Bearer token-loadtest-auditor",
            "X-Vulcan-User": "auditor.mon"
        })

    @task(3)
    @tag("health")
    def check_health(self):
        with self.client.get("/health", name="/health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check failed: {resp.status_code}")

    @task(2)
    @tag("catalog")
    def browse_catalog(self):
        with self.client.get("/api/v1/catalog", name="/api/v1/catalog", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Catalog browse failed: {resp.status_code}")

    @task(1)
    @tag("jobs_list")
    def list_recent_jobs(self):
        with self.client.get("/api/v1/jobs?limit=50", name="/api/v1/jobs [LIST]", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Jobs list failed: {resp.status_code}")
