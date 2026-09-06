# PROJECT VULCAN: ENTERPRISE AUTOMATION CONTROL PLANE
## ARCHITECTURAL WAR ROOM: PLATFORM, INFRASTRUCTURE, CI/CD, OBSERVABILITY & RELEASE ENGINEERING MASTERPLAN
### Rigorous Multi-Perspective Critique, Forensic Platform Audit, Consolidated Opportunity Register & ADRs (Phases 0, 2, and 6)

**Date:** September 6, 2026  
**Document Version:** 1.0.0-PROD (Authoritative Platform Engineering Blueprint)  
**Classification:** Tier-0 Banking-Grade Automation Infrastructure & Governance Foundation  
**Location:** Mission-Critical War Room 4D, Enterprise Platform & SRE Engineering Tower  
**Target System:** Project Vulcan Platform Stack (`deploy/`, `.github/workflows/`, `backend/`, `frontend/`, `scripts/`, `migrations/`)  
**Canonical File Path:** `docs/PLATFORM_INFRASTRUCTURE_CI_OBSERVABILITY_DEBATE.md`  
**Mirror Path:** `PLATFORM_INFRASTRUCTURE_CI_OBSERVABILITY_DEBATE.md`

---

### EXECUTIVE MANDATE & CURRENT-STATE BASELINE

Project Vulcan is an enterprise-scale, banking-grade Automation Control Plane governing the execution of Ansible playbooks and Terraform plans across Tier-1 financial infrastructure (core transaction engines, payment gateways, F5 load balancers, and multi-cloud landing zones). Previous architectural war rooms have established authoritative registers for the Operator Console (`UI-01` through `UI-28`), the AI Chat Subsystem (`CHAT-01` through `CHAT-26`), and the Backend Governance Core (`BKND-01` through `BKND-35`).

This fourth debate addresses **THE PLATFORM**: the foundational substrate of reproducibility, infrastructure topology, CI/CD quality gates, runtime observability, disaster recovery, and release engineering spanning **Phase 0 (Baseline Reproducibility)**, **Phase 2 (Distributed Infrastructure Integration)**, and **Phase 6 (Production Hardening & Drills)**.

#### The Working Vertical Slice vs. The Operational Reality
Today, the local developer workstation reports an alluring picture of health:
* 64 passing unit and integration tests executing in ~2.33 seconds (`.venv/bin/pytest`).
* A Next.js 15 frontend compiling 15 application routes without TypeScript errors.
* A Docker Compose stack defining PostgreSQL 16 with the `pgvector` extension, Redis 7.2-alpine, and MinIO object storage.
* A FastAPI backend listening on port 8000 with interactive Swagger documentation.

However, an exhaustive forensic audit reveals that this operational health is a **mirage**. The system functions exclusively on the exact, undocumented state of a single developer's laptop. It lacks an active CI gate, runs on phantom persistence where the backend ignores its own backing databases, executes single-threaded in-memory state machines that collapse under concurrent workers, exposes unmanaged dev servers with default credentials, and possesses zero operational observability.

---

### FORENSIC AUDIT: THE EIGHT FATAL PLATFORM DEFECTS

The architectural war room convened with a non-negotiable rule: every critique must be grounded in forensically verifiable evidence from the repository. The following defect matrix represents the undisputed starting point of the platform debate:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        PROJECT VULCAN PLATFORM FORENSIC AUDIT MATRIX                                            │
├────┬─────────────────────────────┬───────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ ID │ DEFECT NAME                 │ CODE LOCATION & FORENSIC PROOF                                │ SEVERITY & IMPACT           │
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D1 │ Phantom CI Gate             │ .github/workflows/vulcan-gate.yml:6-14, 50-58, 67             │ CRITICAL / BLOCKING         │
│    │                             │ Paths omit `backend/**`. Step 50 runs `npm ci` at repo root   │ "60/60 tests pass" is a     │
│    │                             │ where package.json does not exist. Scripts invoke obsolete   │ local fiction. Zero tests   │
│    │                             │ `/whiteboard` smoke tests. Zero Python steps in CI.           │ run on push or pull request.│
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D2 │ Phantom Infrastructure      │ config.py:26-31, 41; deploy/docker-compose.yml:58-64          │ CRITICAL / FRAUD            │
│    │                             │ Compose runs Postgres 16, Redis, and MinIO; backend sets env  │ DB, Redis, and MinIO are    │
│    │                             │ vars, but AppContainer hardcodes `redis_nodes=[]`, mocks S3,  │ decoration. All state lives │
│    │                             │ and seeds jobs into in-memory Dict. Zero Vulcan migrations.   │ in volatile Python memory.  │
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D3 │ Single-Worker Trap          │ config.py:41; websockets.py:28-29; routes.py:841              │ CRITICAL / SCALABILITY      │
│    │                             │ Jobs in local heap; WebSockets use local process memory;      │ Uvicorn `--workers 2` or a  │
│    │                             │ execution runner spawned via raw daemon `threading.Thread`.   │ restart causes instant state│
│    │                             │ No distributed background sweeper for approval timeouts.      │ partition and lost jobs.    │
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D4 │ Dev-Server Reality          │ backend/main.py:8; backend/Dockerfile:1-18                    │ HIGH / COMPLIANCE           │
│    │                             │ Backend runs `uvicorn.run(..., reload=True)`. Dockerfile runs │ Unmanaged dev server as     │
│    │                             │ as root on python:3.11-slim (drift from local Python 3.14.6). │ root; missing healthchecks; │
│    │                             │ Zero resource limits, zero restart policies in Compose.       │ no graceful shutdown.       │
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D5 │ Default Secrets Void        │ deploy/docker-compose.yml:11, 43, 58, 62; backend/.env.example│ CRITICAL / SECURITY         │
│    │                             │ `vulcan_secure_password_2026` & `vulcan_minio_secret_2026`    │ Hardcoded credentials in git│
│    │                             │ hardcoded in Compose and example envs. No secret injection,   │ and compose. Zero rotation   │
│    │                             │ no rotation strategy, no vault abstraction.                   │ or lease protocol.          │
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D6 │ Python 3.14 Dependency     │ backend/requirements.txt:2-18; resolve_intent.py:164-210      │ HIGH / TECHNICAL DEBT       │
│    │ Wheel Risk                  │ Host uses Python 3.14.6. Constrained decoding (outlines,      │ Unpinned requirements (`>=`);│
│    │                             │ guidance -> numba, llvmlite) lack wheels. Forces fragile      │ C-extension builds will     │
│    │                             │ regex parsing fallbacks. No lockfile exists.                  │ brick CI pipelines.         │
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D7 │ Observability Void          │ server.py:6-45; routes.py:98-109; websockets.py:14            │ HIGH / SRE DEFECT           │
│    │                             │ Zero Prometheus metrics (`/metrics`). Logs are unstructured   │ Operators fly blind. Health │
│    │                             │ text. No correlation ID header propagation. Health route      │ route pegging CPU with O(N) │
│    │                             │ re-hashes entire Merkle ledger on every request.              │ blockchain verification.    │
├────┼─────────────────────────────┼───────────────────────────────────────────────────────────────┼─────────────────────────────┤
│ D8 │ Zero Drills & Untested      │ scripts/ (only obsolete frontend-smoke.mjs exists);           │ CRITICAL / AUDIT FAILURE    │
│    │ Phase 0 Gate                │ migrations/ (only whiteboard SQL tables exist).               │ RTO is purely theoretical.  │
│    │                             │ Zero backup/restore scripts, zero rollback drills, zero       │ Clean checkout cannot build │
│    │                             │ chaos tests. Phase 0 clean checkout gate never validated.     │ without undocumented steps. │
└────┴─────────────────────────────┴───────────────────────────────────────────────────────────────┴─────────────────────────────┘
```

#### Detailed Forensic Proofs from Repository Files:

1. **Defect 1: The Phantom CI Gate (`.github/workflows/vulcan-gate.yml`)**
   *Lines 5–14:* The workflow path filter defines:
   ```yaml
   paths:
     - 'apps/**'
     - 'packages/**'
     - 'frontend/**'
     - 'package.json'
     - 'package-lock.json'
     - 'migrations/**'
     - 'deploy/**'
     - 'scripts/**'
     - '.github/workflows/vulcan-gate.yml'
   ```
   *Forensic Proof:* `backend/**` is completely absent from the trigger paths. A developer can alter the entire domain state machine or delete backend routes, and GitHub Actions will not even trigger. Furthermore, line 50 executes `npm ci` at the root directory `/Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/`, but `ls package.json` returns `no such file or directory`—the file exists only inside `frontend/`. Line 51 attempts to run `npm run build -w @vulcan/domain`, referencing a monorepo workspace package that does not exist. Line 67 runs `node scripts/frontend-smoke.mjs`, which tests a `/whiteboard` landmark from an abandoned prototype. The workflow has never passed on GitHub and contains zero steps executing Python, pytest, ruff, or mypy.

2. **Defect 2: The Phantom Infrastructure Illusion (`backend/app/config.py` & `deploy/docker-compose.yml`)**
   *`deploy/docker-compose.yml:58–64`:* Compose injects `DATABASE_URL=postgresql://...`, `REDIS_URL=redis://...`, and `S3_ENDPOINT_URL=http://minio:9000`.
   *`backend/app/config.py:26–41`:*
   ```python
   self.lock_manager = RedlockManager(redis_nodes=[])
   self.audit_logger = MerkleAuditLogger(persistence_file="data/audit_ledger.jsonl")
   self.secret_provider = CyberArkPAMProvider(mock_mode=True)
   self.snow_gateway = ServiceNowGateway(mock_mode=True)
   self.storage_gateway = S3MultipartGateway(bucket_name="pnc-vulcan-artifacts", mock_mode=True)
   self.execution_engine = SimulationExecutionEngine(delay_per_step=0.02)
   self.jobs = self._seed_jobs()
   ```
   *Forensic Proof:* `AppContainer` ignores every environment variable injected by Compose. It initialises `RedlockManager` with an empty list `[]`, causing line 67 of `redlock_adapter.py` to enter fallback mode and unconditionally return `True` for every lock acquisition without talking to Redis. It stores jobs in a plain Python dictionary `self.jobs`. It mocks S3 uploads to `https://s3.mock.vulcan.internal`. The PostgreSQL container runs empty; the `migrations/` directory contains only `001_whiteboard.sql` and `002_identity_ai_audit.sql` defining `boards`, `workspaces`, and `memberships`. Not a single table exists for Project Vulcan.

3. **Defect 3: The Single-Worker Trap (`backend/app/api/websockets.py` & `routes.py`)**
   *`backend/app/api/websockets.py:28–29`:*
   ```python
   self.buffers: Dict[str, List[Dict]] = {}
   self.connections: Dict[str, Set[WebSocket]] = {}
   ```
   *`backend/app/api/routes.py:841`:*
   ```python
   thread = threading.Thread(target=run_worker, daemon=True)
   thread.start()
   ```
   *Forensic Proof:* All active jobs, log streams, and connected client sockets are bound to the memory space of a single OS process. If Uvicorn starts with `--workers 4` behind a round-robin proxy, an approval submitted by an operator hitting Worker 2 will fail with 404 because the job was seeded into Worker 1's heap. A WebSocket client connected to Worker 3 will receive zero log lines because the runner thread is executing on Worker 1. Furthermore, spawning execution via an unmanaged daemon OS thread inside the web process means an application restart or OOM event will instantly sever execution mid-playbook without triggering compensation or teardown.

4. **Defect 4: The Dev-Server Reality (`backend/main.py` & `backend/Dockerfile`)**
   *`backend/main.py:8`:*
   ```python
   uvicorn.run("app.api.server:app", host="0.0.0.0", port=8000, reload=True)
   ```
   *`backend/Dockerfile:1–18`:*
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   ...
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   CMD ["python", "main.py"]
   ```
   *Forensic Proof:* The containerised backend executes `reload=True`, activating StatReload file system watchers in production containers. The container runs as the `root` superuser. The Dockerfile base is `python:3.11-slim`, whereas the developer workstation runs Python 3.14.6, introducing severe runtime and ABI divergence. In `deploy/docker-compose.yml`, neither `backend` nor `minio` specifies a `healthcheck`, and `frontend` depends on `backend` without a health condition (`depends_on: - backend`), causing the frontend to boot and attempt API requests before the backend port is bound. Zero containers define CPU or memory constraints.

5. **Defect 5: The Default Secrets Void (`deploy/docker-compose.yml` & `backend/.env.example`)**
   *`deploy/docker-compose.yml:11, 43`:*
   ```yaml
   POSTGRES_PASSWORD: vulcan_secure_password_2026
   MINIO_ROOT_PASSWORD: vulcan_minio_secret_2026
   ```
   *Forensic Proof:* Static, default credentials are hardcoded directly in version-controlled infrastructure manifests. There is no `.env` interpolation, no secret manager provider, and no dynamic credential leasing. If deployed to a staging or pilot cluster, these default credentials grant full administrative control over the control plane's database and artifact storage.

6. **Defect 6: Python 3.14 Dependency Wheel Risk & Missing Lockfiles (`backend/requirements.txt`)**
   *`backend/requirements.txt:2–18`:*
   Every single dependency specifies an unpinned lower bound (`fastapi>=0.115.0`, `redis>=5.0.0`, `psycopg[binary]>=3.2.0`).
   *Forensic Proof:* There is no `requirements.lock`, `poetry.lock`, or `uv.lock`. When a new sub-dependency releases a breaking change, builds will fail non-deterministically. Furthermore, on Python 3.14.6, modern grammar-constrained decoding libraries (`outlines`, `guidance`) fail to build because their dependencies (`numba`, `llvmlite`) lack precompiled wheels for Python 3.14. This forced `backend/app/use_cases/resolve_intent.py:173–209` to resort to manual, brittle regex parsing for IPs and hostnames.

7. **Defect 7: The Observability Void (`backend/app/api/server.py` & `routes.py`)**
   *`backend/app/api/server.py`:* Contains zero middleware for correlation ID tracing (`X-Correlation-ID`) and zero Prometheus metrics exporters (`prometheus_client` or `/metrics`).
   *`backend/app/api/routes.py:98–109`:*
   ```python
   @router.get("/health")
   def get_health():
       is_audit_valid = container.audit_logger.verify_chain()
       return {"status": "OPERATIONAL", ...}
   ```
   *Forensic Proof:* The sole health endpoint synchronously executes `verify_chain()`, which iterates across every single Merkle block in the audit ledger and performs SHA-256 hash recalculations. At 50,000 audit records, a simple Docker liveness probe every 5 seconds will pin 100% of the CPU core and trigger a cascading denial-of-service. There is no separation between liveness (`/healthz`) and readiness (`/readyz`).

8. **Defect 8: Zero Operational Drills & Untested Phase 0 Gate (`scripts/` & `docs/`)**
   *Forensic Proof:* The repository contains zero automated backup scripts for PostgreSQL (`pg_dump` with WAL streaming), zero MinIO replication configs, zero rollback drill scripts, and zero chaos test harnesses. Phase 0 of the project plan mandates: *"A clean checkout builds and passes all tests without manual steps."* Because of the missing root `package.json`, missing lockfiles, and broken CI scripts, a clean checkout on a fresh machine fails immediately.

---

### EXPLICIT NON-GOALS (THE PLATFORM BOUNDARY)

To maintain focus and avoid over-engineering during Phases 0, 2, and 6, the Platform SRE Lead and Architecture Council enforce the following **Six Non-Goals**:

1. **Docker Compose is for Local Pilot & CI Only (No Multi-DC Kubernetes in Pilot):** We will not write Helm charts, Terraform for EKS/GKE, or distributed multi-region orchestrators for the initial bank pilot. Docker Compose is the target deployment artifact for local evaluation, CI, and the single-host air-gapped pilot VM.
2. **Zero Production Bank Access from CI or Local Workstations:** CI and local environments shall never attempt to dial PNC Bank's internal CyberArk Enterprise Vault, corporate ServiceNow instances, or live core banking subnets. All external dependencies must be satisfied by hermetic, local contract testcontainers.
3. **Default Secrets Shall NEVER Ship to Any Shared Environment:** No build artifact or compose deployment outside an isolated developer sandbox shall run with default passwords. Production and pilot configurations must mandate external secret injection via files or environment variables.
4. **Development Servers Are Not Deployment Artifacts:** We will never package `uvicorn --reload` or `next dev` into deployable container images. All container images must represent immutable, optimised production builds.
5. **No 5-Node Redlock Complexity Until Multi-Host Deployment is Earned:** While the PRD and documentation tout a 5-node Redlock consensus cluster, Compose runs a single Redis container. We will not fabricate multi-node Redis topologies in Compose; we will engineer a rock-solid, AOF-persisted single Redis instance for the pilot and defer distributed quorum locks until physical multi-node worker fleets are provisioned.
6. **No Phantom Metrics or Observability Theater:** We will not deploy heavy external observability platforms (Datadog agents, full Grafana Mimir/Loki clusters) inside the local Compose stack. The platform will expose standard OpenTelemetry spans and Prometheus `/metrics`, validated by lightweight contract probes.

---

### THE WAR ROOM PARTICIPANTS

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           WAR ROOM 4D PARTICIPANT MATRIX                                         │
├────────────────────────┬──────────────────────────────────────┬──────────────────────────────────────────────────┤
│ PERSONA                │ PRIMARY ARCHITECTURAL LENS           │ FOCUS IN PLATFORM & RELEASE DEBATE               │
├────────────────────────┼──────────────────────────────────────┼──────────────────────────────────────────────────┤
│ Robert C. Martin       │ Clean Architecture, Testability,     │ The environment as the first dependency; hermetic │
│ ("Uncle Bob")          │ Invariants & Dependency Hygiene      │ CI gates; pinned lockfiles; clean checkout tests;│
│                        │                                      │ elimination of human manual intervention.        │
├────────────────────────┼──────────────────────────────────────┼──────────────────────────────────────────────────┤
│ Alex Xu                │ Distributed Systems, Capacity,       │ Compose topology; health-check ordering; probes  │
│                        │ Failure Modes & Storage Topologies   │ (/healthz vs /readyz); Redis persistence & AOF;  │
│                        │                                      │ MinIO bucket bootstrap; RTO-measured backups.    │
├────────────────────────┼──────────────────────────────────────┼──────────────────────────────────────────────────┤
│ Andrej Karpathy        │ AI Infrastructure, Eval Repeatability│ Eval harness as CI artifact; deterministic fake  │
│                        │ & Runtime Compatibility              │ model provider; golden dataset versioning; pure- │
│                        │                                      │ Python grammar fallback; AI token telemetry.     │
├────────────────────────┼──────────────────────────────────────┼──────────────────────────────────────────────────┤
│ Jordan Walke           │ Declarative UI, Frontend Build       │ Next.js production build contract; runtime vs    │
│                        │ Pipelines & End-to-End Contracts     │ build-time env vars; Playwright E2E in CI against│
│                        │                                      │ full Compose stack; bundle & performance budgets.│
├────────────────────────┼──────────────────────────────────────┼──────────────────────────────────────────────────┤
│ Platform SRE Lead      │ Runtime Hardening, Security Posture, │ Multi-stage distroless images; non-root users;   │
│ (Chair & Owner)        │ CI/CD Gates, Observability & Release │ SBOM & CVE scanning; 12-factor secrets; release  │
│                        │                                      │ tag gates; backup/restore & chaos drills.        │
└────────────────────────┴──────────────────────────────────────┴──────────────────────────────────────────────────┘
```

---

## 1. THE ARCHITECTURAL DEBATE SESSIONS

---

### SESSION 1: PHASE 0 — THE CLEAN CHECKOUT TEST, DEPENDENCY PINNING & CI AS FIRST CITIZEN

**Platform SRE Lead (Chair):**  
"Welcome to War Room 4D. Let us dispense with polite fictions immediately. Phase 0 of Project Vulcan's delivery plan promises: *'A clean checkout builds and passes all tests without manual steps.'* Furthermore, our developers proudly claim that 64 out of 64 pytest tests pass in 2.3 seconds.

Look at `.github/workflows/vulcan-gate.yml`. It is an absolute catastrophe. 
Lines 6–14 filter triggers on `apps/**`, `packages/**`, and `frontend/**`. The entire `backend/` directory is missing from path filtering! If I rewrite `app/domain/entities.py`, CI does not even awaken!
Worse, look at line 50: `run: npm ci` at the root directory. There is no `package.json` at the root! If anyone pushes to GitHub right now, GitHub Actions crashes instantly with `ENOENT: no such file or directory, open 'package-lock.json'`.
Line 51 runs `npm run build -w @vulcan/domain`. There is no `@vulcan/domain` workspace in this repository!
Line 67 runs `node scripts/frontend-smoke.mjs`, which curls `/whiteboard` looking for 'Whiteboard editor'! That is leftover code from an entirely different application!
And the most damning fact of all: there is not a single line of Python in `.github/workflows/vulcan-gate.yml`. No `actions/setup-python`, no virtual environment, no `pytest`, no `ruff`, no `mypy`.
Gentlemen, '64/64 tests pass' is an unverified claim on one person's laptop. We have zero CI."

**Uncle Bob:**  
"Thank you for speaking the truth, Chair. In Clean Architecture, **the environment is the very first dependency of the system**. If your build requires an undocumented environment variable, a pre-existing virtual environment, or an engineer running commands manually, your architecture is broken. Reproducibility *is* testability!

Look at `backend/requirements.txt`:
```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.8.0
redis>=5.0.0
psycopg[binary]>=3.2.0
```
Every single line uses `>=`! This is an open invitation to chaos. Tomorrow, Pydantic or Psycopg releases a minor version that deprecates an internal API, and our builds break across the team without a single line of our code changing! Where is `requirements.lock`? Where is `uv.lock` or `poetry.lock`?

And look at `frontend/package.json`. It specifies:
```json
"dependencies": {
  "next": "^15.0.0",
  "react": "^19.0.0"
}
```
At least the frontend has a `package-lock.json`, but because our CI script runs at the root instead of inside `frontend/`, it is never verified!

Here is my demand for Phase 0:
1. **The Hermetic Clean Checkout Test:** We must have an automated test—run in a completely clean Docker container with zero mounted volumes and zero ambient host caches—that executes:
   `git clone -> make setup -> make verify`.
   If any human intervention is required, the build fails.
2. **Absolute Dependency Pinned Invariants:** Every Python dependency must be strictly pinned with cryptographic hashes using `uv pip compile` to generate an immutable `requirements.lock`. Every Node dependency must be installed via `npm ci` strictly adhering to `package-lock.json`.
3. **The Universal CI Gate:** The GitHub Actions pipeline must execute three non-negotiable parallel tracks on every push and PR:
   - Track A (Backend): Python 3.12 LTS setup -> dependency hash verification -> `ruff` lint -> `mypy` strict typecheck -> `import-linter` domain boundary check -> `pytest` unit & invariant suite.
   - Track B (Frontend): Node 20 LTS setup -> `npm ci` -> `tsc --noEmit` -> `next lint` -> unit tests.
   - Track C (Integration): Boot Compose stack -> contract smoke tests -> teardown.
   If any track fails, merging to `main` is physically blocked."

**Jordan Walke:**  
"Bob is completely right about the frontend CI failure, but let us also talk about what the frontend actually needs to build.
In `frontend/package.json`, our scripts are:
```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "typecheck": "tsc --noEmit"
}
```
Notice what is missing? There is no `"test"` script! There is no Jest, no Vitest, and no Playwright! Our frontend has zero automated unit or component tests.
And look at `scripts/frontend-smoke.mjs`:
```javascript
const baseUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3100";
...
const html = await response.text();
if (!html.includes("Whiteboard editor")) throw new Error("whiteboard editor landmark missing");
```
It looks for 'Whiteboard editor'! When I built the Obsidian Glass console for Project Vulcan, we created routes for `/dashboard`, `/matrix`, `/workflows`, `/audit`, `/actions`, `/policies`, and `/chat`. The `/whiteboard` route does not even exist!
If you run that script today against the Vulcan frontend, it fails with a 404!

We must delete `frontend-smoke.mjs` immediately and replace it with a true Playwright smoke suite that verifies the real Vulcan DOM landmarks: the Execution Grid, the Approval Banner, the Terminal stream, and the Intent Resolution drawer. And we must wire that directly into Track B of the CI pipeline."

**Alex Xu:**  
"While Bob and Jordan focus on application code, look at what happens in CI when you try to test integration.
In `.github/workflows/vulcan-gate.yml:20–42`, the author attempted to configure GitHub Actions service containers for Postgres and Redis:
```yaml
services:
  postgres:
    image: postgres:16-alpine
    ...
  redis:
    image: redis:7-alpine
```
Notice:
1. They used standard `postgres:16-alpine`, NOT `pgvector/pgvector:pg16`! If any test attempts to execute an HNSW vector query, Postgres throws `ERROR: extension "vector" does not exist`!
2. MinIO is completely missing from the CI services! Any test touching our S3 multipart adapter will crash with connection refused!
3. The database name in CI is `vulcan`, with user `vulcan`, while `deploy/docker-compose.yml` uses database `vulcan_control_plane` with user `vulcan_admin`!

This means our local environment and our CI environment have completely different topologies, different credentials, and different capabilities! That violates the core principle of environment parity. CI must test the exact same Compose contract that runs on the pilot workstation!"

**Platform SRE Lead (Chair):**  
"Let us converge on Session 1. We have exposed the root causes: phantom CI files, missing backend triggers, unpinned Python dependencies, missing frontend test harnesses, and environment divergence between CI services and Compose.

Here are the concrete opportunities spawned by this session:
* `INFRA-01`: Overhaul GitHub Actions CI into a unified multi-stage gate (`vulcan-ci.yml`) covering backend, frontend, and compose contracts.
* `INFRA-02`: Hermetic clean-checkout verification script (`scripts/verify-clean-checkout.sh`) executed as an isolated CI job.
* `INFRA-03`: Pinned dependency locks with hash verification (`requirements.lock` via `uv` and `frontend/package-lock.json`).
* `INFRA-04`: Purge legacy whiteboard smoke tests and establish Playwright frontend landmark smoke suite.
* `INFRA-05`: CI/Local environment parity enforcement: CI services must run the canonical `pgvector/pgvector:pg16`, Redis, and MinIO stack matching Compose exactly."

---

#### SPAWNED OPPORTUNITIES — SESSION 1
* **INFRA-01: Unified Multi-Stage CI Quality Gate (`vulcan-ci.yml`)**  
  *Problem Killed:* Eliminates Defect D1 (Phantom CI Gate). Restores path filtering for `backend/**`, `frontend/**`, and `deploy/**`. Enforces parallel execution of lint, strict typecheck, unit tests, and integration smoke on every PR.  
  *Acceptance Criteria:* GitHub Actions workflow triggers on push/PR to `main` across all project paths; executes `ruff`, `mypy --strict`, `pytest`, `npm run typecheck`, `next lint`, and Playwright smoke; fails closed if any check fails; blocks merge on red.  
  *Source:* Platform SRE Lead (Chair)

* **INFRA-02: Hermetic Clean-Checkout Verification Job**  
  *Problem Killed:* Kills the undocumented host setup trap where code builds only on one configured laptop.  
  *Acceptance Criteria:* A dedicated CI job checks out a pristine repository clone in a bare Alpine/Debian container, executes `./scripts/verify-clean-checkout.sh`, and validates that dependencies install, schemas validate, and test suites pass without any interactive prompts or manual configuration.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **INFRA-03: Pinned Dependency Locking with Cryptographic Hashes**  
  *Problem Killed:* Eliminates unpinned `>=` bounds in `backend/requirements.txt` (Defect D6). Prevents non-deterministic build failures.  
  *Acceptance Criteria:* `requirements.lock` generated via `uv pip compile --generate-hashes`; CI enforces that `pip install --require-hashes -r requirements.lock` is used during container builds; any unpinned dependency addition causes CI failure.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **INFRA-04: Replacement of Obsolete Whiteboard Smoke Script with Playwright Suite**  
  *Problem Killed:* Deletes `scripts/frontend-smoke.mjs` checking for `/whiteboard` and "Whiteboard editor".  
  *Acceptance Criteria:* New suite `frontend/tests/e2e/smoke.spec.ts` verifies Next.js root redirect to `/dashboard`, renders Header navigation, loads the execution matrix, and asserts presence of `#vulcan-terminal-landmark`; passes in headless Chromium in CI.  
  *Source:* Jordan Walke

* **INFRA-05: Infrastructure Environment Parity Engine**  
  *Problem Killed:* Eliminates config drift where CI runs vanilla Postgres 16 while Compose runs `pgvector:pg16`, with mismatched database names (`vulcan` vs `vulcan_control_plane`).  
  *Acceptance Criteria:* CI pipeline spins up `deploy/docker-compose.yml` directly via `docker compose up -d` for integration testing, guaranteeing identical container tags, environment variable schemas, and network topologies across CI, local dev, and pilot VMs.  
  *Source:* Alex Xu

---

### SESSION 2: COMPOSE TOPOLOGY — HEALTH PROBES, STARTUP ORDERING, SECRETS & RESOURCE LIMITS

**Alex Xu:**  
"Now let us examine `deploy/docker-compose.yml`. This file represents our deployment topology for local developers and the pilot VM. When I inspect it through the lens of distributed systems and capacity, it fails basic systems engineering standards.

Look at lines 38–50:
```yaml
minio:
  image: minio/minio:latest
  container_name: vulcan-minio
  environment:
    MINIO_ROOT_USER: vulcan_minio_admin
    MINIO_ROOT_PASSWORD: vulcan_minio_secret_2026
  command: server /data --console-address ":9001"
  ports:
    - "9000:9000"
    - "9001:9001"
  volumes:
    - minio_data:/data
```
First, `minio/minio:latest` uses a floating tag! In production and banking infrastructure, using `:latest` is professional negligence. A MinIO release tomorrow could deprecate the CLI flags or change default authentication, and our stack stops booting.
Second, `minio` has NO HEALTHCHECK!
Third, look at `backend`:
```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```
Notice that `backend` depends on `postgres` and `redis`, but does NOT depend on `minio`! If `backend` starts up and attempts to verify the S3 artifact bucket on boot, it races against MinIO's startup!
And who creates the bucket? MinIO starts with an empty `/data` volume. It does NOT automatically create `vulcan-artifacts`! In S3, if a bucket does not exist, all presigned URL generation and uploads fail with `NoSuchBucket`! Where is the MinIO provisioning container?

Fourth, look at `frontend`:
```yaml
frontend:
  depends_on:
    - backend
```
It does not say `condition: service_healthy` because `backend` HAS NO HEALTHCHECK! So Docker starts `backend`, and immediately starts `frontend`. The Next.js frontend tries to fetch `/api/catalog` or `/health` while Uvicorn is still importing Python modules, resulting in HTTP 502 Bad Gateway errors on boot!"

**Platform SRE Lead (Chair):**  
"Alex is identifying severe startup race conditions, but look at the security disaster in that same file:
Lines 11, 43, 58, 62:
```yaml
POSTGRES_PASSWORD: vulcan_secure_password_2026
MINIO_ROOT_PASSWORD: vulcan_minio_secret_2026
DATABASE_URL: postgresql://vulcan_admin:vulcan_secure_password_2026@postgres:5432/vulcan_control_plane
S3_SECRET_KEY: vulcan_minio_secret_2026
```
This is Defect D5. Plaintext passwords hardcoded in a git-tracked file!
If an engineer clones this repo and runs `docker compose up` on a pilot server inside the bank network, the database is wide open to anyone with internal network access who guesses the password from GitHub!

In banking security under OCC and NIST SP 800-53:
1. Passwords and secret keys must **NEVER** exist in docker-compose.yml.
2. We must enforce a **12-Factor Secrets Contract**: `docker-compose.yml` must use variable substitution (`${POSTGRES_PASSWORD:?Error: POSTGRES_PASSWORD must be set}`).
3. In local development, these values must be loaded from an uncommitted `.env` file created from `.env.template` via an automated bootstrap script.
4. If an unpinned default credential is detected in CI, the build must fail immediately via a GitGuardian or TruffleHog pre-commit scan!"

**Uncle Bob:**  
"And what about resource limits and restart policies? Look at every service in `deploy/docker-compose.yml`. Not a single one defines:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2048M
```
If a rogue Ansible execution or an unconstrained Python query triggers a memory leak, it will consume all host RAM, invoke the Linux Out-Of-Memory (OOM) killer, and crash the Docker daemon!
Furthermore, none of the services declare `restart: unless-stopped`. If the host experiences a transient blip or Postgres crashes during a high-load query, the container simply dies and stays dead!"

**Alex Xu:**  
"Now, let us confront the Redis honesty question.
In `docs/BACKEND_CONTROL_PLANE_ARCHITECTURE_DEBATE.md` and our PRDs, we spent thousands of words describing a '5-Node Redlock Distributed Consensus Mutex with Quorum Voting across separate availability zones'.
Now look at `deploy/docker-compose.yml:23–35`:
```yaml
redis:
  image: redis:7.2-alpine
  command: ["redis-server", "--appendonly", "yes"]
```
There is ONE Redis container! A single instance!
And look at `backend/app/adapters/redlock_adapter.py:48–50`:
```python
self.redis_nodes = redis_nodes or []
self.quorum = (len(self.redis_nodes) // 2) + 1 if self.redis_nodes else 1
```
And in `AppContainer`, `redis_nodes=[]`!
Gentlemen, why are we pretending to run Martin Kleppmann vs. Salvatore Sanfilippo distributed consensus on a single-node Compose stack?
Attempting to run a 5-node Redlock consensus protocol on a single developer laptop or a single pilot VM is pure architecture theater. It adds latency, multiplies network sockets by 5, and creates artificial split-brain scenarios when Docker throttles CPU.

For Project Vulcan's local pilot, the honest, robust distributed systems decision is:
1. **Single-Node Hardened Redis 7.2:** Configure a single Redis 7.2 instance with `appendonly yes`, `appendfsync everysec`, and `maxmemory 512mb` with `maxmemory-policy noeviction` (so lock keys are never silently evicted under memory pressure).
2. **Atomic Lua Mutex with Watchdog Heartbeat:** Use an atomic Lua acquire/release script with a background renewal watchdog. It gives 100% mutual exclusion for the single-host pilot.
3. **Earned Complexity Gate:** Document honestly in the ADR that multi-node Redlock consensus is deferred until Phase 6 multi-host enterprise deployment, where Redis nodes run on distinct physical hardware."

**Platform SRE Lead (Chair):**  
"Agreed. That is refreshing honesty. Let us also fix the MinIO bootstrap.
We will add a dedicated, lightweight initialization service to Compose: `minio-init` using the `minio/mc:RELEASE...` pinned client image. It will depend on MinIO being healthy, execute `mc alias set`, create the `vulcan-artifacts` bucket if it does not exist, configure a 30-day lifecycle retention policy on transient execution logs, and exit cleanly with code 0.
Then `backend` will depend on `minio-init` with `condition: service_completed_successfully`.
This guarantees that the moment the backend boots, the database is healthy, Redis is listening, and the S3 bucket exists and is writable.

Let us record the opportunities for Session 2:
* `INFRA-06`: Hardened Docker Compose topology with healthcheck dependency chain (`postgres` healthy -> `redis` healthy -> `minio` healthy -> `minio-init` completed -> `backend` healthy -> `frontend`).
* `INFRA-07`: MinIO bootstrap provisioner container (`minio-init`) for bucket creation and retention policies.
* `INFRA-08`: 12-Factor Secrets Contract with zero default passwords in Compose and `.env.template` enforcement.
* `INFRA-09`: Container resource limits (CPU/Memory quotas) and `unless-stopped` restart policies.
* `INFRA-10`: Rationalized Single-Node Redis 7.2 ADR with AOF persistence, `noeviction` policy, and atomic Lua mutex."

---

#### SPAWNED OPPORTUNITIES — SESSION 2
* **INFRA-06: Hardened Docker Compose Topology & Health-Check Dependency Chain**  
  *Problem Killed:* Eliminates startup race conditions (Defect D4) where services boot out of order and crash.  
  *Acceptance Criteria:* `deploy/docker-compose.yml` specifies explicit healthchecks for all services; backend depends on `postgres` (`service_healthy`), `redis` (`service_healthy`), and `minio-init` (`service_completed_successfully`); frontend depends on `backend` (`service_healthy`); stack boots cleanly via `docker compose up -d` with zero 502/connection refused errors.  
  *Source:* Alex Xu

* **INFRA-07: MinIO Bucket Bootstrap Provisioner (`minio-init`)**  
  *Problem Killed:* Kills the `NoSuchBucket` runtime error on uninitialised MinIO volumes.  
  *Acceptance Criteria:* Ephemeral service running `minio/mc` creates `vulcan-artifacts` bucket and configures private access policies before backend service accepts requests; exits with code 0.  
  *Source:* Alex Xu & Platform SRE Lead

* **INFRA-08: 12-Factor Secrets Contract & TruffleHog Pre-Commit Scanning**  
  *Problem Killed:* Eliminates hardcoded plaintext passwords in git-tracked Compose files (Defect D5).  
  *Acceptance Criteria:* All passwords in `docker-compose.yml` use `${VAR:?error}` syntax; credentials supplied via local uncommitted `.env` file generated by `scripts/bootstrap-env.sh`; CI executes TruffleHog secret scan; commits containing plaintext keys fail immediately.  
  *Source:* Platform SRE Lead (Chair)

* **INFRA-09: Container Resource Limits & Crash Resilience Policies**  
  *Problem Killed:* Prevents memory leaks or runaway processes from crashing the host OS via OOM.  
  *Acceptance Criteria:* All Compose services specify `deploy.resources.limits.memory` and `cpus`; all production-facing services specify `restart: unless-stopped`; memory limits verified under stress testing.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **INFRA-10: Rationalised Redis 7.2 Storage Engine & Mutex Contract**  
  *Problem Killed:* Eliminates the false claim of 5-node Redlock in single-host deployments while fixing lock eviction risks.  
  *Acceptance Criteria:* Redis configured with `--appendonly yes`, `--appendfsync everysec`, and `--maxmemory-policy noeviction`; ADR-004 records single-node Redis as authoritative for pilot, establishing concrete SLA criteria for migrating to Redis Cluster in Phase 6.  
  *Source:* Alex Xu

---

### SESSION 3: FROM DEV SERVER TO DEPLOYABLE ARTIFACT — IMAGES, PROBES, SHUTDOWN & MULTI-WORKER TOPOLOGY

**Platform SRE Lead (Chair):**  
"Now let us examine Defect D4 and Defect D3: the transition from an unmanaged developer server to a production deployable artifact.

Look at `backend/main.py`:
```python
if __name__ == "__main__":
    uvicorn.run("app.api.server:app", host="0.0.0.0", port=8000, reload=True)
```
And look at `backend/Dockerfile:18`:
```dockerfile
CMD ["python", "main.py"]
```
Our container is running Uvicorn with `reload=True`! That means a watchdog file monitor is polling disk changes inside a production container!
Furthermore, it runs as `root`. If an attacker executes arbitrary code via a malicious Ansible playbook or shell escape, they own the root user of the container and can attempt container breakout.

And what happens when Docker sends `SIGTERM` to stop the backend container?
Because `python main.py` is running as PID 1 without a proper signal handler or graceful shutdown timeout, Docker waits 10 seconds, times out, and sends `SIGKILL`!
If an Ansible playbook was halfway through reconfiguring a core router or database tablespace, the execution is abruptly murdered! The Redis lock is orphaned for 30 seconds, the audit log never receives `EXEC_FAILED`, and the infrastructure is left in an unknown, corrupted state!"

**Jordan Walke:**  
"And look at `frontend/Dockerfile`:
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
CMD ["npm", "start"]
```
Look at what is wrong here:
1. `COPY package.json ./` followed by `RUN npm install`. It does not copy `package-lock.json`! It runs `npm install` instead of `npm ci`, which mutates the dependency tree on every build!
2. It runs as `root`! `node:20-alpine` comes with a built-in unprivileged user `node`, but the Dockerfile never switches to it (`USER node`).
3. It copies the entire `node_modules` folder from the builder stage into the runner stage, including devDependencies (`typescript`, `@types/*`, `tailwindcss`, `postcss`)! That bloats the image to over 800MB!
4. **The Next.js Build-Time Inlining Trap:**
   Look at our frontend code. We have `process.env.NEXT_PUBLIC_API_URL` scattered across 10 files.
   In Next.js, `NEXT_PUBLIC_*` environment variables are replaced at **BUILD TIME** by Webpack/Turbopack!
   Because `frontend/Dockerfile` does not declare `ARG NEXT_PUBLIC_API_URL`, Next.js compiles the fallback string `'http://localhost:8000'` directly into the static JavaScript chunks!
   When we deploy this image to the pilot server at `https://vulcan.bank.internal`, any operator opening the browser will have their browser attempt to connect to `http://localhost:8000` on their own local machine! The frontend cannot communicate with the backend!"

**Alex Xu:**  
"Jordan has hit on a critical production frontend flaw. In Next.js production deployments, we must either:
- Pass `ARG NEXT_PUBLIC_API_URL` during `docker build`, OR
- Better yet, use a runtime configuration endpoint (`/api/config` or relative `/api` paths with reverse-proxy routing) so that the container image is built **once** and promoted across Dev, CI, Pilot, and Prod without rebuilding!

Now let us confront Defect D3: **The Single-Worker Trap**.
Look at `backend/app/api/routes.py:826–844`:
```python
def run_worker():
    try:
        ws_hub.publish(job.correlation_id, "status", {"status": "RUNNING", "message": "Worker spawned"})
        runner.run(job)
        ws_hub.publish(job.correlation_id, "status", {"status": job.status.value, "message": "Execution complete"})
    except Exception as e:
        ...

thread = threading.Thread(target=run_worker, daemon=True)
thread.start()
```
The FastAPI route spawns a raw, unmanaged daemon Python OS thread directly inside the web server process!
Now consider what happens when we run a production application server with multiple workers:
`gunicorn app.api.server:app -w 4 -k uvicorn.workers.UvicornWorker`
1. Worker 1 receives the POST `/jobs/EXEC-001/execute`. It spawns a background thread on Worker 1.
2. The browser connects via WebSocket to `/ws/logs/EXEC-001`. The reverse proxy routes the WebSocket to Worker 2.
3. Worker 2's `ws_hub.buffers` has never heard of `EXEC-001`. The operator sees a blank terminal!
4. An operator clicks 'Reject' or 'Approve' on another job. The request lands on Worker 3. Worker 3 looks up `container.jobs.get(id)`. Because `self.jobs` is an in-memory dictionary on Worker 1, Worker 3 returns HTTP 404 Not Found!
5. And what about the 15-minute approval timeout sweeper? If a job is waiting for approval, who sweeps it? In `entities.py:257`, timeout is only checked when someone actively attempts to approve it! If nobody clicks anything, it sits in `PENDING_APPROVAL` forever in memory!

We have two architectural paths:
- Path A: Pretend we are multi-worker, run Gunicorn with 4 workers, and suffer immediate split-brain state corruption.
- Path B: Acknowledge the architecture honestly and engineer the proper multi-worker topology."

**Uncle Bob:**  
"In Clean Architecture, the web server is a **delivery mechanism**, not an execution engine! An HTTP request handler's only job is to validate input, invoke a use case, and return a response. Spawning long-running OS threads inside an HTTP handler violates Single Responsibility and turns the API server into a fragile monolith.

The authoritative multi-worker topology must be:
1. **The API Node (Stateless Web Tier):** Runs FastAPI/Uvicorn. It possesses ZERO in-memory job dictionaries and ZERO daemon execution threads. It validates requests and commits jobs to PostgreSQL.
2. **The Distributed Work Queue (Redis Streams):** When a job is approved, the API node pushes an execution message to a Redis Stream (`stream:jobs:queued`).
3. **The Worker Fleet (Decoupled Runner Process):** Dedicated worker processes (e.g. ARQ or Celery or a standalone Python runner daemon) pull jobs from Redis Streams, acquire the Redlock mutex, invoke `BaseJobRunner.run()`, and stream logs to a Redis Pub/Sub channel.
4. **The Distributed Event Hub:** The API nodes subscribe to Redis Pub/Sub (`pubsub:logs:{correlation_id}`) and bridge log lines to the operator's WebSocket connection. Now it does not matter which worker runs the playbook or which API node terminates the WebSocket!"

**Platform SRE Lead (Chair):**  
"Bob's target architecture is the gold standard, but we must sequence it honestly across our delivery phases:
- **Phase 0 & Pilot (The Honest Single-Worker Interim Decision):**
  Until the Celery/ARQ worker fleet and PostgreSQL repository adapters are implemented, we MUST NOT run Uvicorn with `--workers > 1`.
  The pilot deployment will run a **single hardened Uvicorn worker process** (`uvicorn app.api.server:app --workers 1 --timeout-graceful-shutdown 30 --no-reload`).
  We will explicitly document this limitation in ADR-005.
- **Production Hardening (Phase 2 & Phase 6 Target):**
  We will implement the Redis Streams worker pool and the Redis Pub/Sub WebSocket backplane as specified in `INFRA-14` and `BKND-06`.

And for our container images:
1. **Multi-stage, unprivileged Dockerfiles:** Both `backend/Dockerfile` and `frontend/Dockerfile` must create an unprivileged user (`vulcan`, UID 10001) and switch to `USER vulcan`.
2. **Graceful Shutdown Protocol:** The backend entrypoint must handle `SIGTERM` and `SIGINT`, set a draining flag, reject new incoming executions with HTTP 503, wait up to 30 seconds for active playbooks to complete or checkpoint, and flush audit logs before exiting.
3. **Frontend Standalone Output:** Configure Next.js with `output: 'standalone'` in `next.config.js`. This copies only the strictly necessary files into the runner stage, reducing image size from 800MB to under 120MB and eliminating the devDependencies bloat.

Let us record the opportunities for Session 3:
* `INFRA-11`: Multi-stage, unprivileged, distroless-base Dockerfiles for backend and frontend.
* `INFRA-12`: Graceful shutdown signal handling (SIGTERM draining, 30s timeout, lock release).
* `INFRA-13`: Next.js standalone build contract with runtime environment configuration.
* `INFRA-14`: Interim Single-Worker ADR & Redis Streams Worker Fleet Migration Blueprint.
* `INFRA-15`: Background Periodic Sweeper Daemon for fail-closed approval timeout enforcement."

---

#### SPAWNED OPPORTUNITIES — SESSION 3
* **INFRA-11: Multi-Stage Production Container Images with Non-Root Users**  
  *Problem Killed:* Eliminates Defect D4 (running as root on dev servers). Shrinks container attack surface.  
  *Acceptance Criteria:* `backend/Dockerfile` and `frontend/Dockerfile` use multi-stage builds; runner stages run as `USER vulcan` (UID 10001); base images pinned to explicit SHAs or patch releases (`python:3.12.5-slim-bookworm`, `node:20.17.0-alpine3.20`); frontend image size reduced to $<150$MB using Next.js standalone output.  
  *Source:* Platform SRE Lead (Chair)

* **INFRA-12: Graceful Shutdown & In-Flight Execution Drain Protocol**  
  *Problem Killed:* Prevents orphaned distributed locks and corrupted infrastructure when containers restart mid-run.  
  *Acceptance Criteria:* Backend intercepts `SIGTERM`/`SIGINT`; stops accepting new jobs; waits up to 30s (`--timeout-graceful-shutdown 30`) for in-flight runners to complete or safely halt; releases held locks and closes DB pools cleanly before process exit.  
  *Source:* Alex Xu & Platform SRE Lead

* **INFRA-13: Next.js Runtime Environment Configuration Contract**  
  *Problem Killed:* Eliminates the build-time inlining trap where `NEXT_PUBLIC_API_URL` hardcodes `localhost:8000` into client bundles.  
  *Acceptance Criteria:* Frontend exposes `/api/config` runtime endpoint or uses dynamic window location derivation for API and WebSocket URLs; container image built once can be promoted across Dev, CI, and Pilot without rebuild.  
  *Source:* Jordan Walke

* **INFRA-14: ADR-005: Concurrency Topology & Worker Fleet Decoupling**  
  *Problem Killed:* Eliminates Defect D3 (Single-Worker Trap) and documents the interim single-worker limit honestly.  
  *Acceptance Criteria:* ADR-005 ratified; codifies strict single-worker `--workers 1` requirement for Phase 0 pilot; defines the Phase 2 transition blueprint to Redis Streams job dispatch and decoupled ARQ/Celery worker processes.  
  *Source:* Alex Xu & Uncle Bob

* **INFRA-15: Distributed Approval Timeout Sweeper Daemon**  
  *Problem Killed:* Kills the bug where pending approvals stay in memory indefinitely if no user clicks approve.  
  *Acceptance Criteria:* Asynchronous background loop runs every 10 seconds; queries all jobs in `PENDING_APPROVAL` status with `created_at < now - 900s`; transitions expired jobs to `TIMEOUT_DENIED`; emits WebSocket event and records `APPROVAL_EXPIRED` in audit ledger.  
  *Source:* Robert C. Martin ("Uncle Bob")

---

### SESSION 4: PERSISTENCE, STATE MIGRATION & CONCURRENCY — MOVING FROM PHANTOM TO REAL SERVICES

**Alex Xu:**  
"Now we come to Defect D2: **Phantom Infrastructure**.
Let us restate the forensic evidence from `backend/app/config.py`:
- `self.lock_manager = RedlockManager(redis_nodes=[])` -> Standalone fallback!
- `self.audit_logger = MerkleAuditLogger(persistence_file="data/audit_ledger.jsonl")` -> Local disk file!
- `self.storage_gateway = S3MultipartGateway(..., mock_mode=True)` -> Fake URLs!
- `self.jobs = self._seed_jobs()` -> Python memory dict!

Meanwhile, `deploy/docker-compose.yml` runs PostgreSQL 16 with the `pgvector` extension.
Look inside `migrations/`:
`001_whiteboard.sql` creates `boards` and `board_updates`.
`002_identity_ai_audit.sql` creates `users`, `workspaces`, `memberships`, `share_links`, and `ai_generations`.
There is not a single table for Project Vulcan! No `vulcan_jobs`, no `vulcan_catalog_items`, no `vulcan_approvals`, no `vulcan_merkle_blocks`.
The database is running, consuming RAM, and completely ignored!

We must execute a disciplined migration sequence from this in-memory simulation to real services:
1. **Alembic Database Migration Baseline:** Initialize Alembic under `backend/alembic/` and write Migration `0001_vulcan_core_schema.py`.
2. **PostgreSQL Schema Definitions:**
   - Table `vulcan_jobs`: `id`, `correlation_id`, `catalog_id`, `requester_id`, `approver_id`, `target_resource_id`, `parameters (JSONB)`, `status (VARCHAR(32))`, `environment`, `version (INT - Optimistic Locking)`, `created_at`, `updated_at`.
   - Table `vulcan_catalog_items`: `id`, `identifier`, `name`, `engine`, `git_repo`, `git_commit_sha`, `playbook_path`, `risk_tier`, `requires_maker_checker`, `input_schema (JSONB)`, `embedding (vector(1536))`.
   - Table `vulcan_audit_ledger`: `sequence (BIGINT GENERATED ALWAYS AS IDENTITY)`, `correlation_id`, `actor_id`, `action`, `payload (JSONB)`, `previous_hash (VARCHAR(64))`, `record_hash (VARCHAR(64) UNIQUE)`, `timestamp`.
3. **Repository Adapter Swapping:** We do not rewrite the domain! We implement `PostgresJobRepository` and `PostgresAuditRepository` conforming to `IJobRepository` and `IAuditRepository` (`BKND-08`, `BKND-09`). When `SIMULATION_MODE=false`, `AppContainer` injects the Postgres adapters."

**Uncle Bob:**  
"I applaud Alex's insistence on the Repository Pattern. Notice the beauty of Clean Architecture here:
`backend/app/domain/entities.py` will not change by a single comma. `ExecutionJob` remains a pure Python dataclass with zero SQL imports.
The mapping between database rows and domain entities occurs exclusively inside `app/adapters/persistence/postgres_job_repository.py`.

And look at the concurrency guarantee we gain: **Optimistic Concurrency Control**.
When Worker A attempts to transition a job from `PENDING_APPROVAL` to `QUEUED`, it issues:
```sql
UPDATE vulcan_jobs 
SET status = 'QUEUED', version = version + 1, updated_at = NOW() 
WHERE correlation_id = :id AND version = :current_version;
```
If Worker B has already approved or rejected the job, the row count affected is 0! The repository raises `ConcurrencyCollisionError` (`ERR_VULCAN_CONCURRENCY_CONFLICT`), and the API returns HTTP 409 Conflict. That completely eliminates race conditions without distributed deadlocks!"

**Andrej Karpathy:**  
"And look at what happens to the catalog and pgvector.
Currently, `backend/app/catalog_data.py` contains 110+ items hardcoded in Python dictionaries.
When we migrate to PostgreSQL:
1. Migration `0002_seed_vulcan_catalog.py` populates `vulcan_catalog_items` from `catalog_data.py`.
2. We create an HNSW vector index on the `embedding` column:
   ```sql
   CREATE INDEX idx_catalog_embedding_hnsw 
   ON vulcan_catalog_items 
   USING hnsw (embedding vector_cosine_ops) 
   WITH (m = 16, ef_construction = 64);
   ```
3. In `resolve_intent.py`, the dense search becomes a single SQL query:
   ```sql
   SELECT id, identifier, name, input_schema, 1 - (embedding <=> :query_vector) AS cosine_sim
   FROM vulcan_catalog_items
   ORDER BY embedding <=> :query_vector
   LIMIT 10;
   ```
Now hybrid search (RRF) combines real pgvector dense retrieval with PostgreSQL `tsvector` sparse retrieval, running entirely inside the database in $<5$ms!"

**Platform SRE Lead (Chair):**  
"And what about MinIO and S3?
In `backend/app/adapters/s3_multipart_adapter.py`, when `mock_mode=False`, the adapter uses `boto3.client('s3')`.
With our `minio-init` provisioner ensuring the bucket exists, the backend can now talk to real S3 storage in both CI and Compose.
We must add an integration contract test suite (`backend/tests/integration/test_adapters_contract.py`) that boots against the Compose stack and asserts:
1. Postgres connection pool initializes and migrations apply cleanly.
2. An audit record written to `PostgresAuditRepository` persists across container restarts.
3. A 50MB file uploaded through `S3MultipartGateway` actually writes chunks to MinIO and returns an HTTP 200 on presigned download.
4. Redis lock acquires and releases with atomic Lua verification.

Let us record the opportunities for Session 4:
* `INFRA-16`: Alembic database migration harness and initial Vulcan schema baseline.
* `INFRA-17`: PostgreSQL persistence adapters (`PostgresJobRepository`, `PostgresAuditRepository`) with optimistic locking.
* `INFRA-18`: pgvector Catalog Schema and database-backed hybrid search.
* `INFRA-19`: Live S3/MinIO multipart contract verification test suite.
* `INFRA-20`: Database connection pooling with Health and Liveness integration."

---

#### SPAWNED OPPORTUNITIES — SESSION 4
* **INFRA-16: Alembic Database Migration Engine & Baseline Vulcan Schema**  
  *Problem Killed:* Eliminates Defect D2 (Phantom Infrastructure) and legacy whiteboard SQL files in `migrations/`.  
  *Acceptance Criteria:* Alembic configured with auto-migration support; migration `0001_vulcan_core_schema.py` creates `vulcan_jobs`, `vulcan_catalog_items`, and `vulcan_audit_ledger`; `alembic upgrade head` executes idempotently in CI.  
  *Source:* Alex Xu

* **INFRA-17: PostgreSQL Production Repository Adapters with Optimistic Locking**  
  *Problem Killed:* Eliminates in-memory job dictionaries (`config.py:41`) and POSIX file lock concurrency collisions.  
  *Acceptance Criteria:* `PostgresJobRepository` and `PostgresAuditRepository` implemented using SQLAlchemy 2.0 async/core; state transitions enforce `WHERE version = :version`; unit and integration tests verify 100% data persistence across process restarts.  
  *Source:* Robert C. Martin ("Uncle Bob") & Alex Xu

* **INFRA-18: pgvector Catalog Schema & Database-Level HNSW Hybrid Search**  
  *Problem Killed:* Eliminates hardcoded dictionary catalog and enables real vector similarity search.  
  *Acceptance Criteria:* `vulcan_catalog_items` stores 1536-dimensional embeddings with HNSW cosine index; hybrid query combines pgvector distance and `tsvector` full-text search; p95 query latency $<15$ms for 1,000 items.  
  *Source:* Andrej Karpathy

* **INFRA-19: Live MinIO/S3 Storage Gateway Contract Suite**  
  *Problem Killed:* Eliminates fake `s3.mock.vulcan.internal` URLs and validates real multipart chunk assembly.  
  *Acceptance Criteria:* Integration test uploads 100MB payload across 2 parts to MinIO container; verifies MD5/SHA-256 ETag checksum; tests abort multipart upload on interrupted client.  
  *Source:* Alex Xu

* **INFRA-20: Resilient Database Connection Pool Management**  
  *Problem Killed:* Prevents socket exhaustion and handles transient DB failovers gracefully.  
  *Acceptance Criteria:* SQLAlchemy connection pool configured with `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, and `pool_recycle=3600`; verifies automatic reconnect after Postgres container restart.  
  *Source:* Platform SRE Lead (Chair)

---

### SESSION 5: OBSERVABILITY & TELEMETRY — METRICS, STRUCTURED LOGS, CORRELATION IDS & AI TRACING

**Platform SRE Lead (Chair):**  
"Now we confront Defect D7: **The Observability Void**.
Right now, if an operator runs a playbook and it hangs, or if the API begins throwing 500 errors, how do we know?
We don't. We have zero Prometheus metrics. There is no `/metrics` endpoint.
Look at our logging:
`backend/app/api/websockets.py:14`: `logger = logging.getLogger("vulcan.ws")`.
Throughout the codebase, logs are plain, unstructured English strings printed to stdout. There is no JSON formatting, no timestamp standardization, no level filtering, and no standard contextual fields.

Worse, look at correlation IDs. An HTTP request comes in with `X-Correlation-ID: corr-abc-123`.
Does that correlation ID get attached to the database query span? No.
Does it get logged in the runner execution thread? No.
Does it get forwarded to the WebSocket event stream? Only if explicitly passed as a string parameter.
If a customer calls PNC SRE reporting a failed playbook, an engineer has to manually grep through gigabytes of raw console text trying to piece together what happened!

And look at the healthcheck endpoint in `backend/app/api/routes.py:98–109`:
```python
@router.get("/health")
def get_health():
    is_audit_valid = container.audit_logger.verify_chain()
    return {"status": "OPERATIONAL", ...}
```
Every time someone hits `/health`, it recalculates the entire Merkle hash chain!
If an SRE or a Kubernetes kubelet pings `/health` every 5 seconds, and the audit log has 10,000 records, the API will spend 100% of its CPU power rehashing SHA-256 blocks! That turns a health probe into a self-inflicted denial of service!"

**Alex Xu:**  
"The healthcheck architecture must be bifurcated immediately according to distributed systems best practices:
1. **Liveness Probe (`/healthz`):**
   A dumb, lightweight endpoint that answers one question: *Is the Python event loop running and responsive?* It returns HTTP 200 `{"status": "ALIVE"}` immediately in $<1$ms without touching the database, Redis, or the audit log.
2. **Readiness Probe (`/readyz`):**
   Answers the question: *Can this process accept user traffic?* It checks:
   - Can we execute `SELECT 1` on PostgreSQL with a 1-second timeout?
   - Can we execute `PING` on Redis with a 500ms timeout?
   - Can we check S3 head-bucket on MinIO?
   If all three succeed, return HTTP 200 `{"status": "READY", "database": "OK", "redis": "OK", "storage": "OK"}`.
   If any critical dependency is down, return HTTP 503 Service Unavailable.
3. **Deep Integrity Diagnostic (`/api/v1/system/audit-integrity`):**
   Move Merkle chain verification to an explicit, authenticated administrative diagnostic endpoint, triggered on-demand or as a background cron drill, never on a liveness probe!"

**Andrej Karpathy:**  
"And what about AI observability?
In `backend/app/use_cases/resolve_intent.py`, we calculate `tokens_used`.
In `test_ai_reasoning_evals.py`, we assert that `tokens_used <= 2500`.
Where does that telemetry go in production? It evaporates into thin air!
In a production automation control plane powered by LLMs, token consumption directly equals cloud expenditure and rate-limit latency.

We must introduce dedicated Prometheus metrics for the AI and governance engine:
- `vulcan_ai_intent_requests_total{status="READY|NEEDS_INPUT|REFUSED"}`
- `vulcan_ai_token_usage_total{model="gpt-4o|claude-3-5|fake", type="prompt|completion"}`
- `vulcan_ai_intent_duration_seconds{status="READY|REFUSED"}`
- `vulcan_ai_adversarial_refusals_total{pattern="injection|override"}`

Furthermore, every AI call must be wrapped in an OpenTelemetry trace span that records:
`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`, and `gen_ai.usage.completion_tokens`.
This allows us to track token drift, cost anomalies, and latency spikes across models and prompt versions."

**Jordan Walke:**  
"From the UI and operator perspective, we need end-to-end trace correlation.
When an operator clicks 'Submit Execution' in Next.js:
1. The frontend generates a UUIDv4 `X-Correlation-ID` and passes it in the HTTP request headers.
2. The FastAPI `CorrelationIdMiddleware` captures `X-Correlation-ID` (or generates one if missing) and attaches it to Python `contextvars`.
3. Every log message emitted during that request automatically includes `{"correlation_id": "...", "service": "vulcan-backend"}`.
4. When the runner spawns, it inherits that correlation ID and includes it in all stdout WebSocket frames: `{"event": "stdout", "correlation_id": "...", "seq": 42}`.
5. In the frontend Obsidian Glass terminal, the operator can click 'Copy Trace ID' to instantly view all correlated backend logs and audit events in a unified timeline.

And let us expose Prometheus metrics for the execution engine itself:
- `vulcan_job_state_transitions_total{from_state, to_state}`
- `vulcan_job_execution_duration_seconds{catalog_id, risk_tier}`
- `vulcan_distributed_lock_wait_seconds{resource_id}`
- `vulcan_maker_checker_approval_age_seconds`"

**Platform SRE Lead (Chair):**  
"Let us formalize this into our platform stack.
We will add `prometheus-fastapi-instrumentator` or standard `prometheus_client` middleware to expose `/metrics` on port 8000.
We will configure `structlog` or standard library JSON logging formatting to stdout so that log collectors (Fluentbit, Promtail, Vector) can parse lines without regex scraping.
And we will establish the OpenTelemetry tracing boundary.

Let us record the opportunities for Session 5:
* `INFRA-21`: Liveness (`/healthz`), Readiness (`/readyz`), and Diagnostic probe bifurcation.
* `INFRA-22`: Prometheus metrics exporter exposing HTTP, execution engine, and Redlock latency.
* `INFRA-23`: AI Token, Cost, and Refusal telemetry instrumentation.
* `INFRA-24`: JSON Structured Logging with standard fields (`timestamp`, `level`, `correlation_id`, `caller`).
* `INFRA-25`: Universal `X-Correlation-ID` propagation middleware across HTTP, WebSockets, and database spans."

---

#### SPAWNED OPPORTUNITIES — SESSION 5
* **INFRA-21: Probe Bifurcation: Lightweight Liveness & Deep Readiness Probes**  
  *Problem Killed:* Eliminates Defect D7 where `/health` pins CPU by re-hashing the entire Merkle ledger on every ping.  
  *Acceptance Criteria:* `/healthz` returns 200 in $<2$ms without DB access; `/readyz` probes PostgreSQL (`SELECT 1`), Redis (`PING`), and MinIO (`head_bucket`) with strict 1s timeouts, returning 503 if dependencies fail; Merkle verification moved to `/api/v1/system/audit-integrity`.  
  *Source:* Alex Xu & Platform SRE Lead

* **INFRA-22: Prometheus Metrics Exporter & Operational Instrumentation**  
  *Problem Killed:* Eliminates lack of operational metrics (Defect D7).  
  *Acceptance Criteria:* Exposes `/metrics` conforming to Prometheus exposition format; tracks HTTP request durations, active jobs count, job transition counters, lock acquisition wait times, and runner execution durations.  
  *Source:* Platform SRE Lead (Chair)

* **INFRA-23: AI Token, Cost, and Refusal Telemetry Instrumentation**  
  *Problem Killed:* Kills untracked LLM costs and invisible working memory overflow in AI intent compilation.  
  *Acceptance Criteria:* Prometheus metrics track prompt/completion tokens, calculated USD cost, intent resolution latency histograms, and adversarial refusal counts by pattern; alerts trigger on budget overrun.  
  *Source:* Andrej Karpathy

* **INFRA-24: Structured JSON Logging Framework**  
  *Problem Killed:* Kills unstructured plain-text logging and enables log aggregator ingestion.  
  *Acceptance Criteria:* 100% of logs formatted as single-line JSON objects containing `timestamp` (ISO-8601 UTC), `level`, `message`, `logger_name`, `correlation_id`, and `process_id`; secrets and auth tokens automatically scrubbed via regex filter.  
  *Source:* Platform SRE Lead (Chair)

* **INFRA-25: End-to-End Correlation ID Propagation Middleware**  
  *Problem Killed:* Eliminates disconnected logs across frontend, API, worker threads, and WebSocket streams.  
  *Acceptance Criteria:* FastAPI middleware injects `X-Correlation-ID` into `contextvars`; propagates to all outgoing HTTP headers, JSON logs, WebSocket log envelopes, and PostgreSQL audit rows.  
  *Source:* Jordan Walke

---

### SESSION 6: RELEASE ENGINEERING, OPERATIONAL DRILLS & DISASTER RECOVERY

**Platform SRE Lead (Chair):**  
"Now we arrive at our final session: **Release Engineering, Operational Drills, and Disaster Recovery (Phase 6)**.
Look at Defect D8:
- No backup or restore scripts exist.
- No rollback procedures have ever been tested.
- No chaos scenarios have ever been executed.
- Phase 0's clean checkout gate has never been validated.

Our PRDs state that Project Vulcan guarantees an RTO (Recovery Time Objective) of under 15 minutes and an RPO (Recovery Point Objective) of zero for audit ledgers.
Gentlemen, in SRE we have an adage: **An untested backup is not a backup; it is merely a wish.**
If PostgreSQL's volume corrupts today, what is our runbook? What script restores it? How long does it take? We have zero answers.

Furthermore, look at our release tagging protocol.
How do we tag a pilot release? An engineer types `git tag v1.0.0-pilot && git push --tags`.
Nothing validates whether all tests passed! Nothing verifies that the Docker images built cleanly! Nothing scans the container images for Known Vulnerabilities and Exposures (CVEs)!
In a Tier-1 financial institution, deploying an un-scanned container containing critical CVEs into a bank pilot environment is a direct regulatory violation under OCC bulletin 2013-29!"

**Uncle Bob:**  
"And what about our AI eval harness in CI?
In `docs/AI_CHAT_SUBSYSTEM_ARCHITECTURE_DEBATE.md`, we talked about golden intent datasets and eval benchmarks.
Look at `backend/tests/test_ai_reasoning_evals.py`:
It has 4 unit test methods testing two hardcoded CatalogItems!
If someone changes a prompt template or tweaks the hybrid RRF weights, how does CI know whether intent resolution accuracy degraded across our 1,000-playbook catalog?
CI cannot call live OpenAI or Anthropic endpoints because network calls in CI are non-deterministic, slow, and leak API keys!

We must have an **Eval Harness as a CI Artifact**:
1. A version-controlled golden dataset: `backend/tests/evals/golden_intents.jsonl` containing 100+ annotated user intents, edge cases, and prompt injection attacks.
2. A `DeterministicFakeChatProvider` that simulates model completions without external network calls.
3. An automated CI job that executes the eval harness and fails if:
   - Slot extraction accuracy falls below 98%.
   - Adversarial prompt injection refusal is $<100\%$.
   - Working memory budget exceeds 2,500 tokens on any test case."

**Andrej Karpathy:**  
"Bob is completely right, and that brings us back to Defect D6: **The Python 3.14 Dependency Wheel Risk**.
Currently, developer laptops are running Python 3.14.6.
If we attempt to introduce advanced grammar-constrained decoding libraries like `outlines` or `guidance`, they depend on `numba` and `llvmlite`.
Numba has NOT released wheels for Python 3.14! When `pip install` runs, it tries to compile LLVM C-extensions from source, which requires 4GB of RAM and LLVM 15 development headers, failing completely on Alpine or slim images!

We must make two architectural decisions here:
1. **Pin Production Runtime to Python 3.12 LTS:**
   Our production Docker images and CI runners must be pinned to **Python 3.12 LTS** (specifically `python:3.12.5-slim-bookworm`). Python 3.12 has universal precompiled binary wheel support across all scientific and AI libraries. We will not run an unreleased or bleeding-edge alpha/beta Python version in a banking control plane!
2. **Pure-Python Grammar Fallback:**
   Even on Python 3.12, our constrained decoding engine must provide a zero-C-extension, pure-Python fallback using `Pydantic` and `Lark` regex state machines. If a compiled library is unavailable, the system degrades gracefully rather than refusing to boot."

**Alex Xu:**  
"Now let us address the Disaster Recovery Drills.
To satisfy our RTO $<15$ minutes and RPO $=0$ audit SLA:
1. **Automated PostgreSQL Backup Script (`scripts/dr-backup.sh`):**
   - Executes `pg_dump` with custom directory format (`-Fd`), compressed, with transaction snapshot consistency (`--single-transaction`).
   - Streams WAL archive segments to the MinIO `vulcan-artifacts/backups/wal/` bucket.
   - Computes SHA-256 checksum of the backup archive and signs it.
2. **Automated Disaster Recovery Restore Drill (`scripts/dr-restore.sh`):**
   - Drops the existing database volume in a test sandbox.
   - Spins up a clean Postgres container.
   - Restores the dump via `pg_restore --clean --if-exists`.
   - Replays WAL segments.
   - Runs `backend/scripts/verify_audit_chain.py` to assert that the Merkle ledger is intact and the tip hash matches the pre-disaster state.
3. **Chaos Drill Suite (`scripts/chaos-drills.sh`):**
   We must test four catastrophic failure modes in CI/Compose:
   - Scenario 1: Abrupt SIGKILL on the runner worker mid-execution. Assert that the watchdog lock expires after 30s and a replacement worker detects the orphaned job.
   - Scenario 2: Redis connection partition (simulate network drop). Assert that the backend fails-closed and refuses to execute un-mutexed playbooks.
   - Scenario 3: Database write failure during `EXEC_START`. Assert that the runner immediately aborts, revokes credentials, and releases locks without touching infrastructure.
   - Scenario 4: S3 multipart upload disconnect at Part 3. Assert that `abort_multipart_upload` is invoked and zero orphaned chunks consume storage."

**Platform SRE Lead (Chair):**  
"And finally, the **Release Tag Protocol**:
We will create a strict GitHub Actions release workflow (`vulcan-release.yml`):
1. A release tag `vX.Y.Z` can ONLY be pushed if all checks in `vulcan-ci.yml` are green on `main`.
2. The release workflow builds the multi-stage Docker images.
3. It executes **Syft** to generate a complete Software Bill of Materials (SBOM) in SPDX and CycloneDX formats.
4. It executes **Trivy** to scan the images for CVEs. If any CRITICAL or HIGH vulnerability without an upstream fix is detected, the release is aborted!
5. It pushes the signed images to the enterprise registry and generates a release artifact package containing the images, the SBOM, the signed checksums, and the Operator Runbook.

Let us record the opportunities for Session 6:
* `INFRA-26`: Production runtime pinning to Python 3.12 LTS and pure-Python grammar fallback.
* `INFRA-27`: Automated CI Eval Harness with Deterministic Fake Model & Golden Dataset.
* `INFRA-28`: Disaster Recovery Backup & Restore Drills with RTO verification.
* `INFRA-29`: Automated Chaos Engineering Drill Harness.
* `INFRA-30`: Release Engineering Pipeline with SBOM generation, Trivy CVE scanning, and Release Tag Protocol."

---

#### SPAWNED OPPORTUNITIES — SESSION 6
* **INFRA-26: Production Runtime Pinning to Python 3.12 LTS & Pure-Python Grammar Fallback**  
  *Problem Killed:* Eliminates Defect D6 (Python 3.14 wheel compilation failures with numba/llvmlite).  
  *Acceptance Criteria:* CI and Dockerfiles pinned to `python:3.12.5-slim-bookworm`; constrained decoding utilizes pure-Python Pydantic/Lark grammar engine without requiring external LLVM C-compilation.  
  *Source:* Andrej Karpathy & Platform SRE Lead

* **INFRA-27: Automated AI Eval Harness & Golden Intent CI Gate**  
  *Problem Killed:* Prevents AI intent compilation regressions from merging into `main`.  
  *Acceptance Criteria:* CI job executes `backend/tests/evals/test_golden_intents.py` against `golden_intents.jsonl` using `DeterministicFakeChatProvider`; asserts $\ge 98\%$ slot extraction accuracy, $100\%$ adversarial refusal, and $\le 2500$ tokens working memory; runs in $<10$s.  
  *Source:* Robert C. Martin ("Uncle Bob") & Andrej Karpathy

* **INFRA-28: Automated Disaster Recovery Backup/Restore Verification Drills**  
  *Problem Killed:* Eliminates unmeasured, theoretical RTO/RPO claims (Defect D8).  
  *Acceptance Criteria:* Scripts `scripts/dr-backup.sh` and `scripts/dr-restore.sh` execute in a scheduled CI job; restores full database from scratch; verifies 100% cryptographic Merkle chain validity; proves RTO $<15$ minutes.  
  *Source:* Platform SRE Lead (Chair) & Alex Xu

* **INFRA-29: Automated Chaos Drill Suite for Infrastructure Failure Modes**  
  *Problem Killed:* Kills unknown failure behaviors under network partitions and process crashes.  
  *Acceptance Criteria:* `scripts/chaos-drills.sh` executes 4 scenarios (worker SIGKILL, Redis partition, DB write drop, S3 abort); asserts fail-closed behavior, lock release, and zero state corruption.  
  *Source:* Alex Xu

* **INFRA-30: Release Gate Protocol, SBOM Generation & Trivy Vulnerability Scanning**  
  *Problem Killed:* Prevents releasing unvetted, vulnerable container images with default credentials to bank pilots.  
  *Acceptance Criteria:* `vulcan-release.yml` triggers on semantic tags; validates green CI; generates CycloneDX SBOM via Syft; runs Trivy vulnerability scan; blocks release on any unpatched CRITICAL/HIGH CVE; signs release bundles with Cosign.  
  *Source:* Platform SRE Lead (Chair)

---

## 2. CONSOLIDATED INFRASTRUCTURE OPPORTUNITY REGISTER

The thirty platform opportunities spawned during the war room debates are indexed, prioritized, and mapped across the Project Vulcan delivery phases (Phase 0: Baseline Reproducibility; Phase 2: Infrastructure & Integration; Phase 6: Production Hardening & Drills):

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         CONSOLIDATED INFRASTRUCTURE OPPORTUNITY REGISTER                                              │
├──────────┬─────────────────────────────────────────────────┬──────────────────────────────────┬──────────────┬──────────┬─────────────┤
│ ID       │ IMPROVEMENT INITIATIVE                          │ DEFECT / PROBLEM KILLED          │ SOURCE       │ PRIORITY │ PHASE       │
├──────────┼─────────────────────────────────────────────────┼──────────────────────────────────┼──────────────┼──────────┼─────────────┤
│ INFRA-01 │ Unified Multi-Stage CI Quality Gate             │ D1: Phantom CI & missing backend │ SRE Lead     │ P0       │ Phase 0     │
│ INFRA-02 │ Hermetic Clean-Checkout Verification Script     │ D8: Undocumented setup steps     │ Uncle Bob    │ P0       │ Phase 0     │
│ INFRA-03 │ Pinned Dependency Locking with Hashes           │ D6: Unpinned requirements (`>=`) │ Uncle Bob    │ P0       │ Phase 0     │
│ INFRA-04 │ Playwright Frontend Landmark Smoke Suite        │ D1: Obsolete `/whiteboard` tests │ Jordan Walke │ P0       │ Phase 0     │
│ INFRA-05 │ CI/Local Environment Parity Engine              │ D1: Mismatched CI service tags   │ Alex Xu      │ P0       │ Phase 0     │
├──────────┼─────────────────────────────────────────────────┼──────────────────────────────────┼──────────────┼──────────┼─────────────┤
│ INFRA-06 │ Hardened Compose Topology & Health Ordering     │ D4: Startup race conditions      │ Alex Xu      │ P0       │ Phase 2     │
│ INFRA-07 │ MinIO Bucket Bootstrap Provisioner (minio-init) │ D2: NoSuchBucket runtime errors  │ Alex Xu      │ P0       │ Phase 2     │
│ INFRA-08 │ 12-Factor Secrets Contract & TruffleHog Scan    │ D5: Hardcoded default passwords  │ SRE Lead     │ P0       │ Phase 0     │
│ INFRA-09 │ Container Resource Limits & Restart Policies    │ D4: Unbounded memory / OOM risk  │ Uncle Bob    │ P1       │ Phase 2     │
│ INFRA-10 │ Rationalised Redis 7.2 Storage Engine ADR       │ D2: Fake 5-node Redlock claims   │ Alex Xu      │ P1       │ Phase 2     │
├──────────┼─────────────────────────────────────────────────┼──────────────────────────────────┼──────────────┼──────────┼─────────────┤
│ INFRA-11 │ Multi-Stage Unprivileged Non-Root Dockerfiles   │ D4: Running as root in dev images│ SRE Lead     │ P0       │ Phase 2     │
│ INFRA-12 │ Graceful Shutdown & Execution Drain Protocol    │ D4: SIGKILL mid-playbook         │ Alex Xu      │ P0       │ Phase 2     │
│ INFRA-13 │ Next.js Standalone Build & Runtime Env Contract │ D4: Build-time env inlining trap │ Jordan Walke │ P0       │ Phase 2     │
│ INFRA-14 │ Single-Worker ADR & Worker Fleet Blueprint      │ D3: Single-worker memory trap    │ Alex Xu      │ P0       │ Phase 2     │
│ INFRA-15 │ Background Approval Timeout Sweeper Daemon      │ D3: Unswept pending approvals    │ Uncle Bob    │ P0       │ Phase 2     │
├──────────┼─────────────────────────────────────────────────┼──────────────────────────────────┼──────────────┼──────────┼─────────────┤
│ INFRA-16 │ Alembic DB Migration Engine & Vulcan Baseline   │ D2: Decorative PostgreSQL DB     │ Alex Xu      │ P0       │ Phase 2     │
│ INFRA-17 │ PostgreSQL Repository Adapters (Optimistic Lock)│ D2: In-memory Python dictionaries│ Uncle Bob    │ P0       │ Phase 2     │
│ INFRA-18 │ pgvector Catalog Schema & HNSW Hybrid Search    │ D2: Hardcoded catalog data       │ Karpathy     │ P0       │ Phase 2     │
│ INFRA-19 │ Live MinIO/S3 Storage Gateway Contract Suite    │ D2: Fake S3 mock URLs            │ Alex Xu      │ P1       │ Phase 2     │
│ INFRA-20 │ Resilient DB Connection Pool Management         │ D2: Socket exhaustion on blips   │ SRE Lead     │ P1       │ Phase 2     │
├──────────┼─────────────────────────────────────────────────┼──────────────────────────────────┼──────────────┼──────────┼─────────────┤
│ INFRA-21 │ Probe Bifurcation: /healthz vs /readyz          │ D7: Health check CPU-pegging     │ Alex Xu      │ P0       │ Phase 2     │
│ INFRA-22 │ Prometheus Metrics Exporter (/metrics)          │ D7: Zero operational metrics     │ SRE Lead     │ P0       │ Phase 6     │
│ INFRA-23 │ AI Token, Cost, and Refusal Telemetry           │ D7: Untracked LLM costs / drift  │ Karpathy     │ P1       │ Phase 6     │
│ INFRA-24 │ Structured JSON Logging Framework               │ D7: Unstructured string logging  │ SRE Lead     │ P1       │ Phase 6     │
│ INFRA-25 │ Universal Correlation ID Propagation Middleware │ D7: Disconnected log traces      │ Jordan Walke │ P1       │ Phase 6     │
├──────────┼─────────────────────────────────────────────────┼──────────────────────────────────┼──────────────┼──────────┼─────────────┤
│ INFRA-26 │ Python 3.12 LTS Pinning & Pure-Python Grammar   │ D6: Python 3.14 wheel failures   │ Karpathy     │ P0       │ Phase 0     │
│ INFRA-27 │ Automated AI Eval Harness & Golden Dataset CI   │ D8: Untested AI regressions      │ Uncle Bob    │ P1       │ Phase 6     │
│ INFRA-28 │ Disaster Recovery Backup/Restore RTO Drills     │ D8: Untested backups & RTO claims│ SRE Lead     │ P0       │ Phase 6     │
│ INFRA-29 │ Automated Chaos Engineering Drill Suite         │ D8: Unknown failure modes        │ Alex Xu      │ P1       │ Phase 6     │
│ INFRA-30 │ Release Pipeline, SBOM & Trivy Vulnerability Scan│ D8: Unverified pilot releases    │ SRE Lead     │ P0       │ Phase 6     │
└──────────┴─────────────────────────────────────────────────┴──────────────────────────────────┴──────────────┴──────────┴─────────────┘
```

---

## 3. ARCHITECTURE DECISION RECORDS (ADRS)

---

### ADR-001: THE ENVIRONMENT MATRIX (LOCAL DEV VS. CI VS. PILOT VM)

```
┌────────────────────────┬──────────────────────────┬──────────────────────────┬──────────────────────────┐
│ DIMENSION              │ LOCAL DEVELOPER SANDBOX  │ GITHUB ACTIONS CI        │ ENTERPRISE PILOT VM      │
├────────────────────────┼──────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Host OS & Arch         │ macOS / Linux (ARM64/x86)│ Ubuntu 22.04 LTS (x86_64)│ RHEL 9 / Rocky Linux 9   │
│ Container Engine       │ Docker Desktop / OrbStack│ Docker Engine (Moby)     │ Podman / Docker Engine   │
│ Compose Topologies     │ deploy/docker-compose.yml│ deploy/docker-compose.yml│ deploy/docker-compose.yml│
│ Python Runtime         │ 3.12.5 (Virtualenv)      │ 3.12.5 (Container)       │ 3.12.5 (Container)       │
│ Node.js Runtime        │ 20.17.0 LTS              │ 20.17.0 LTS              │ 20.17.0 LTS (Build only) │
│ Database Persistence   │ Named Docker Volume      │ Ephemeral Runner Volume  │ Host-Mounted NVMe Volume │
│ Secrets Provisioning   │ Local uncommitted .env   │ GitHub Actions Secrets   │ External Vault / Systemd │
│ Simulation Flag        │ SIMULATION_MODE=true     │ SIMULATION_MODE=true     │ SIMULATION_MODE=false    │
│ External Bank Network  │ DISCONNECTED (Hermetic)  │ DISCONNECTED (Hermetic)  │ PNC DMZ Jump Host        │
└────────────────────────┴──────────────────────────┴──────────────────────────┴──────────────────────────┘
```

---

### ADR-002: COMPOSE TOPOLOGY & HEALTH-CHECK DEPENDENCY GRAPH

```
                                  ┌────────────────────────┐
                                  │   postgres (pg16)      │
                                  │   healthcheck:         │
                                  │   pg_isready -U vulcan │
                                  └───────────┬────────────┘
                                              │
                       ┌──────────────────────┼──────────────────────┐
                       │ service_healthy      │                      │ service_healthy
                       ▼                      ▼                      ▼
           ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
           │   redis (7.2-alpine)  │  │   minio (RELEASE...)  │  │ alembic-migration     │
           │   healthcheck:        │  │   healthcheck:        │  │ (ephemeral job)       │
           │   redis-cli ping      │  │   curl -f :9000/minio/│  │ upgrades schema       │
           └───────────┬───────────┘  │   health/live         │  └───────────┬───────────┘
                       │              └───────────┬───────────┘              │
                       │ service_healthy          │ service_healthy          │ completed_successfully
                       ▼                          ▼                          ▼
                       │              ┌───────────────────────┐              │
                       │              │   minio-init (mc)     │              │
                       │              │   creates bucket      │              │
                       │              │   vulcan-artifacts    │              │
                       │              └───────────┬───────────┘              │
                       │                          │                          │
                       │                          │ completed_successfully   │
                       └──────────────────────────┼──────────────────────────┘
                                                  │
                                                  ▼
                                      ┌───────────────────────┐
                                      │   vulcan-backend      │
                                      │   Uvicorn (1 worker)  │
                                      │   healthcheck:        │
                                      │   curl -f :8000/healthz│
                                      └───────────┬───────────┘
                                                  │
                                                  │ service_healthy
                                                  ▼
                                      ┌───────────────────────┐
                                      │   vulcan-frontend     │
                                      │   Next.js Standalone  │
                                      │   healthcheck:        │
                                      │   wget -q :3000/api/  │
                                      │   health              │
                                      └───────────────────────┘
```

---

### ADR-003: CI/CD PIPELINE STAGE GRAPH (`vulcan-ci.yml`)

```
 [Push / Pull Request to main]
             │
 ┌───────────┴─────────────────────────────────────────┐
 │                                                     │
 ▼                                                     ▼
[Stage 1: Code Hygiene & Static Analysis]  [Stage 2: Frontend Validation]
 ├─ ruff check app/ tests/ (Linting)        ├─ npm ci (Pinned package-lock)
 ├─ mypy --strict app/ (Typecheck)          ├─ tsc --noEmit (0 Type Errors)
 ├─ import-linter (Domain Purity Guard)     ├─ next lint (ESLint Rules)
 └─ trufflehog filesystem (Secret Scan)     └─ next build (Standalone Bundle)
             │                                         │
 ┌───────────┴─────────────────────────────────────────┘
 │ (All Parallel Static Checks Green)
 ▼
[Stage 3: Hermetic Unit & Invariant Suites]
 ├─ pytest tests/test_domain_invariants.py (14-State Transition Matrix)
 ├─ pytest tests/test_policy_engine.py (Maker != Checker RBAC)
 ├─ pytest tests/evals/test_golden_intents.py (AI Intent Eval Harness)
 └─ ./scripts/verify-clean-checkout.sh (Clean Checkout Invariant)
             │
             ▼
[Stage 4: Docker Compose Integration & Adapter Contracts]
 ├─ docker compose up -d (postgres, redis, minio, minio-init)
 ├─ alembic upgrade head (Run migrations against real PostgreSQL 16)
 ├─ pytest tests/integration/ (Live Postgres, Redis, MinIO contract suite)
 ├─ playwright test (Headless browser E2E smoke against frontend & backend)
 └─ docker compose down -v (Clean teardown)
             │
             ▼
[Stage 5: Security Auditing & Artifact Packaging]
 ├─ docker build (Multi-stage unprivileged production images)
 ├─ syft dir:. -o cyclonedx-json > sbom.json (SBOM Generation)
 ├─ trivy image --severity HIGH,CRITICAL (Vulnerability Gate)
 └─ cosign sign-blob (Cryptographic Signing of Artifact Hashes)
```

---

### ADR-004: THE SECRETS CONTRACT & CREDENTIAL ISOLATION

1. **The Core Invariant:** Plaintext credentials shall NEVER be committed to version control, embedded in Docker image layers, or written to Compose files.
2. **Environment Variable Injection Hierarchy:**
   - Level 0 (Hard Constraint): `deploy/docker-compose.yml` uses required variable expansion: `${VAR:?Error: Variable VAR must be set in environment}`.
   - Level 1 (Local Sandbox): Developers generate a local, uncommitted `.env` file via `scripts/bootstrap-env.sh`, which generates high-entropy cryptographic strings (`openssl rand -hex 24`).
   - Level 2 (CI Environment): Secrets injected via GitHub Actions Encrypted Secrets.
   - Level 3 (Pilot VM): Secrets mounted from secure host files (`/etc/vulcan/secrets/.env`) with permissions `0400` owned by `vulcan:vulcan`.
3. **Dynamic PAM Leases:**
   When running in live enterprise mode (`SIMULATION_MODE=false`), backend adapters retrieve transient PAM credentials from CyberArk via REST API. Credentials reside exclusively in heap memory, are marked with a 15-minute lease duration, and are explicitly zeroed out in `finally` teardown blocks.

---

### ADR-005: CONCURRENCY TOPOLOGY & WORKER FLEET DECOUPLING

1. **Context & Problem:**
   The current backend relies on in-memory state:
   - Active jobs dictionary (`config.py:41`).
   - WebSocket stdout ring buffers (`websockets.py:28`).
   - Daemon execution threads spawned inside route handlers (`routes.py:841`).
   Running multiple Uvicorn workers (`uvicorn --workers 4`) immediately causes state fragmentation, 404 errors on approvals, and blank terminal streams.
2. **Interim Decision for Phase 0 Pilot:**
   For Phase 0 and the initial single-host pilot deployment, the backend MUST run as a **single worker process**:
   `uvicorn app.api.server:app --workers 1 --timeout-graceful-shutdown 30`
   This is an explicit, documented architectural constraint. It eliminates split-brain memory partitioning while we complete the database migration.
3. **Phase 2 Target Topology (The Decoupled Worker Fleet):**
   - **Persistence:** All job states and logs are persisted to PostgreSQL and Redis.
   - **Job Dispatch:** The API route enqueues an execution task to a Redis Stream (`vulcan:tasks:queued`).
   - **Worker Fleet:** Dedicated background workers (ARQ/Celery) pull tasks from Redis Streams. The API web process never spawns execution threads.
   - **WebSocket Backplane:** Workers publish stdout chunks to Redis Pub/Sub (`vulcan:logs:{correlation_id}`). Any API worker node can subscribe to Redis Pub/Sub and stream events to connected WebSockets, enabling horizontal API scaling.

---

### ADR-006: MIGRATION SEQUENCE FROM IN-MEMORY TO REAL SERVICES

The transition from simulated in-memory storage to production-grade backing services occurs in four strictly ordered, non-breaking steps:

```
Step 1: Database Schema Creation (INFRA-16)
  └─ Alembic creates `vulcan_jobs`, `vulcan_catalog_items`, and `vulcan_audit_ledger` tables.
  └─ pgvector extension enabled; HNSW index provisioned.

Step 2: Dual-Adapter Implementation (INFRA-17, BKND-08)
  └─ Implement `PostgresJobRepository` and `PostgresAuditRepository` implementing domain ports.
  └─ Pure domain entities (`ExecutionJob`) remain 100% untouched.

Step 3: AppContainer Dynamic Injection (INFRA-17)
  └─ If `DATABASE_URL` is set and `SIMULATION_MODE=false`:
       container.job_repo = PostgresJobRepository(engine)
       container.audit_repo = PostgresAuditRepository(engine)
       container.lock_manager = RedlockManager(redis_nodes=[redis_client])
     Else:
       container.job_repo = InMemoryJobRepository()
       container.audit_repo = MemoryAuditRepository()

Step 4: Deprecation of In-Memory Fallbacks (Phase 6)
  └─ Delete `self.jobs = self._seed_jobs()` from `config.py`.
  └─ Enforce database backing as a hard boot prerequisite.
```

---

## 4. THE PLATFORM MEASUREMENT PLAN

Nothing ships to production unmeasured. Every platform quality attribute must be verified against an automated metric, a target threshold, and an explicit profiling instrument:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           VULCAN PLATFORM MEASUREMENT PLAN                                             │
├────────────────────────────────┬──────────────────────┬────────────────────────────────────────────────────────────────┤
│ METRIC                         │ TARGET THRESHOLD     │ INSTRUMENTATION / PROFILING METHOD                             │
├────────────────────────────────┼──────────────────────┼────────────────────────────────────────────────────────────────┤
│ Clean Checkout Success Rate    │ 100% (Zero Failures) │ CI Job: ./scripts/verify-clean-checkout.sh on fresh container  │
│ Stack Boot-to-Healthy Time     │ < 25.0 seconds       │ docker compose up -d -> probe /readyz until HTTP 200           │
│ CI Pipeline Runtime (Full Gate)│ < 4 minutes 30 sec   │ GitHub Actions workflow execution timer                        │
│ Liveness Probe Latency (p99)   │ < 2.0 ms             │ Locust load test hitting /healthz at 200 RPS                   │
│ Readiness Probe Latency (p95)  │ < 15.0 ms            │ Prometheus: vulcan_probe_duration_seconds{probe="readyz"}      │
│ Disaster Recovery RTO          │ < 15 minutes         │ ./scripts/dr-restore.sh execution duration on test instance    │
│ Disaster Recovery RPO          │ 0 audit records lost │ Cryptographic hash comparison: verify_audit_chain.py           │
│ REST API Latency (p95)         │ < 35.0 ms            │ Prometheus: http_request_duration_seconds                      │
│ Distributed Lock Wait Time     │ < 25.0 ms            │ OpenTelemetry span: redlock_acquire_duration_ms                │
│ Merkle Audit Insert Latency    │ < 10.0 ms            │ SQL execution span: postgres_audit_insert_duration_ms          │
│ 10GB S3 Upload Throughput      │ > 250 MB/second      │ MinIO client benchmark (50MB parts across 8 streams)           │
│ WebSocket Latency (Stdout Lag) │ < 50.0 ms            │ Client-measured time delta between runner emit and xterm paint │
│ Approval Sweeper Precision     │ < 5.0 seconds drift  │ Background sweeper execution timestamp delta                   │
│ AI Intent Accuracy (Golden)    │ >= 98.0% match rate  │ CI Eval Harness: pytest backend/tests/evals/                   │
│ Adversarial Refusal Rate       │ 100.0% refusal rate  │ CI Eval Harness injection attack suite                         │
│ Container Image Vulnerabilities│ 0 Critical, 0 High   │ Trivy security scan in release pipeline                        │
└────────────────────────────────┴──────────────────────┴────────────────────────────────────────────────────────────────┘
```

---

## 5. IRON PLATFORM GUARDRAILS: WHAT THE CONTROL PLANE MUST NEVER DO

To prevent regulatory censure, catastrophic infrastructure outages, or security compromise, the platform infrastructure and release engineering pipeline must strictly adhere to the following **Ten Iron Guardrails**:

1. **NEVER ship default, plaintext, or version-controlled credentials to any environment:** `docker-compose.yml` and all deployment manifests must use strict environment variable substitution. Default passwords like `vulcan_secure_password_2026` must be blocked by pre-commit hooks and CI secret scanning.
2. **NEVER document a manual step as a prerequisite for building or running the system:** Every build, setup, migration, and verification step must be encapsulated in an executable script or Makefile target. If a human has to create a folder or edit a file manually, the build is considered broken.
3. **NEVER claim production readiness from an unisolated developer laptop run:** "It works on my machine" and "60/60 tests pass locally" are zero evidence of production readiness. Reliability is proven exclusively by green, automated CI pipelines running against hermetic container contracts.
4. **NEVER allow unpinned dependencies or floating container tags into deployment artifacts:** Dependencies must specify exact versions with cryptographic hashes (`requirements.lock`, `package-lock.json`). Container images must use immutable patch tags or digest SHAs (`pgvector:pg16`, `redis:7.2.4-alpine`, `node:20.17.0-alpine3.20`), never `:latest`.
5. **NEVER add a Compose or production service without a healthcheck and startup ordering:** Every service must declare a testable health probe. Dependent services must wait on `condition: service_healthy` or `service_completed_successfully`. Zero startup race conditions permitted.
6. **NEVER run container workloads as the `root` superuser:** All Dockerfiles must create an unprivileged system user (`vulcan`, UID 10001) and explicitly switch to `USER vulcan` before executing application code.
7. **NEVER execute long-running execution runners as unmanaged threads inside the API web process:** Uvicorn web workers must remain stateless. Background executions belong to isolated, decoupled worker processes governed by Redis Streams and distributed locks.
8. **NEVER perform heavy O(N) cryptographic hashing inside liveness or readiness probes:** `/healthz` must return in $<2$ms without I/O. `/readyz` must check shallow connectivity (`SELECT 1`). Deep Merkle blockchain verification belongs to dedicated diagnostic endpoints.
9. **NEVER bake environment-specific hostnames into frontend container images:** Next.js containers must be built once and promoted across environments. Configuration must be resolved at runtime via reverse proxy or dynamic config endpoints.
10. **NEVER tag or distribute a release without signed SBOM and CVE gate evidence:** A release tag `vX.Y.Z` requires 100% green CI gates, a Syft-generated CycloneDX SBOM, and a zero-high/critical CVE attestation signed with Cosign.

---

## 6. DEFINITION OF DONE (DoD) PER INFRASTRUCTURE ITEM

Before any item from the Consolidated Infrastructure Opportunity Register (`INFRA-01` through `INFRA-30`) can be closed and merged into `origin/main`, it must satisfy all seven criteria of this Definition of Done:

1. **Code & Configuration Complete:**
   - Manifests, Dockerfiles, scripts, or Python/TypeScript code written cleanly without temporary hacks or commented-out blocks.
   - Pinned versions and non-root execution verified.
2. **Automated CI Verification:**
   - A dedicated GitHub Actions step or test suite validates the item on every PR.
   - Zero regression across existing backend and frontend test suites.
3. **Container Health & Parity:**
   - Works identically across Local Dev, CI runner, and Compose stack.
   - Health probes pass cleanly under `docker compose ps`.
4. **Resilience & Failure Testing:**
   - Failure and restart behavior verified (service gracefully recovers after dependent container restart).
   - Resources clean up cleanly in `finally` blocks (no orphaned locks, no dangling S3 parts).
5. **Telemetry & Observability:**
   - Emits structured JSON logs with correlation IDs.
   - Exposes relevant Prometheus metrics and OpenTelemetry spans where applicable.
6. **Runbook Documentation:**
   - Operational runbook updated under `docs/runbooks/` explaining how an operator inspects, debugs, backs up, or rolls back this component.
7. **Architectural Sign-off:**
   - Reviewed and signed off by the Platform SRE Lead and relevant domain architect (Uncle Bob, Alex Xu, Karpathy, or Walke).

---

### ARCHITECTURAL RATIFICATION & SIGN-OFF

The Architecture Council and Platform Engineering Lead unanimously ratify this Platform Infrastructure, CI/CD, Observability & Release Engineering Masterplan as the binding engineering blueprint for Project Vulcan:

* **Platform SRE Lead (Chair & Owner)** — Runtime Hardening, Observability, CI/CD & Release Lead  
* **Robert C. Martin ("Uncle Bob")** — Clean Architecture, Invariants & Dependency Hygiene Lead  
* **Alex Xu** — Distributed Systems, Storage Topologies & Concurrency Lead  
* **Andrej Karpathy** — LLM Operating System, Eval Harness & AI Infrastructure Lead  
* **Jordan Walke** — Declarative UI, API Contracts & Frontend Build Systems Lead  
