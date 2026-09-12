# Project Vulcan: Complete User Guide (How to Use)

Welcome to **Project Vulcan**, the Enterprise Automation Control Plane built to Tier-1 banking standards (PNC Bank Engineering Baseline). This definitive operational guide covers every feature, screen, workflow, and API interaction available to operators, site reliability engineers (SREs), approvers, and compliance auditors.

---

## Table of Contents
1. [System Overview & Access](#1-system-overview--access)
2. [Screen-by-Screen Operator Workflows](#2-screen-by-screen-operator-workflows)
   - [2.1 AI Copilot & Intent Resolution (`/chat` or `/`)](#21-ai-copilot--intent-resolution-chat-or-)
   - [2.2 Universal Command Palette (Cmd + K)](#22-universal-command-palette-cmd--k)
   - [2.3 High-Filtered Task Matrix (`/matrix`)](#23-high-filtered-task-matrix-matrix)
   - [2.4 Maker-Checker Governance & Approvals (`/history` or `/chat`)](#24-maker-checker-governance--approvals-history-or-chat)
   - [2.5 Real-Time Terminal Streaming & Replay (xterm.js)](#25-real-time-terminal-streaming--replay-xtermjs)
   - [2.6 AI SRE Failure Diagnosis & Root Cause Drawer](#26-ai-sre-failure-diagnosis--root-cause-drawer)
   - [2.7 Human Feedback Reinforcement Loop (RLHF)](#27-human-feedback-reinforcement-loop-rlhf)
   - [2.8 Automation Actions Catalog (`/actions`)](#28-automation-actions-catalog-actions)
   - [2.9 Workflows, DAG Pipelines & Distributed Cron (`/workflows`)](#29-workflows-dag-pipelines--distributed-cron-workflows)
   - [2.10 Event-Driven Automation Rules (`/rules`)](#210-event-driven-automation-rules-rules)
   - [2.11 Content Packs Ecosystem (`/packs`)](#211-content-packs-ecosystem-packs)
   - [2.12 Roles, RBAC & Policy-as-Code Simulator (`/policies`)](#212-roles-rbac--policy-as-code-simulator-policies)
   - [2.13 Cryptographic Merkle Audit & Compliance Ledger (`/audit`)](#213-cryptographic-merkle-audit--compliance-ledger-audit)
   - [2.14 Enterprise Telemetry Dashboard (`/dashboard`)](#214-enterprise-telemetry-dashboard-dashboard)
   - [2.15 Enterprise Connectors Hub (`/integrations`)](#215-enterprise-connectors-hub-integrations)
3. [REST & WebSocket API Usage Recipes](#3-rest--websocket-api-usage-recipes)
   - [3.1 Authentication & Token Setup](#31-authentication--token-setup)
   - [3.2 Resolving Natural Language Intents](#32-resolving-natural-language-intents)
   - [3.3 Creating and Dispatching Jobs](#33-creating-and-dispatching-jobs)
   - [3.4 Maker-Checker Job Approvals & Rejections](#34-maker-checker-job-approvals--rejections)
   - [3.5 Real-Time Log Streaming via WebSocket](#35-real-time-log-streaming-via-websocket)
   - [3.6 Submitting Human Feedback & RLHF Dataset Export](#36-submitting-human-feedback--rlhf-dataset-export)
4. [Operator Best Practices & Safety Guardrails](#4-operator-best-practices--safety-guardrails)

---

## 1. System Overview & Access

Project Vulcan is accessed via standard web browsers or programmatic REST/WebSocket clients:

* **Web Console:** `http://<VULCAN_HOST>:3000` (e.g. `http://141.148.195.233:3000` or `http://localhost:3000`)
* **REST & WebSocket API Gateway:** `http://<VULCAN_HOST>:8000`
* **Object Storage / S3 Console:** `http://<VULCAN_HOST>:9001` (Data API on `:9000`)

### Authentication
Every request to the API or web console is authenticated via Bearer tokens matching the server's configured `VULCAN_API_TOKENS`. In the web console, paste your assigned API token in the top navigation bar or settings drawer. The token is securely stored in browser `localStorage` under `vulcan_api_token`.

---

## 2. Screen-by-Screen Operator Workflows

### 2.1 AI Copilot & Intent Resolution (`/chat` or `/`)
The **AI Chat Assistant** is the flagship conversational workspace. It converts natural language infrastructure operations into strictly typed, governed execution plans without ever hallucinating or guessing parameters.

```
┌───────────────────────────────────────┬──────────────────────────────────────────┐
│ Left Pane: Natural Language Chat      │ Right Pane: Dual-Mode Mission Control    │
│                                       │                                          │
│ Operator: "Renew SSL cert on          │ [Tab 1: Live Terminal]                   │
│            f5-edge-01 in prod"        │ 60 FPS WebGL xterm.js stdout/stderr      │
│                                       │ stream with pause-on-scroll              │
│ Assistant: Intent Matched             │                                          │
│ ┌───────────────────────────────────┐ │ [Tab 2: Diagnostic Drawer]              │
│ │ Playbook: security-ssl-renewal    │ │ Root cause analysis, failed task,       │
│ │ Host: f5-edge-01.bank.internal    │ │ automated remediation suggestions      │
│ │ Validity: [ 90 days ]             │                                          │
│ └───────────────────────────────────┘ │ [Approval Deck (Maker-Checker)]          │
│ [ Submit for Approval ]               │ Separation-of-Duties cryptographic card │
└───────────────────────────────────────┴──────────────────────────────────────────┘
```

#### Step-by-Step Operator Flow:
1. **Type a Prompt:** In the chat input box at the bottom, type your operational intent:
   * Example: `"Restart nginx service on web-dmz-01"`
   * Example: `"Provision AWS VPC in us-east-1 for staging environment"`
   * Example: `"Renew SSL cert on f5-edge-01.bank.internal for 90 days"`
2. **Intent Resolution & Disambiguation:**
   * **Exact / High Confidence Match (`READY`):** A pre-filled slot card appears with extracted parameters.
   * **Ambiguous Intent (`NEEDS_INPUT`):** The copilot displays a Disambiguation Bento Card with multiple candidate playbooks and interactive parameter pills (`[DEV]`, `[UAT]`, `[PROD]`). Select the intended target.
   * **Out-of-Scope / Malicious Request (`REJECTED`):** If the prompt attempts prompt injection or requests an action outside the 100+ vetted enterprise playbooks, a refusal banner is rendered citing the exact safety gate triggered.
3. **Submit Plan:** Click **Submit Job** or press `Cmd + Enter`. The job enters the deterministic state machine (`DRAFT` → `PENDING_APPROVAL`).

---

### 2.2 Universal Command Palette (Cmd + K)
Press **`Cmd + K`** (or `Ctrl + K` on Linux/Windows) from any screen to open the Universal Command Palette:
* **Dynamic Search:** Fuzzy searches live across all playbooks, actions, and recent jobs.
* **Instant Keyboard Navigation:** Use `↑` and `↓` arrow keys to navigate, and press `Enter` to open or execute.
* **Quick Route Jumps:** Jump directly to Audit, History, Matrix, Policies, or Workflows without touching the mouse.

---

### 2.3 High-Filtered Task Matrix (`/matrix`)
The **Task Matrix** is an enterprise-grade operational table designed to inspect hundreds of concurrent or historical jobs:
* **10-Column Sorting:** Sort by Correlation ID, Playbook, Requester, Approver, Risk Tier (`TIER_1` to `TIER_3`), Status, Start Time, and Duration.
* **Multi-Dimensional Facet Filtering:** Filter simultaneously by Risk Tier, Execution Status (`PENDING_APPROVAL`, `RUNNING`, `COMPLETED`, `FAILED`), and Environment (`PROD`, `STAGE`, `DEV`).
* **Virtualized Row Windowing:** Automatically virtualizes DOM rows to maintain 60 FPS scrolling even with 10,000+ jobs loaded.
* **CSV Export:** Click the **Export CSV** button in the header to download a compliance-ready report of all filtered jobs.

---

### 2.4 Maker-Checker Governance & Approvals (`/history` or `/chat`)
In banking-grade environments, **no operator may approve their own job**. Project Vulcan strictly enforces this invariant mathematically:

```
Requester: alice.operator  ───► Submits Job (TIER_1) ───► Status: PENDING_APPROVAL
                                                                 │
                                ┌────────────────────────────────┴────────────────────────────────┐
                                ▼                                                                 ▼
               alice.operator attempts approval                                   bob.lead reviews and approves
               [ Approve Button: DISABLED ]                                       [ Approve Button: ACTIVE ]
               HTTP 403: Requester cannot approve own job                         HTTP 200: Transition to QUEUED
```

#### Approving a Job:
1. Navigate to the job via `/history` or click the job card in `/chat`.
2. Inspect the **Separation of Duties Proof Card**:
   * Review the target infrastructure (`host_target`, `environment`).
   * Review exact execution parameters and associated ServiceNow Change Request (`CHG0098231`).
3. If you are **not** the requester and hold the `APPROVER` or `ADMIN` role:
   * Click **Approve Execution** to dispatch the runner.
   * Click **Reject Execution** with an optional reason to cancel the job permanently.
4. **Approval Deadlines:** High-risk jobs have fail-closed timeout windows (e.g., 15 minutes). If unapproved within the deadline, the Distributed Approval Sweeper automatically cancels the job to prevent stale execution.

---

### 2.5 Real-Time Terminal Streaming & Replay (xterm.js)
The **Terminal** provides a 60 FPS hardware-accelerated (WebGL) console view:
* **Live Streaming:** As Ansible or Terraform executes inside the isolated sandbox pod, stdout/stderr is streamed line-by-line over WebSocket with sub-50ms latency.
* **Smart Pause-on-Scroll:** When you scroll up to inspect earlier logs, auto-scrolling automatically pauses and a floating **Scroll to Bottom** button appears.
* **ANSI Color Support:** Full rendering of colored diffs, warnings, errors, and task headers.
* **Terminal Action Bar:**
  * **Search (`Ctrl + F`):** Highlights occurrences inside the log buffer.
  * **Copy Clean Text:** Strips ANSI escape sequences and copies clean plain-text logs to the clipboard.
  * **Clear:** Clears current viewport display without truncating the backend buffer.

---

### 2.6 AI SRE Failure Diagnosis & Root Cause Drawer
When a job fails (exit code $\ne 0$, syntax error, network timeout, or post-flight health probe failure):
1. The **AI SRE Diagnostic Drawer** automatically slides open in the right pane.
2. The engine analyzes a strict 50-line window around the exact failure point.
3. Within $<3$ seconds, it renders:
   * **Root Cause Classification:** (e.g., `AuthenticationFailure`, `DiskSpaceExhausted`, `SyntaxError`, `NetworkUnreachable`).
   * **Evidence Citation:** Exact line number and raw error output from the log.
   * **Suggested Remediation Playbook:** One-click recommendation to run a healing playbook (e.g., `system-disk-cleanup` or `network-dns-flush`).

---

### 2.7 Human Feedback Reinforcement Loop (RLHF)
Every assistant message and resolution card includes an operator reinforcement bar:

```
[ 👍 Accurate ]   [ 👎 Incorrect / Refusal ]   [ 🔄 Correct Playbook ▼ ]
```

* **Positive Reinforcement:** Click 👍 to mark the intent resolution as accurate. This records a positive training pair (`positive_reinforcement`) for model alignment.
* **Corrections:** If the copilot selected an incorrect playbook, click 👎 or select the correction dropdown:
  1. Select the intended playbook from the live catalog list.
  2. Enter a brief diagnostic comment (e.g., `"Should use system-restart-nginx rather than generic reboot"`).
  3. Click **Submit Correction**.
  4. The UI displays an optimistic `✓ RLHF Dataset Updated` badge.
* **Exporting Training Sets:** SRE leads and ML engineers can export the accumulated DPO/KTO/SFT preference dataset directly via the API (`GET /api/v1/chat/feedback/export-rlhf`).

---

### 2.8 Automation Actions Catalog (`/actions`)
Browse all 100+ vetted Ansible playbooks and Terraform modules structured by pack:
* Filter by Category (`Operating System`, `Network`, `Cloud`, `Database`, `Security`).
* Inspect parameter schemas, default values, and risk tier assignments.
* Click **Run Action** to open a schema-validated execution modal with sliders, boolean toggles, and ServiceNow ticket validators.

---

### 2.9 Workflows, DAG Pipelines & Distributed Cron (`/workflows`)
* **Multi-Step DAGs:** Chain multiple playbooks into sequential or parallel execution graphs with conditional branching and automated rollback compensation steps.
* **Distributed Cron Engine:** Schedule recurring automation jobs backed by Redis Redlock leader election to guarantee single execution across multi-worker clusters.
* Inspect upcoming cron trigger times, active lease holders, and historical workflow execution graphs.

---

### 2.10 Event-Driven Automation Rules (`/rules`)
Configure automated incident remediation:
* **Trigger Sources:** Datadog Webhooks, Prometheus Alerts, Kafka Topics, or ServiceNow Incidents.
* **Criteria Filters:** Match alerts based on severity (`CRITICAL`), service name (`f5-edge`), or region.
* **Action Bindings:** Automatically dispatch remediation playbooks (e.g., scale up ECS tasks, restart failed service, clear temporary cache) with Jinja2 payload interpolation.

---

### 2.11 Content Packs Ecosystem (`/packs`)
Manage modular automation bundles:
* Inspect installed packs: `core-network`, `cloud-aws`, `database-oracle`, `compliance-sox`.
* Check dependency health, semantic versions (`v1.4.0`), and playbook counts.
* Ingest new community or internal Git repositories into the catalog.

---

### 2.12 Roles, RBAC & Policy-as-Code Simulator (`/policies`)
* **Role Capability Matrix:** Compare permissions across `OPERATOR`, `APPROVER`, `AUDITOR`, `SRE_ADMIN`, and `SECURITY_LEAD`.
* **OPA / Rego Guardrails:** View active enterprise policies (e.g., No Production deployments after 18:00 EST, Multi-region replication required for Tier-1 databases).
* **Execution Simulator:** Test hypothetical requests against policy rules to preview whether a proposed execution would be `PERMITTED`, `REQUIRES_CAB`, or `DENIED`.

---

### 2.13 Cryptographic Merkle Audit & Compliance Ledger (`/audit`)
Designed for FDIC, SOX 404, and external compliance auditors:
* **Genesis-to-Tip SHA-256 Hash Chain:** Every state change, execution start, approval, and probe verification is cryptographically chained to the previous record (`current_hash = SHA256(prev_hash + payload)`).
* **Tamper-Evidence Verification:** Click **Verify Chain Integrity**. If any row in the PostgreSQL ledger is manually modified, the Merkle chain breaks immediately, pin-pointing the exact tampered sequence number.
* **ServiceNow Reconciliation:** Verify that every production execution corresponds to an approved ServiceNow `CHG` ticket.

---

### 2.14 Enterprise Telemetry Dashboard (`/dashboard`)
Operational bird's-eye view:
* **Key Metrics:** Active Runners (capacity out of 75), Catalog Size, Pending Approvals, 24-Hour Failure Rate, and Merkle Ledger Tip.
* **RED Telemetry HUD:** Real-time monitoring of Request Rate, Error Rate, and Duration across the FastAPI backend.
* **Recent Activity Feed:** Live ticker of dispatched jobs and approval decisions.

---

### 2.15 Enterprise Connectors Hub (`/integrations`)
Check the real-time health and synchronization state of enterprise third-party integrations:
* **ServiceNow:** Bi-directional Table API sync for Change Requests and CMDB Configuration Items.
* **Red Hat AAP / Tower:** External Ansible execution cluster connectivity.
* **CyberArk / Vault:** Ephemeral Just-In-Time (JIT) credential injection.
* **GitHub / GitLab:** GitOps playbook synchronization.

---

## 3. REST & WebSocket API Usage Recipes

All endpoints require authentication via Bearer token in the `Authorization` header.

### 3.1 Authentication & Token Setup

```bash
# Define your Vulcan host and assigned API token
export VULCAN_URL="http://141.148.195.233:8000"
export VULCAN_TOKEN="vlc_adm_9f82k3...YourTokenHere"

# Verify connectivity & health
curl -s "${VULCAN_URL}/healthz" | jq .
```

Response:
```json
{
  "status": "ALIVE",
  "timestamp": "2026-09-12T11:27:22.230636+00:00",
  "uptime_seconds": 124.5
}
```

---

### 3.2 Resolving Natural Language Intents

```bash
curl -s -X POST "${VULCAN_URL}/api/v1/intent/resolve" \
  -H "Authorization: Bearer ${VULCAN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Renew SSL certificate on f5-edge-01.bank.internal in prod for 90 days"
  }' | jq .
```

Response:
```json
{
  "status": "READY",
  "catalog_item": {
    "identifier": "security-ssl-cert-renewal",
    "name": "F5 BIG-IP SSL Certificate Renewal",
    "risk_tier": "TIER_2"
  },
  "extracted_parameters": {
    "host_target": "f5-edge-01.bank.internal",
    "validity_days": 90,
    "environment": "prod"
  },
  "missing_parameters": [],
  "tokens_used": 642,
  "latency_ms": 112.4
}
```

---

### 3.3 Creating and Dispatching Jobs

```bash
# 1. Create the Job
JOB_RESPONSE=$(curl -s -X POST "${VULCAN_URL}/api/v1/jobs" \
  -H "Authorization: Bearer ${VULCAN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "security-ssl-cert-renewal",
    "parameters": {
      "host_target": "f5-edge-01.bank.internal",
      "validity_days": 90
    },
    "requester_id": "alice.operator",
    "servicenow_chg": "CHG0098231"
  }')

JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.correlation_id')
echo "Created Job ID: $JOB_ID"
```

---

### 3.4 Maker-Checker Job Approvals & Rejections

```bash
# Approve Job (Must be called with a token belonging to an approver other than alice.operator)
curl -s -X POST "${VULCAN_URL}/api/v1/jobs/${JOB_ID}/approve" \
  -H "Authorization: Bearer ${APPROVER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "approver_id": "bob.lead",
    "notes": "Verified against Change Window CHG0098231. Approved for execution."
  }' | jq .
```

Response:
```json
{
  "status": "SUCCESS",
  "job_id": "EXEC-98AF23D1",
  "new_state": "APPROVED",
  "approver_id": "bob.lead"
}
```

---

### 3.5 Real-Time Log Streaming via WebSocket

Connect to the WebSocket event stream using Python or any WebSocket client:

```python
import asyncio
import json
import websockets

async def stream_job_logs(job_id: str, token: str):
    uri = f"ws://141.148.195.233:8000/api/v1/ws/jobs/{job_id}?token={token}"
    async with websockets.connect(uri) as ws:
        print(f"Connected to stream for {job_id}...")
        async for message in ws:
            event = json.loads(message)
            if event["type"] == "stdout":
                print(f"[{event['seq']}] {event['line']}", end="")
            elif event["type"] == "status_change":
                print(f"\n>>> Status Changed: {event['old_status']} -> {event['new_status']}")
            elif event["type"] == "completed":
                print(f"\n>>> Job Finished with status: {event['status']}")
                break

asyncio.run(stream_job_logs("EXEC-98AF23D1", "vlc_adm_..."))
```

---

### 3.6 Submitting Human Feedback & RLHF Dataset Export

#### Record Operator Correction:
```bash
curl -s -X POST "${VULCAN_URL}/api/v1/chat/feedback" \
  -H "Authorization: Bearer ${VULCAN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Restart web proxy",
    "resolved_identifier": "system-restart-server",
    "rating": "corrected",
    "correction_identifier": "system-restart-nginx",
    "comment": "Route to nginx service restart rather than server reboot"
  }' | jq .
```

#### Export RLHF DPO Preference Dataset:
```bash
curl -s "${VULCAN_URL}/api/v1/chat/feedback/export-rlhf" \
  -H "Authorization: Bearer ${VULCAN_TOKEN}" | jq .
```

Response:
```json
{
  "dataset_size": 240,
  "dataset": [
    {
      "prompt": "Restart web proxy",
      "chosen": "system-restart-nginx",
      "rejected": "system-restart-server",
      "type": "pairwise_preference",
      "rating": "corrected"
    },
    {
      "prompt": "Renew SSL cert on f5-edge-01",
      "chosen": "security-ssl-cert-renewal",
      "rejected": null,
      "type": "positive_reinforcement",
      "rating": "thumbs_up"
    }
  ]
}
```

---

## 4. Operator Best Practices & Safety Guardrails

1. **Verify Change Request Numbers:** For `TIER_1` (Production critical) actions, always supply a valid, CAB-approved ServiceNow Change Request ID (`CHG...`).
2. **Never Share Approver Tokens:** Maker-checker governance is verified both by caller identity and token signature. Attempting to approve your own job triggers an irreversible audit violation alert.
3. **Respect Active Maintenance Windows:** Production targets enforce active maintenance schedule locks. Out-of-window attempts will be blocked by pre-flight validation.
4. **Use Terminal Search for Large Outputs:** When troubleshooting playbook executions with $>1,000$ lines, use `Ctrl + F` inside xterm.js or the Diagnostic Drawer to isolate root causes instantly.
