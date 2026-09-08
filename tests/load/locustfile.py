"""
Project Vulcan: Concurrency & Stress Testing Locustfile (Milestone C.3 Leg 2)
Author: Alex Xu (Distributed Systems & Scalability Lead)

Models 75 Concurrent Banking Operators, Leads, WebSockets, & Monitors:
1. OperatorUser: Resolves AI intents, submits jobs, tracks execution status.
2. LeadApproverUser: Sweeps pending approvals, approves dual-control Maker-Checker gates, triggers execution.
3. WebSocketTerminalUser: Connects to live job streams, measures handshake and stream event delivery latency.
4. AuditorMonitorUser: Health probes, catalog browsing, audit log inspection.
"""
import json
import os
import random
import time
import urllib.request
import uuid
import websocket
from locust import HttpUser, User, task, between, tag, events

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

# Shared correlation ID pool for WebSocket streaming subscribers
ACTIVE_JOBS = []

# Dynamic token resolution from environment (supports both local side-cluster & VM tokens)
OP_TOKEN = os.environ.get("VULCAN_LOAD_OP_TOKEN", "token-loadtest-op")
LEAD_TOKEN = os.environ.get("VULCAN_LOAD_LEAD_TOKEN", "token-loadtest-lead")
AUDITOR_TOKEN = os.environ.get("VULCAN_LOAD_AUDITOR_TOKEN", "token-loadtest-auditor")

try:
    tokens_json = os.environ.get("VULCAN_API_TOKENS")
    if tokens_json:
        tokens_map = json.loads(tokens_json)
        for t, u in tokens_map.items():
            if u == "eng.alice":
                OP_TOKEN = t
            elif u == "lead.bob":
                LEAD_TOKEN = t
            elif u in ("admin.dave", "sec.carol", "e2e.bot"):
                AUDITOR_TOKEN = t
except Exception:
    pass


class OperatorUser(HttpUser):
    """Simulates active operators submitting automation requests."""
    weight = 3
    wait_time = between(0.1, 0.4)

    def on_start(self):
        self.user_id = f"operator-{uuid.uuid4().hex[:6]}"
        self.client.headers.update({
            "Authorization": f"Bearer {OP_TOKEN}",
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
                    ACTIVE_JOBS.append(corr_id)
                    if len(ACTIVE_JOBS) > 100:
                        del ACTIVE_JOBS[0]
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
    """Simulates team leads reviewing, approving Maker-Checker gates, and triggering execution."""
    weight = 2
    wait_time = between(0.2, 0.6)

    def on_start(self):
        self.approver_id = "lead.bob"
        self.client.headers.update({
            "Authorization": f"Bearer {LEAD_TOKEN}",
            "X-Vulcan-User": self.approver_id
        })

    @task(2)
    @tag("approval")
    def sweep_and_approve_pending(self):
        with self.client.get("/api/v1/jobs?status=PENDING_APPROVAL&limit=10", name="/api/v1/jobs?status=PENDING_APPROVAL", catch_response=True) as resp:
            if resp.status_code == 200:
                jobs = resp.json()
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
                                if app_resp.status_code == 200:
                                    ACTIVE_JOBS.append(corr_id)
                                    # Trigger execution to generate live streaming log events
                                    self.client.post(
                                        f"/api/v1/jobs/{corr_id}/execute",
                                        json={},
                                        name="/api/v1/jobs/{id}/execute",
                                        catch_response=True
                                    )
                            else:
                                app_resp.failure(f"Approval failed with {app_resp.status_code}")
                resp.success()
            else:
                resp.failure(f"Failed to query pending approvals: {resp.status_code}")


class WebSocketTerminalUser(User):
    """
    Simulates real-time operator consoles and terminal monitoring dashboards.
    Connects to live job WebSocket streams via Redis backplane and measures:
    1. WS Handshake Latency (/api/v1/ws/jobs/{id} [CONNECT])
    2. Event Delivery & Stream Throughput (/api/v1/ws/jobs/{id} [LINE_RECV])
    3. Stream Lines/Sec fanout throughput
    """
    weight = 2
    wait_time = between(0.2, 0.6)

    def on_start(self):
        self.ws_host = self.environment.host.replace("http://", "ws://").replace("https://", "wss://")
        self.user_id = f"ws-monitor-{uuid.uuid4().hex[:6]}"

    @task
    def stream_job_terminal(self):
        corr_id = None
        if ACTIVE_JOBS:
            corr_id = random.choice(ACTIVE_JOBS)
        else:
            # Fallback to polling recently created jobs
            try:
                req = urllib.request.Request(
                    f"{self.environment.host}/api/v1/jobs?limit=5",
                    headers={"Authorization": f"Bearer {AUDITOR_TOKEN}"}
                )
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    items = data if isinstance(data, list) else data.get("items", [])
                    if items:
                        corr_id = random.choice(items).get("correlation_id")
            except Exception:
                pass

        if not corr_id:
            corr_id = "VULCAN-WS-MONITOR-001"

        ws_url = f"{self.ws_host}/api/v1/ws/jobs/{corr_id}?token={AUDITOR_TOKEN}"

        # 1. Measure Handshake Latency
        t0 = time.time()
        ws = None
        try:
            ws = websocket.create_connection(ws_url, timeout=3.0)
            connect_latency = (time.time() - t0) * 1000.0
            self.environment.events.request.fire(
                request_type="WS",
                name="/api/v1/ws/jobs/{id} [CONNECT]",
                response_time=connect_latency,
                response_length=0,
                exception=None,
                context=None,
            )
        except Exception as e:
            connect_latency = (time.time() - t0) * 1000.0
            self.environment.events.request.fire(
                request_type="WS",
                name="/api/v1/ws/jobs/{id} [CONNECT]",
                response_time=connect_latency,
                response_length=0,
                exception=e,
                context=None,
            )
            return

        # 2. Read streaming lines (up to 20 lines or 2 seconds)
        lines_read = 0
        t_stream_start = time.time()
        try:
            ws.settimeout(1.0)
            while lines_read < 20 and (time.time() - t_stream_start < 2.0):
                t_msg_start = time.time()
                try:
                    msg = ws.recv()
                    t_msg_end = time.time()
                    lines_read += 1
                    msg_latency = max(0.1, (t_msg_end - t_msg_start) * 1000.0)
                    self.environment.events.request.fire(
                        request_type="WS",
                        name="/api/v1/ws/jobs/{id} [STREAM_LINE]",
                        response_time=msg_latency,
                        response_length=len(msg) if msg else 0,
                        exception=None,
                        context=None,
                    )
                except (websocket.WebSocketTimeoutException, TimeoutError):
                    break
        except Exception as e:
            self.environment.events.request.fire(
                request_type="WS",
                name="/api/v1/ws/jobs/{id} [STREAM_LINE]",
                response_time=0,
                response_length=0,
                exception=e,
                context=None,
            )
        finally:
            try:
                ws.close()
            except Exception:
                pass


class AuditorMonitorUser(HttpUser):
    """Simulates monitoring agents, audit scrapers, and console dashboards."""
    weight = 1
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.client.headers.update({
            "Authorization": f"Bearer {AUDITOR_TOKEN}",
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
