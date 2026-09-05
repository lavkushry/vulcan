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

## Quick Start (Local Testbed)

```bash
# 1. Start Infrastructure (PostgreSQL 16 + pgvector, Redis, MinIO S3)
cd deploy && docker compose up -d

# 2. Start Backend Control Plane (FastAPI)
cd ../backend
pip install -r requirements.txt
python main.py

# 3. Start Frontend Web Console (Next.js 15)
cd ../frontend
npm install
npm run dev
```
