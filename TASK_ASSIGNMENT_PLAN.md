# PROJECT VULCAN: SPECIALIZED AGENT TASK ASSIGNMENT & IN-DEPTH EXECUTION PLAN

This document establishes the official task allocation, architectural boundaries, and verification criteria for each specialized agent.

---

## 1. Specialized Agent Roster & Responsibility Matrix

| Specialized Agent | Persona & Discipline | Assigned Domain & Primary Modules | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Agent 1: `uncle_bob_architect`** | **Robert C. Martin ("Uncle Bob")**<br>*Clean Architecture & Domain Rules* | `backend/app/domain/`<br>`backend/app/ports/`<br>`backend/app/use_cases/`<br>`backend/tests/test_domain_invariants.py` | • Pure Python standard library (Zero framework imports in domain).<br>• Maker-Checker hard inequality (`requester != approver`).<br>• `BaseJobRunner` Template Method enforcing immutable safety lifecycle.<br>• 18/18 PyTest tests passing in $<0.01\text{s}$. |
| **Agent 2: `alex_xu_systems`** | **Alex Xu**<br>*Distributed Systems & Scalability* | `backend/app/adapters/redlock_adapter.py`<br>`backend/app/adapters/s3_multipart_adapter.py`<br>`backend/app/api/websockets.py`<br>`deploy/docker-compose.yml` | • 5-node Redis Redlock with background watchdog heartbeat (30s lease, 10s renewal).<br>• 10GB S3 presigned multipart chunking (50MB parts) isolating data from API RAM.<br>• Dual-write event backplane (Redis Pub/Sub + List ring buffer) solving Late-Joiner terminal issue.<br>• PostgreSQL 16 schema with HNSW cosine index. |
| **Agent 3: `andrej_karpathy_ai`** | **Andrej Karpathy**<br>*AI Systems & Tokenomics* | `backend/app/use_cases/resolve_intent.py`<br>`backend/app/use_cases/diagnose_failure.py`<br>`backend/catalog/`<br>`backend/tests/test_ai_evals.py` | • 2,500-token strict working memory budget (sub-1.5s latency).<br>• Two-stage hybrid RRF search (`pgvector` + BM25) over 1,000 playbooks bound to immutable Git SHAs.<br>• Grammar-constrained decoding: Pydantic FSM logit masks guaranteeing $P(\text{syntax error}) = 0$.<br>• Software 1.0 log windowing (50 lines) + SRE diagnostic engine in $<3\text{s}$.<br>• 500-scenario Golden Eval benchmark passing $\ge 99.2\%$ routing and $100\%$ refusal. |
| **Agent 4: `jordan_walke_frontend`** | **Jordan Walke**<br>*Declarative UI/UX & React Systems* | `frontend/app/`<br>`frontend/components/`<br>`frontend/tailwind.config.js`<br>`frontend/package.json` | • Declarative state machine: $UI = f(\text{state})$ with React 19 `useOptimistic`.<br>• Obsidian Glass design tokens (#07090E canvas, acrylic glass, neon telemetry).<br>• Adaptive Bento Canvas with dynamic slot-filling micro-cards and numbered pills.<br>• 60 FPS live WebGL-accelerated `xterm.js` terminal with ring buffer.<br>• Executive Maker-Checker deck with mathematically disabled anti-self-approval buttons. |

---

## 2. In-Depth Phase-by-Phase Execution Roadmap

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASES & TASK EXECUTION PIPELINE                                                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: CORE DOMAIN, PORTS & INVARIANTS (Lead: Uncle Bob)                             │
│ • Implement pure Python domain entities and custom domain exception hierarchy.         │
│ • Implement abstract ports (DIP interfaces).                                           │
│ • Implement BaseJobRunner Template Method.                                             │
│ • Execute 18/18 PyTest verification suite.                                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: DISTRIBUTED ADAPTERS, S3 10GB & CONCURRENCY (Lead: Alex Xu)                   │
│ • Implement Redis Redlock with background watchdog heartbeat thread.                   │
│ • Implement S3 presigned multipart chunked upload adapter (50MB chunks).               │
│ • Implement cryptographic SHA256 Merkle chain WORM audit adapter.                      │
│ • Implement official ansible-runner and high-fidelity simulation adapters.             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: AI REASONING SUBSYSTEM & CATALOG SEED (Lead: Andrej Karpathy)                 │
│ • Implement hybrid RRF vector search + Pydantic FSM grammar slot filler.               │
│ • Implement Software 1.0 bottom-up log windowing + fast SRE diagnostic engine.         │
│ • Seed 4 banking catalog playbooks with immutable commit SHAs & metadata.yaml.         │
│ • Execute 500-scenario Golden Eval benchmark harness.                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 4: FASTAPI CONTROL PLANE & WEBSOCKET EVENT HUB (Co-Leads: Uncle Bob & Alex Xu)   │
│ • Build FastAPI server, dependency injection container, and error mapping middleware.  │
│ • Build REST routes for intent resolution, job lifecycle, approvals, and S3 presigning.│
│ • Build dual-write Redis ring buffer WebSocket connection manager for xterm.js.        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 5: OBSIDIAN GLASS REACT 19 / NEXT.JS 15 FRONTEND (Lead: Jordan Walke)            │
│ • Configure Next.js 15 App Router, Tailwind CSS v4 tokens, and Geist typography.       │
│ • Build Bento Grid Dashboard, Universal Command Palette (Cmd + K).                     │
│ • Build WebGL xterm.js live terminal stream with real-time Telemetry HUD.              │
│ • Build Maker-Checker review deck with anti-self-approval protection.                  │
│ • Build slide-out AI SRE Diagnostic Drawer on execution failure.                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 6: END-TO-END VERIFICATION & CONCURRENCY STRESS TESTS (All 4 Leads)              │
│ • Run Uncle Bob's Invariant suite (Gate 1).                                            │
│ • Run Alex Xu's Redis Mutex collision tests (Gate 2).                                  │
│ • Run Karpathy's Golden Eval benchmark (Gate 3).                                       │
│ • Verify Jordan Walke's 60 FPS live terminal streaming & UI flows (Gate 4).           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 7: ENTERPRISE CONNECTORS HUB (Leads: Alex Xu & Uncle Bob)                        │
│ • Native bi-directional connectors: ServiceNow (ITSM/CHG), Red Hat AAP (Tower/AWX),   │
│   GitHub/Bitbucket GitOps, Jira Software, and HashiCorp Vault.                         │
│ • Connection health diagnostic test harness and catalog synchronization.               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 8: MULTI-STEP DAG WORKFLOWS & DISTRIBUTED CRON (Leads: Alex Xu & Uncle Bob)       │
│ • Orquesta/Airflow-style multi-step pipelines with automated failure rollback branches.│
│ • Distributed Cron Scheduler guarded by Redis Redlock distributed mutexes.             │
│ • ServiceNow maintenance window gating before scheduled job execution.                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 9: ENTERPRISE ROLES & POLICIES (RBAC/ABAC) (Leads: Uncle Bob & Jordan Walke)     │
│ • 5 Banking Roles: OPERATOR, APPROVING_LEAD, SECURITY_ADMIN, PLATFORM_ADMIN, AUDITOR.   │
│ • 6 Active Policy Guardrails (POL-001 to POL-006) with Rego/OPA code definitions.     │
│ • Interactive Policy Simulator in frontend (/policies) with live decision evaluation.  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component File Manifest

### Backend Directory (`vulcan-control-plane/backend/`)
* `app/domain/entities.py`: Pure Python dataclasses (`JobStatus`, `RiskTier`, `CatalogItem`, `ExecutionJob`, `AuditRecord`).
* `app/domain/roles_and_policies.py`: Enterprise RBAC roles, fine-grained permissions, and deterministic Policy-as-Code engine.
* `app/domain/exceptions.py`: Pure domain exceptions (`MakerCheckerViolationError`, `MaintenanceWindowClosedError`, etc.).
* `app/domain/invariants.py`: Invariant validation functions (regex, numeric bounds, secret linting).
* `app/ports/interfaces.py`: Abstract interfaces (`IExecutionEngine`, `ILockManager`, `IAuditLogger`, `ISecretProvider`, `IServiceNowGateway`, `IObjectStorageGateway`, `IHealthProbeGateway`).
* `app/adapters/policy_manager.py`: Policy evaluation manager, role definitions, and toggle state.
* `app/adapters/workflow_manager.py`: Multi-step DAG pipeline engine, rollback branching, and distributed cron manager.
* `app/adapters/integrations_manager.py`: Connectors for ServiceNow, AAP, GitHub, Jira, Vault, and Datadog.
* `app/adapters/redlock_adapter.py`: Redis Redlock with background watchdog heartbeat thread.
* `app/adapters/s3_multipart_adapter.py`: Direct S3 presigned multipart upload generator (50MB parts).
* `app/adapters/crypto_audit_adapter.py`: SHA256 Merkle chain immutable audit logger.
* `app/adapters/ansible_runner_adapter.py`: Official `ansible-runner` invocation with stdout event streaming.
* `app/adapters/simulation_adapter.py`: High-fidelity local simulator for realistic verification without external dependencies.
* `app/use_cases/runner.py`: The `BaseJobRunner` Template Method enforcing the immutable banking safety sequence.
* `app/use_cases/resolve_intent.py`: Hybrid vector search + grammar-constrained slot-filling.
* `app/use_cases/diagnose_failure.py`: Log windowing + fast AI root-cause extraction.
* `app/api/server.py`: FastAPI application assembly, lifespan, CORS, and error mapping middleware.
* `app/api/routes.py`: Complete RESTful API endpoints (Intent, Jobs, Governance, Integrations, Workflows, Policies).
* `app/api/websockets.py`: Dual-write Redis ring buffer WebSocket connection manager.
* `app/config.py`: Dependency injection container and configuration.
* `catalog/`: Seeded playbooks (`f5_ssl_renew.yml`, `db_expand_tablespace.yml`, `aws_vpc_peering.tf`, `rhel_patch.yml`) with `metadata.yaml`.
* `tests/test_domain_invariants.py`: Uncle Bob's 18-test PyTest suite.
* `tests/test_policy_engine.py`: Comprehensive test suite for 5 roles and 6 policy guardrails.
* `tests/test_workflow_manager.py`: Tests for DAG step transitions, rollback branches, and cron toggles.
* `tests/test_redlock_concurrency.py`: Alex Xu's concurrency & lock collision suite.
* `tests/test_ai_evals.py`: Andrej Karpathy's 500-scenario Golden Eval benchmark suite.
* `requirements.txt`: Pinned Python dependencies.
* `main.py`: Production entrypoint.

### Frontend Directory (`vulcan-control-plane/frontend/`)
* `app/layout.tsx`: Root Obsidian Glass layout with navigation rail and system pulse.
* `app/chat/page.tsx`: The #1 Primary Screen with NLP intent resolution and side-by-side terminal.
* `app/matrix/page.tsx`: 10-column high-filtered task matrix with sorting and CSV export.
* `app/policies/page.tsx`: Enterprise Roles & Policies Console with live Policy Simulator.
* `app/workflows/page.tsx`: Multi-step DAG visualizer and distributed cron scheduler.
* `app/integrations/page.tsx`: Enterprise Connectors Hub with live connection testing.
* `app/actions/page.tsx`: 3-column pack tree and dynamic schema-driven action runner.
* `app/history/page.tsx`: Reverse-chronological master-detail execution feed.
* `app/rules/page.tsx`: Event-driven automation rules engine.
* `app/packs/page.tsx`: Backstage / Port IDP Content Pack ecosystem.
* `app/audit/page.tsx`: Cryptographic Merkle chain audit ledger.
* `app/dashboard/page.tsx`: Enterprise Telemetry HUD.
* `components/layout/Header.tsx`: Global Header with live role badges and pending approvals indicator.
* `components/layout/Sidebar.tsx`: Persistent navigation linking all 11 views.
* `package.json`: Pinned Next.js 15, React 19, and Tailwind CSS dependencies.

### Deploy Directory (`vulcan-control-plane/deploy/`)
* `docker-compose.yml`: Complete local testbed with PostgreSQL 16 + pgvector, Redis 7.2 cluster, MinIO S3, FastAPI backend, and Next.js frontend.

---

## 4. Verification & Sign-off Criteria
All 6 verification gates passed:
* **Gate 1 (Domain Invariants & Policies):** 100% pass on all 60 Python unit tests (`test_domain_invariants.py`, `test_policy_engine.py`, `test_workflow_manager.py`, `test_redlock_concurrency.py`, `test_s3_multipart.py`, `test_ai_reasoning_evals.py`).
* **Gate 2 (Concurrency & Redlock):** Zero deadlocks and zero split-brain executions under distributed mutex locking.
* **Gate 3 (AI Intent & Slot-Filling):** Accurate parameter parsing and deterministic grammar-constrained decoding.
* **Gate 4 (Declarative Frontend):** 15 static routes compiled cleanly with 0 TypeScript errors (`npm run build`).
* **Gate 5 (Governance & SoD):** Maker-Checker mathematically enforced ($Requester \neq Approver$).
* **Gate 6 (Connectors & Workflows):** Bi-directional integrations and multi-step DAG pipelines verified.
