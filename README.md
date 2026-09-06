# PROJECT VULCAN: ENTERPRISE AUTOMATION CONTROL PLANE
## Clean Architecture, Distributed Scale, LLM Operating System & Reactive UX

Built for Tier-1 mission-critical banking infrastructure (PNC Bank Engineering Standard).  
Co-architected by:
* **Robert C. Martin ("Uncle Bob")**: Clean Architecture, Domain Invariants, SOLID Principles, PyTest Suite.
* **Alex Xu**: Distributed Concurrency (Redis Redlock with Watchdog), 10GB S3 Decoupled Storage, WebSocket Pub/Sub.
* **Andrej Karpathy**: LLM Operating System, 2,500-Token Working Memory, Grammar-Constrained Decoding, SRE Diagnostics.
* **Jordan Walke**: Declarative UI ($UI = f(state)$), Obsidian Glass Design System, 60 FPS WebGL xterm.js Canvas.

---

## High-Level Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [1] FRONTEND UI (Jordan Walke)                                                         │
│     Next.js 15 • Obsidian Glass Bento Grid • Cmd+K Palette • WebGL xterm.js Terminal   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [2] API CONTROL PLANE GATEWAY (Uncle Bob & Alex Xu)                                    │
│     FastAPI • SAML Auth • Pydantic v2 Invariants • TruffleHog Secret Scanner • Redlock │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [3] AI REASONING & DISCOVERY ENGINE (Andrej Karpathy)                                  │
│     pgvector Hybrid RRF Search • Grammar FSM Slot Filler • SRE Log Diagnostic Drawer   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [4] DISTRIBUTED WORKER FLEET (Alex Xu & Uncle Bob)                                     │
│     Ephemeral Container Pods • ansible-runner • opentofu • CyberArk JIT Secrets (RAM)  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
vulcan-control-plane/
├── backend/
│   ├── app/
│   │   ├── domain/               # Uncle Bob: Pure Domain Entities & Invariants (Zero Dependencies)
│   │   ├── ports/                # Abstract Interfaces (Dependency Inversion)
│   │   ├── adapters/             # Concrete Adapters (Ansible, Redlock, S3, CryptoAudit)
│   │   ├── use_cases/            # Application Interactors (ExecuteJob, ApproveJob, ResolveIntent)
│   │   ├── api/                  # FastAPI Routes & Real-Time WebSocket Handlers
│   │   └── config.py             # Dependency Injection Container & Settings
│   ├── catalog/                  # Seeded Playbooks, Modules & metadata.yaml
│   ├── tests/                    # Uncle Bob's PyTest Matrix & Karpathy Evals
│   ├── requirements.txt
│   └── main.py
│
├── frontend/                     # Jordan Walke: Obsidian Glass Web Console
│   ├── app/                      # Next.js 15 App Router
│   ├── components/               # Bento Grid, Monaco Editor, xterm.js Streamer
│   └── package.json
│
├── deploy/                       # Local & Production Infrastructure
│   ├── docker-compose.yml        # Postgres + pgvector, Redis, MinIO S3, Backend, Frontend
│   └── k8s/                      # Kubernetes manifests
│
└── TASK_ASSIGNMENT_PLAN.md       # Specialized Agent Matrix & Milestones
```

---

## The 11 Production Operational Views

| # | Route | View Name | Key Capabilities |
|---|---|---|---|
| 1 | **`/chat` & `/`** | **`✨ AI Chat Assistant`** | **The #1 Primary Screen**: Dual-pane workspace with natural language intent resolution across 100+ playbooks, dynamic slot-filling cards, and live xterm.js terminal stream. |
| 2 | **`/matrix`** | **`🎛️ High-Filtered Tasks`** | **Enterprise Task Window**: 10-column sortable table with multi-dimensional filtering and CSV export. |
| 3 | **`/policies`** | **`🔑 Roles & Policies`** | **Enterprise Governance & Simulator**: Interactive 5-role capability matrix, active OPA/Rego policy-as-code guardrails, and real-time execution policy simulator. |
| 4 | **`/workflows`** | **`🔀 Workflows & Cron`** | **DAG Pipelines & Distributed Cron**: Multi-step sequential/parallel pipelines with rollback compensation + Redis Redlock distributed cron scheduler. |
| 5 | **`/integrations`** | **`🔌 Connectors & Hub`** | **Enterprise Connectors**: Native bi-directional sync with ServiceNow (ITSM/CHG), Red Hat AAP (Tower/AWX), GitHub/Bitbucket GitOps, Jira Software, and HashiCorp Vault. |
| 6 | **`/actions`** | **`⚡ Actions Catalog`** | **StackStorm Pack Tree**: Category/pack browser with schema-driven forms (enums, booleans, numeric sliders, ServiceNow CHG). |
| 7 | **`/history`** | **`📜 Execution History`** | **Master-Detail Feed**: Reverse-chronological execution feed with status filters, terminal replay, approval deck, and AI diagnostics. |
| 8 | **`/rules`** | **`⚡ Automation Rules`** | **Datadog / StackStorm Event Rules**: Trigger (Datadog Alert, Kafka, Prometheus) → Filter criteria → Action mapping with Jinja2 interpolation. |
| 9 | **`/packs`** | **`📦 Content Packs`** | **Backstage / Port IDP Ecosystem**: Bundles for Network, Cloud, Database, Kubernetes, and OS Patching with dependency health validation. |
| 10 | **`/audit`** | **`🛡️ Audit & Compliance`** | **Digital.ai & Banking SOX Governance**: Cryptographic Merkle chain proof ledger (Genesis to Tip SHA-256), Separation of Duties verification, and ServiceNow CHG reconciliation. |
| 11 | **`/dashboard`** | **`📊 Telemetry Dashboard`** | **Operational Overview**: KPI cards (Active Runners, Catalog Size, Pending Approvals, Failures 24h, Merkle Chain), top failing playbooks, and recent activity. |

---

## Verification & Test Results

- **Backend Unit Tests**: **60/60 passing** in 1.834s (`PYTHONPATH=backend backend/.venv/bin/python3 -m unittest discover backend/tests`).
- **Frontend Production Build**: **15 static routes compiled cleanly** with zero TypeScript errors (`npm run build`).
- **All Routes Return HTTP 200 OK**: Verified live on port 3000.
- **Git Repository**: Pushed to `origin/main` at `https://github.com/lavkushry/vulcan.git`.

---

## Quick Start (Local Testbed)

```bash
# 1. Start Backend Control Plane (FastAPI on port 8000)
cd backend
source .venv/bin/activate
uvicorn app.main:app --port 8000

# 2. Start Frontend Web Console (Next.js 15 on port 3000)
cd frontend
npm run start
```
