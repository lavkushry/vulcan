# PROJECT VULCAN: ENTERPRISE AUTOMATION CONTROL PLANE
## ARCHITECTURAL WAR ROOM: BACKEND CONTROL PLANE & GOVERNANCE CORE MASTERPLAN
### Rigorous Multi-Perspective Architectural Critique, Forensic Defect Audit, & Consolidated Backend Opportunity Register

**Date:** September 6, 2026  
**Document Version:** 1.0.0-PROD (Forensically Grounded & Authoritative)  
**Classification:** Tier-0 Enterprise Automation Governance & Distributed Control Plane Blueprint  
**Location:** Mission-Critical War Room 4B, Enterprise Engineering Tower  
**Target System:** Project Vulcan Backend Control Plane (`backend/app/` FastAPI, Domain Core, Adapters, Ports, & Workers)  
**Canonical File Path:** `docs/BACKEND_CONTROL_PLANE_ARCHITECTURE_DEBATE.md`  

---

### EXECUTIVE MANDATE & CURRENT-STATE BASELINE

Project Vulcan is a banking-grade Enterprise Automation Control Plane governing the execution of Ansible playbooks and Terraform stacks across Tier-1 financial infrastructure (core transaction databases, F5 BIG-IP edge routing, AWS/Azure cloud landing zones, and enterprise Linux fleets). The system operates under strict regulatory mandates—Sarbanes-Oxley (SOX) §404, OCC Bulletin 2013-29, and NIST SP 800-53 dual-control standards—where unverified, unauthorized, or untracked changes represent catastrophic operational, financial, and legal risk.

Frontend (`UI-01` through `UI-28`) and AI-chat planning debates (`CHAT-01` through `CHAT-26`) have established the operator-facing requirements and intent compilation boundaries. The focus of this war room debate is **THE BACKEND CONTROL PLANE**: the FastAPI service layer, the pure domain state machine, the template-method runner, distributed concurrency primitives, persistence tiers, and external system adapters.

#### The Working Vertical Slice Baseline
A functional vertical slice exists in the codebase today, with 60 tests passing across 8 suites:
1. **Domain Aggregate Root (`backend/app/domain/entities.py`):**
   - Finite state machine with 14 declared statuses (`SUBMITTED` through `REVERTED`).
   - Universal maker-checker guardrails (`requester_id != approver_id`) and 15-minute fail-closed timeout timers (`TIMEOUT_DENIED`).
   - In-memory parameter validation with regex, numeric bounds, and TruffleHog-style secret pattern linting.
2. **Template-Method Runner Pipeline (`backend/app/use_cases/runner.py`):**
   - Ordered invariant execution: State preflight $\rightarrow$ Maintenance window check $\rightarrow$ S3 checksum verification $\rightarrow$ Redlock mutex acquisition $\rightarrow$ JIT PAM secret checkout $\rightarrow$ Synchronous write-before-run audit commit $\rightarrow$ Engine execution $\rightarrow$ Post-flight health probing $\rightarrow$ Rollback on degradation $\rightarrow$ Guaranteed teardown (secret wipe & lock release).
3. **Application & Service Layer (`backend/app/api/routes.py`, `server.py`, `websockets.py`):**
   - FastAPI REST endpoints for health, catalog, intent resolution, task dispatch, job approval/rejection, and manual execution triggers.
   - In-memory WebSocket hub (`WebSocketLogHub`) with sequence numbering and late-joiner replay.
4. **Adapter Integrations (`backend/app/adapters/`):**
   - Distributed mutex simulation (`redlock_adapter.py`) with watchdog lease extension and fencing tokens.
   - S3 multipart chunked upload gateway (`s3_multipart_adapter.py`) partitioning 10GB payloads into 50MB parts.
   - ServiceNow ITSM gateway (`servicenow_adapter.py`) for Change Request validation and maintenance window checks.
   - Merkle audit logger (`crypto_audit_adapter.py`) with SHA-256 block hashing and disk/memory append logs.

---

### FORENSIC AUDIT: THE EIGHT KNOWN ARCHITECTURAL DEFECTS

Before any architect proposes optimizations or scaling patterns, the war room has established the undeniable forensic reality of the current codebase. Every defect listed below has been verified through live code inspection and test execution:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 VULCAN BACKEND FORENSIC DEFECT MATRIX                                            │
├────┬─────────────────────────────┬────────────────────────────────────────────────────────┬─────────────────────┤
│ ID │ DEFECT NAME                 │ CODE LOCATION & FORENSIC EVIDENCE                      │ SEVERITY            │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D1 │ Zero-Score Trap             │ catalog_data.py:1213, 1264-1268; resolve_intent.py:115 │ CRITICAL / BLOCKING │
│    │                             │ Nonsense queries match catalog #0 with 0.65 score.     │                     │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D2 │ Synthetic Governance        │ servicenow_adapter.py:48-57, 66-77                     │ CRITICAL / FRAUD    │
│    │ Illusion                    │ Accepts ANY unknown CHG as valid, CAB-approved & open. │                     │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D3 │ Tautological Token Budget   │ resolve_intent.py:201; test_ai_reasoning_evals.py:79   │ HIGH / UNMEASURED   │
│    │                             │ tokens_used = min(calc, 2500) hard-clamped; test vacuous│                    │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D4 │ Approval RBAC Void          │ routes.py:708-746; roles_and_policies.py:39-77         │ CRITICAL / SOX VIOL │
│    │                             │ No role check on approve endpoint; any user approves.  │                     │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D5 │ Doc-Only AI Ports           │ ports/interfaces.py (0 chat interfaces defined)        │ HIGH / TECHNICAL    │
│    │                             │ IChatModelProvider exists only as markdown pseudocode. │                     │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D6 │ Ephemeral In-Memory State   │ config.py:41; websockets.py:28; routes.py:396          │ CRITICAL / OUTAGE   │
│    │                             │ All state lives in RAM; total loss at 2+ workers.      │                     │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D7 │ Unmigrated pgvector Schema  │ migrations/ (0 vulcan tables); catalog_data.py:26      │ HIGH / TECHNICAL    │
│    │                             │ HNSW vector(1536) catalog exists on paper only.       │                     │
├────┼─────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ D8 │ Python 3.14 Runtime Risk    │ pyproject.toml / runtime env (Python 3.14 alpha/beta)  │ HIGH / COMPATIBILITY│
│    │                             │ Constrained decoding libs lack prebuilt wheels.        │                     │
└────┴─────────────────────────────┴────────────────────────────────────────────────────────┴─────────────────────┘
```

#### Detailed Forensic Proofs:

1. **Defect 1 (The Zero-Score Trap):**
   In `backend/app/catalog_data.py:1212-1213`:
   ```python
   scored_candidates.sort(key=lambda x: x[1], reverse=True)
   best_item, top_score = scored_candidates[0] if scored_candidates else (_MATERIALIZED_ITEMS[0], 1.0)
   ...
   confidence = min(0.98, max(0.65, top_score / 12.0))
   return {"matched": True, "confidence": round(confidence, 2), "catalog_id": best_item["id"], ...}
   ```
   *Forensic Proof:* Executing `find_matching_playbook("xyzzy unknown text 123")` outputs `Matched: True`, `Confidence: 0.65`, selecting `cat-net-001` (F5 SSL Renewal) and pre-filling schema defaults. Furthermore, in `resolve_intent.py:113-122`, the Reciprocal Rank Fusion formula assigns `0.6 / (60 + rank + 1) + 0.4 / (60 + rank + 1)` to every item even if dense and sparse scores are exactly $0.0$. There is zero refusal path.

2. **Defect 2 (The Synthetic Governance Illusion):**
   In `backend/app/adapters/servicenow_adapter.py:46-57`:
   ```python
   def validate_chg(self, chg_number: str) -> Dict[str, Any]:
       if self.mock_mode:
           ticket = self._mock_tickets.get(chg_number)
           if not ticket:
               return {"chg_number": chg_number, "state": "Scheduled", "ci_item": "pnc-prod-infra", "approved_by": "CAB_COMMITTEE"}
   ```
   *Forensic Proof:* Any fabricated string (e.g., `CHG-FAKETICKET-999` or random client-side numbers) is accepted as CAB-approved. Line 77 returns `is_within_maintenance_window = True` unconditionally. The frontend fabricates random CHG numbers (`ChatAssistant.tsx:259`), and the backend accepts them. Frontend and backend collude in fake governance.

3. **Defect 3 (The Tautological Token Budget):**
   In `backend/app/use_cases/resolve_intent.py:199-201`:
   ```python
   prompt_tokens = len(prompt.split()) * 2
   schema_tokens = len(str(schema).split())
   total_tokens = min(400 + prompt_tokens + schema_tokens + 150, 2500)
   ```
   *Forensic Proof:* Because `min(..., 2500)` is hard-clamped in code, `test_ai_reasoning_evals.py:79` (`self.assertLessEqual(res.tokens_used, 2500)`) can never fail under any prompt size. There is no tokenizer, no context overflow detection, and no real budget enforcement.

4. **Defect 4 (The Approval RBAC Void):**
   In `backend/app/api/routes.py:707-746`:
   ```python
   @router.post("/jobs/{correlation_id}/approve")
   def approve_job(correlation_id: str, req: ApproveJobRequest):
       ...
       job.apply_approval_decision(decision, datetime.now(timezone.utc), timeout_seconds=900)
   ```
   *Forensic Proof:* The route only checks `job.apply_approval_decision`, which verifies `approver_id != requester_id`. Neither the route nor the domain entity checks `roles_and_policies.py`. When tested with an unprivileged identity `random.unprivileged.operator`, the endpoint returns HTTP 200 and transitions the job to `QUEUED`.

5. **Defect 5 (Doc-Only AI Ports):**
   In `backend/app/ports/interfaces.py`, there are classes for `ILockManager`, `ISecretProvider`, `IAuditLogger`, `IServiceNowGateway`, `IObjectStorageGateway`, `IHealthProbeGateway`, and `IExecutionEngine`. There is **zero** interface for chat models. `IChatModelProvider` and `DeterministicFakeChatProvider` exist solely as markdown pseudocode in prior documentation.

6. **Defect 6 (Ephemeral In-Memory State):**
   In `backend/app/config.py:41`: `self.jobs = self._seed_jobs()`.
   In `backend/app/api/websockets.py:28`: `self.buffers: Dict[str, List[Dict]] = {}`.
   In `backend/app/adapters/redlock_adapter.py:180`: `self._fallback_locks: Dict[str, tuple] = {}`.
   *Forensic Proof:* Every active job, event buffer, and lock fallback lives in Python process RAM. Starting Uvicorn with `--workers 4` partitions state across 4 memory spaces: a job created on Worker 1 cannot be found or approved on Worker 2, and WebSocket streams on Worker 3 receive zero events.

7. **Defect 7 (Unmigrated pgvector Schema):**
   The repository contains two legacy SQL files (`001_whiteboard.sql`, `002_identity_ai_audit.sql`) belonging to a whiteboard application. There are zero migrations for Project Vulcan. The 110+ catalog items are hardcoded in `catalog_data.py`. The `vector(1536)` HNSW schema exists only as PRD text.

8. **Defect 8 (Python 3.14 Runtime Compatibility Risk):**
   The active virtual environment runs Python 3.14.0a. Packages requiring C-extensions or LLVM bindings (e.g., `outlines` and `guidance` depending on `numba` and `llvmlite`) have no precompiled binary wheels for Python 3.14. A constrained decoding implementation that relies on uncompilable C-extensions will brick CI and production builds.

---

### EXPLICIT NON-GOALS (THE IRON BOUNDARY)

To preserve banking governance and prevent scope dilution, the backend control plane strictly enforces the following **Five Non-Goals**:
1. **No Production Bank Access from Local/CI Environments:** The backend control plane will never connect directly to production core banking networks, live CyberArk vaults, or corporate ServiceNow production instances during testing or local development. All adapters must support local contract-verified testcontainers.
2. **Simulated Adapters are NEVER Evidence of Production Reliability:** A test passing against `mock_mode=True` proves code syntax only; it provides zero evidence of distributed reliability. No adapter is certified production-ready without passing Docker-Compose contract suites under simulated packet loss, network partitions, and latency injection.
3. **No Autonomous Approvals, Executions, or Retries:** The system shall never allow an AI agent, script, or automated background worker to approve its own change, transition a high-risk job to `QUEUED`, or autonomously retry failed production executions without human checker authorization.
4. **No Direct Execution on API Process Nodes:** The FastAPI Uvicorn process shall never execute Ansible playbooks, Terraform CLIs, or heavy shell commands directly. Execution belongs exclusively to an isolated, sandboxed worker fleet.
5. **No Unbounded Memory Buffers or Payload Proxies:** The API layer shall never proxy multi-gigabyte files (S3 multipart uploads go directly from client/worker to object storage via presigned URLs) or maintain unbounded in-memory log arrays.

---

### THE WAR ROOM PARTICIPANTS

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   WAR ROOM 4B PARTICIPANT MATRIX                                       │
├───────────────────────┬──────────────────────────────────────┬─────────────────────────────────────────┤
│ ARCHITECT             │ PRIMARY LENS                         │ ATTACK SURFACE IN VULCAN BACKEND        │
├───────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────┤
│ Robert C. Martin      │ Clean Architecture, Domain Purity,   │ Leaking frameworks into domain; partial │
│ ("Uncle Bob")         │ Invariants & Testability             │ audit commits; bypassable maker-checker;│
│                       │                                      │ clobbered states; unprincipled errors   │
├───────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────┤
│ Alex Xu               │ Distributed Systems, Concurrency,    │ 2+ worker collapse; split-brain locks;  │
│                       │ Capacity & Failure Modes             │ orphaned leases; Little's Law sizing;   │
│                       │                                      │ WS dual-write buffers; connection pools │
├───────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────┤
│ Andrej Karpathy       │ AI Boundary Engineering, Model       │ Zero-score trap; tautological budgets;  │
│                       │ Ports, Evals & Constrained Decoding  │ fake ServiceNow hydration; doc-only     │
│                       │                                      │ ports; log windowing; Python 3.14 risk  │
├───────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────┤
│ Jordan Walke          │ API as Single Source of Truth,       │ Missing error envelopes; idempotency    │
│                       │ Idempotency, Cursor Pagination & WS  │ voids; O(N) memory listing; contract    │
│                       │                                      │ drift; UI forced to compute policy      │
└───────────────────────┴──────────────────────────────────────┴─────────────────────────────────────────┘
```

---

## 1. THE ARCHITECTURAL DEBATE SESSIONS

---

### SESSION 1: THE DOMAIN AND THE FROZEN STATE MACHINE

**Uncle Bob:**  
"Gentlemen, look at `backend/app/domain/entities.py`. On the surface, it looks like Clean Architecture: `ExecutionJob` has zero imports from FastAPI and zero imports from SQLAlchemy. But when you inspect the invariant enforcement, the structural discipline breaks down into wishful thinking.

First, look at `backend/tests/test_domain_invariants.py:573`:
```python
def test_low_risk_job_bypasses_maker_checker(self):
    job.parse()
    job.transition_to(JobStatus.QUEUED, "Low risk bypasses Maker-Checker gate")
```
Who authorized a 'low-risk bypass'? In banking automation, there is no such thing as an unverified execution touching infrastructure. But worse, look at `BaseJobRunner.run` in `backend/app/use_cases/runner.py:63-67`:
```python
if job.status not in (JobStatus.QUEUED, JobStatus.PARSED):
    if job.catalog_item.risk_tier == RiskTier.HIGH and job.status != JobStatus.QUEUED:
        raise StateTransitionError(...)
```
Look at that conditional! If the job is `RiskTier.LOW` or `RiskTier.MEDIUM`, it allows the runner to execute directly from `PARSED`! But then look at line 116: `job.transition_to(JobStatus.LOCKED)`. In `entities.py:168`, `PARSED` can only transition to `PENDING_APPROVAL`, `QUEUED`, or `FAILED`. It CANNOT transition to `LOCKED`! The runner crashes at step 4 with a `StateTransitionError`! Our code is in open contradiction with its own state machine!

Second, look at our exceptions in `backend/app/domain/exceptions.py`. Ten empty exception classes inheriting from `DomainError(Exception)`. Not a single one carries a machine-readable error code, a structured details dictionary, or a suggested HTTP status code. When `ParameterValidationError` is raised, it outputs a raw English string that Jordan's frontend is forced to scrape with regex.

Third, look at `runner.py:73-81` and `105-113`:
```python
except Exception:
    pass
```
When a maintenance window is closed or a resource is locked, the runner attempts to write an `EXEC_BLOCKED` record to the audit logger, and if that write throws an exception, it swallows it with `pass`! A silent audit failure in a SOX-governed banking control plane! If the audit ledger is unavailable, the system must FAIL-CLOSED immediately. It must never proceed, and it must never silently swallow audit write failures!"

**Alex Xu:**  
"Bob, you want an absolute freeze on the state machine, but you have to acknowledge the concurrency realities. Look at the transition matrix `entities.py:166-181`. You have 14 states:
`SUBMITTED` $\rightarrow$ `PARSED` $\rightarrow$ `PENDING_APPROVAL` $\rightarrow$ `QUEUED` $\rightarrow$ `LOCKED` $\rightarrow$ `RUNNING` $\rightarrow$ `VERIFYING` $\rightarrow$ `SUCCESS` / `FAILED` / `DEGRADED` $\rightarrow$ `REVERTING` $\rightarrow$ `REVERTED`.

What happens when two workers attempt to transition the same job concurrently? In-memory, `job.transition_to()` is a Python method mutating an in-memory string. There is no row-level locking, no optimistic concurrency token (`version` or `updated_at`), and no database transaction. If Worker A marks the job `FAILED` due to a probe error while Worker B is processing a cancellation request, you have a race condition where the terminal state depends entirely on the Python GIL!

And look at the declared states `REVERTING` and `REVERTED`. In `runner.py:161-175`, automated rollback is triggered ONLY IF `job.catalog_item.rollback_path` is populated. If `rollback_path` is `None`, line 181 raises `HealthProbeDegradedError`, leaving the job in `DEGRADED`. But in `routes.py:818`, the exception handler receives `HealthProbeDegradedError` and marks the job with whatever is in `job.status.value`! The API layer does not know how to handle `DEGRADED` vs `FAILED`!"

**Jordan Walke:**  
"From the API and UI perspective, Bob is completely right about error codes. Look at what happens right now when an approval fails. If an operator tries to approve their own job, `routes.py:731` catches `MakerCheckerViolationError` and does:
`raise HTTPException(status_code=403, detail=str(e))`
The response body is:
`{"detail": "Separation of Duties Violation: Requester [eng.alice] cannot approve their own change."}`
How is my frontend supposed to render an internationalized, accessible banner from that? I have to parse the string 'Separation of Duties Violation'! 

Every single exception in `backend/app/domain/exceptions.py` must declare:
1. `error_code: str` (e.g., `ERR_VULCAN_MAKER_CHECKER_VIOLATION`, `ERR_VULCAN_RESOURCE_LOCKED`)
2. `message: str` (human-readable summary)
3. `details: Dict[str, Any]` (machine-readable fields like `requester_id`, `approver_id`, `resource_id`, `retry_after_sec`)
4. `http_status: int` (400, 403, 404, 409, 422, 423)

And look at the state machine: why does `entities.py` have two different methods for approval? `apply_approval_decision` (lines 240-273) and `enforce_maker_checker` (lines 274-304)! Why do we have two methods doing almost the same thing with slightly different error messages and signatures? That is dead code waiting to cause a bug."

**Andrej Karpathy:**  
"And look at where `PARSED` comes from. In `entities.py:229-232`, `job.parse()` simply transitions from `SUBMITTED` to `PARSED`. But where does parameter extraction and validation happen? In `entities.py:218`, `self._validate_parameters()` runs inside `__init__`! That means a job cannot even be instantiated in `SUBMITTED` status if its parameters are invalid! 
If someone submits an unparsed or partial intent from the chat console, the Python constructor throws `ParameterValidationError` immediately, returning an HTTP 422. The state `SUBMITTED` is practically unreachable in a persistent store because validation runs in `__init__`!

We must separate:
1. Job creation/submission (recording the operator's raw intent and ambient payload).
2. Compilation and parsing (validating against the catalog schema, checking regex patterns, scanning secrets).
3. Governance evaluation (Maker-Checker, ServiceNow CHG validation, maintenance window verification)."

**Uncle Bob:**  
"Agreed. Here are the non-negotiable domain rules:
1. **Domain Purity:** `app/domain/` must import nothing outside the Python Standard Library (`dataclasses`, `datetime`, `enum`, `re`, `hashlib`, `typing`). No FastAPI, no Pydantic, no Redis, no SQLAlchemy. CI must enforce this with an `import-linter` AST boundary check.
2. **Unified Approval Method:** Delete `enforce_maker_checker`. Consolidate all approval logic into `apply_approval_decision(decision, evaluated_at, timeout_seconds=900)`.
3. **Maker-Checker Invariant:** No execution touching infrastructure bypasses dual-control unless the catalog item explicitly defines `risk_tier == RiskTier.LOW` AND `requires_maker_checker == False`, AND that transition must be logged to the audit ledger as `APPROVAL_BYPASSED_LOW_RISK`.
4. **Frozen State Transition Matrix:** Any transition outside the 14-state directed acyclic graph raises `StateTransitionError` with code `ERR_VULCAN_ILLEGAL_STATE_TRANSITION`.
5. **No Swallowed Audit Failures:** If `self.audit.record()` fails, the runner MUST abort immediately and raise `AuditIntegrityError` (`ERR_VULCAN_AUDIT_WRITE_FAILED`)."

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             FROZEN DOMAIN STATE TRANSITION MATRIX                                │
├───────────────────┬──────────────────────────────────────────────────────────────────────────────┤
│ CURRENT STATE     │ LEGAL TARGET STATES                                                          │
├───────────────────┼──────────────────────────────────────────────────────────────────────────────┤
│ SUBMITTED         │ PARSED, FAILED                                                               │
│ PARSED            │ PENDING_APPROVAL, QUEUED (Low Risk Only), FAILED                             │
│ PENDING_APPROVAL  │ QUEUED, REJECTED, TIMEOUT_DENIED, FAILED                                     │
│ QUEUED            │ LOCKED, FAILED                                                               │
│ LOCKED            │ RUNNING, FAILED                                                              │
│ RUNNING           │ VERIFYING, FAILED                                                            │
│ VERIFYING         │ SUCCESS, DEGRADED, FAILED                                                    │
│ DEGRADED          │ REVERTING, FAILED                                                            │
│ REVERTING         │ REVERTED, FAILED                                                             │
│ SUCCESS           │ (Terminal State)                                                             │
│ FAILED            │ (Terminal State)                                                             │
│ TIMEOUT_DENIED    │ (Terminal State)                                                             │
│ REJECTED          │ (Terminal State)                                                             │
│ REVERTED          │ (Terminal State)                                                             │
└───────────────────┴──────────────────────────────────────────────────────────────────────────────┘
```

#### SPAWNED OPPORTUNITIES — SESSION 1
* **BKND-01: Freeze Domain State Machine & Transition Matrix**  
  *Problem Killed:* Eliminates illegal state jumps, removes redundant approval methods (`enforce_maker_checker`), and establishes deterministic transition enforcement across all 14 states.  
  *Acceptance Criteria:* Transition matrix table codified as an immutable mapping; unit test suite tests all $14 \times 14 = 196$ state pairs, asserting that exactly 17 legal transitions succeed and all 179 illegal transitions raise `StateTransitionError` with code `ERR_VULCAN_ILLEGAL_STATE_TRANSITION`.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **BKND-02: Universal Exception Hierarchy & Machine-Readable Error Codes**  
  *Problem Killed:* Kills unstructured string exceptions in `domain/exceptions.py`. Eliminates string scraping in frontend and API layers.  
  *Acceptance Criteria:* Every domain exception subclasses `VulcanDomainError` and defines `error_code`, `message`, `http_status`, and `details` dictionary. 100% of API endpoints translate domain exceptions into uniform `{error_code, message, details, timestamp, request_id}` JSON envelopes.  
  *Source:* Jordan Walke & Uncle Bob

* **BKND-03: Zero-Tolerance Audit Failure Invariant (No Swallowed Audit Writes)**  
  *Problem Killed:* Kills `except Exception: pass` around `self.audit.record` in `runner.py:80` and `111`. Ensures no execution proceeds if audit storage fails.  
  *Acceptance Criteria:* Any failure in `self.audit.record` during `EXEC_BLOCKED`, `EXEC_START`, or `EXEC_SUCCESS` immediately halts execution, releases acquired locks, and raises `AuditIntegrityError` (`ERR_VULCAN_AUDIT_WRITE_FAILED`).  
  *Source:* Robert C. Martin ("Uncle Bob")

* **BKND-04: Domain Purity & stdlib-Only Boundary Enforcement in CI**  
  *Problem Killed:* Prevents framework contamination (FastAPI, SQLAlchemy, Pydantic, Redis) inside `app/domain/`.  
  *Acceptance Criteria:* AST import linter runs in CI; fails if any file under `app/domain/` imports anything outside Python standard library.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **BKND-05: Post-Flight Probe State Preservation (DEGRADED / REVERTING / REVERTED)**  
  *Problem Killed:* Kills bug where post-flight probe failures are clobbered into generic `FAILED` status by API route exception handlers.  
  *Acceptance Criteria:* When post-flight health probes fail, jobs transition strictly to `DEGRADED` (if no rollback) or `REVERTING` $\rightarrow$ `REVERTED` (if rollback succeeds). Terminal state is preserved and emitted over WebSocket without being overwritten to `FAILED`.  
  *Source:* Robert C. Martin ("Uncle Bob")

---

### SESSION 2: PERSISTENCE: THE LEDGER THAT CANNOT LIE & MULTI-WORKER REALITY

**Alex Xu:**  
"Gentlemen, now we must confront Defect 6. The current backend is an in-memory toy. Look at `config.py:41`:
`self.jobs = self._seed_jobs()`
It is a plain Python dictionary `jobs: Dict[str, ExecutionJob]`. 

Now consider what happens in production. You run `uvicorn main:app --workers 4` behind an NGINX load balancer. 
1. Alice submits a job. The request hits Worker 1. Worker 1 writes the job to its local heap `jobs['EXEC-1001']`.
2. Bob gets an email, opens the console, and clicks 'Approve'. Bob's HTTP request hits Worker 2. Worker 2 looks up `jobs.get('EXEC-1001')`. It returns `None`! Worker 2 throws HTTP 404: `Job not found`!
3. The WebSocket connection from the browser lands on Worker 3. Worker 3 has an empty `ws_hub.buffers['EXEC-1001']`. The operator sees a blank terminal!
4. The approval timeout sweeper (if it existed) running in Worker 4 knows nothing about jobs in Workers 1, 2, or 3.

The moment you scale beyond a single Python process, the current architecture suffers a catastrophic split-brain collapse!

And look at our audit ledger in `backend/app/adapters/crypto_audit_adapter.py`. The file locking using `fcntl.flock` (lines 81-135) only works if all workers share a single local POSIX filesystem! In Kubernetes or AWS ECS, where pods run across distinct nodes, `fcntl` file locking is completely non-functional! You cannot flock across a network unless you use NFS with lock daemons, which is notoriously prone to deadlocks and data corruption!

We must introduce an authoritative persistence architecture:
1. **PostgreSQL 16+ as Single Source of Truth:** `jobs`, `catalog_items`, `approval_decisions`, and `audit_ledger` must live in relational tables with foreign keys and ACID transactions.
2. **Optimistic Locking:** Every job row must have an integer `version` column. Any state transition updates with `WHERE id = :id AND version = :current_version`. If another worker updated the job first, the query affects 0 rows, and we raise a concurrency collision.
3. **Cryptographic Audit Ledger Table:** The Merkle hash chain must be written to an append-only PostgreSQL table with a sequence generator, where `current_hash = sha256(correlation_id + timestamp + actor + action + payload + prev_hash)`."

**Uncle Bob:**  
"Alex, I agree with PostgreSQL and Redis, but you must not let database tables contaminate our domain entities. We must use the **Repository Pattern** and **Unit of Work Pattern**.
Our domain entities—`ExecutionJob`, `CatalogItem`, `AuditRecord`—must remain pure Python dataclasses. 

We define domain ports in `app/ports/repositories.py`:
```python
class IJobRepository(abc.ABC):
    @abc.abstractmethod
    def get_by_id(self, job_id: str) -> Optional[ExecutionJob]: pass
    @abc.abstractmethod
    def save(self, job: ExecutionJob) -> None: pass

class IAuditRepository(abc.ABC):
    @abc.abstractmethod
    def append(self, record: AuditRecord) -> None: pass
    @abc.abstractmethod
    def get_last_record(self) -> Optional[AuditRecord]: pass
```
Then, in `app/adapters/persistence/`, we implement `PostgresJobRepository` and `PostgresAuditRepository` using SQLAlchemy 2.0 Core or asyncpg. The domain use cases interact ONLY with the interface. When we run unit tests, we inject `InMemoryJobRepository`. When we run in production, we inject `PostgresJobRepository`. Nothing in the domain knows SQL exists!"

**Jordan Walke:**  
"And look at what this does for query performance. In `backend/app/api/routes.py:303-354`, the `high_filtered_tasks` endpoint loops over `container.jobs.values()` in memory, performs string containment searches in Python, sorts in memory, and slices by offset!
At 10,000 jobs, that endpoint will consume 100% CPU and block the Python event loop for hundreds of milliseconds!

With a proper PostgreSQL schema:
1. Multi-dimensional filtering (`engine`, `status`, `environment`, `category`) maps to indexed SQL `WHERE` clauses.
2. Search queries execute against PostgreSQL `tsvector` full-text search indexes (`tsv @@ to_tsquery(...)`), returning in sub-5ms.
3. Pagination becomes efficient keyset/cursor pagination (`WHERE created_at < :cursor ORDER BY created_at DESC LIMIT 50`), eliminating slow `OFFSET` scans."

**Andrej Karpathy:**  
"And what about Defect 7—the unmigrated catalog and pgvector?
Look at `backend/app/catalog_data.py`. We have 110+ items hardcoded in Python dictionaries. We need an Alembic migration that creates:
1. `catalog_items` table with columns: `id`, `identifier`, `name`, `engine`, `git_repo`, `git_commit_sha`, `playbook_or_module_path`, `risk_tier`, `requires_maker_checker`, `requires_chg`, `input_schema` (JSONB), `category`, `tags` (text array).
2. A pgvector column: `embedding vector(1536)`.
3. An HNSW index: `CREATE INDEX catalog_hnsw_idx ON catalog_items USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`.

When catalog items are committed to Git, a seed CLI loads them, computes embeddings, and stores them in PostgreSQL. The catalog is no longer hardcoded Python data!"

**Alex Xu:**  
"Let's also resolve the audit write ordering tension: **lock-then-audit vs write-before-execute**.
In `runner.py:104-135`, step 4 acquires the lock, step 5 checks out credentials, and step 6 writes `EXEC_START` to the audit ledger.
Why is this ordering critical?
Because if you write `EXEC_START` *before* acquiring the lock, and the lock acquisition fails because the resource is busy, you have committed an `EXEC_START` record for an execution that never started! That corrupts the audit ledger!
The invariant must be:
1. Validate state and maintenance window.
2. If blocked, commit `EXEC_BLOCKED` to audit ledger and abort.
3. Acquire distributed lock.
4. Check out ephemeral secrets.
5. **Synchronously commit `EXEC_START` to the audit ledger.** If this database write fails, revoke secrets, release lock, and abort!
6. Execute the engine.
7. Commit `EXEC_SUCCESS`, `EXEC_DEGRADED`, or `EXEC_FAILED` to the audit ledger.
8. Release lock and revoke secrets in `finally` block."

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             POSTGRESQL CONTROL PLANE SCHEMA TOPOLOGY                             │
├───────────────────────┬──────────────────────────────────────────────────────────────────────────┤
│ TABLE                 │ CORE COLUMNS & CONSTRAINTS                                               │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ catalog_items         │ id (PK, text), identifier (UQ), name, engine, git_commit_sha (char 40),  │
│                       │ risk_tier, requires_mc (bool), schema (jsonb), embedding (vector(1536))  │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ execution_jobs        │ id (PK, text), correlation_id (UQ), catalog_id (FK), requester_id,       │
│                       │ approver_id, target_resource, parameters (jsonb), status (enum),         │
│                       │ version (int, optimistic lock), created_at, started_at, completed_at     │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ approval_decisions    │ id (PK, uuid), job_id (FK), approver_id, decision (enum), reason,        │
│                       │ chg_number, decided_at, approval_token (char 64, HMAC-SHA256)            │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ audit_ledger          │ sequence (BIGINT GENERATED ALWAYS AS IDENTITY PK), correlation_id,       │
│                       │ actor, action, payload (jsonb), prev_hash (char 64), current_hash        │
│                       │ (char 64 UQ), committed_at (timestamptz)                                 │
└───────────────────────┴──────────────────────────────────────────────────────────────────────────┘
```

#### SPAWNED OPPORTUNITIES — SESSION 2
* **BKND-06: PostgreSQL Persistence Migration & Repository Domain Ports**  
  *Problem Killed:* Kills Defect 6 (in-memory job store). Ensures all jobs, catalog items, and state survive restarts and scale across multi-worker clusters without split-brain.  
  *Acceptance Criteria:* `IJobRepository` port implemented via SQLAlchemy 2.0 Core over PostgreSQL 16; zero in-memory dictionaries for core entities; jobs persist across process restarts; optimistic locking via `version` column prevents concurrent overwrite.  
  *Source:* Alex Xu & Uncle Bob

* **BKND-07: Alembic Migration Pipeline & pgvector HNSW Catalog Schema**  
  *Problem Killed:* Kills Defect 7 (designed but unmigrated schema). Moves catalog out of Python memory into PostgreSQL with pgvector HNSW index.  
  *Acceptance Criteria:* Alembic migration suite creates `catalog_items`, `execution_jobs`, `approval_decisions`, and `audit_ledger`; `catalog_items` includes `embedding vector(1536)` with HNSW index (`m=16`, `ef_construction=64`); seed CLI embeds 110+ items into database.  
  *Source:* Andrej Karpathy & Alex Xu

* **BKND-08: Cryptographic PostgreSQL Merkle Audit Ledger**  
  *Problem Killed:* Replaces flawed single-process `fcntl` file-locked audit logger with an immutable, sequence-checked PostgreSQL table.  
  *Acceptance Criteria:* `IAuditLogger` implemented via `PostgresAuditLogger`; records committed with strict sequence monotonicity; `verify_chain()` SQL procedure recalculates hash chain over 100,000 records in $<500\text{ms}$; any mutated record detected with 100% precision.  
  *Source:* Alex Xu & Uncle Bob

* **BKND-09: Synchronous Write-Before-Run Audit Verification (Iron Gate 6)**  
  *Problem Killed:* Prevents engine execution if the audit ledger is unreachable or degraded.  
  *Acceptance Criteria:* Runner template method enforces that `EXEC_START` is committed to PostgreSQL audit table before runner spawns engine subprocess; if database write fails, runner revokes PAM lease, releases lock, and aborts with `AuditIntegrityError`.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **BKND-10: Database-Backed Keyset Cursor Pagination & TSVector Search**  
  *Problem Killed:* Eliminates $O(N)$ Python memory scanning and sorting in `routes.py:303-354`.  
  *Acceptance Criteria:* `GET /api/v1/tasks` executes indexed PostgreSQL queries with keyset cursor pagination (`cursor = base64(created_at, id)`); response latency p95 $<25\text{ms}$ over 50,000 jobs; search queries utilize `to_tsvector('english', ...)`.  
  *Source:* Jordan Walke & Alex Xu

---

### SESSION 3: LOCKS, LEASES, FENCING, AND THE ORPHAN PROBLEM

**Alex Xu:**  
"Now let us dissect distributed mutual exclusion. Look at `backend/app/adapters/redlock_adapter.py`.
There are two critical distributed systems bugs in this file:

Bug 1: **Compare-and-Delete Ownership Proof Bypass:**
Look at lines 224-243:
```python
elif resource_id in self._fallback_locks:
    expiry, cur_owner, _ = self._fallback_locks[resource_id]
    now = time.time()
    if owner_token is not None:
        if cur_owner != owner_token:
            return False
        ...
    del self._fallback_locks[resource_id]
    return True
```
Look at that `if owner_token is not None:`!
If the caller invokes `lock_mgr.release("f5-vip-01")` without passing `owner_token`—which is optional in the interface `release(resource_id, owner_token=None)`—the adapter unconditionally deletes the lock! Anyone can release anyone else's lock without proof of ownership! A lock that can be deleted without ownership proof is not a lock; it is a suggestion!

Bug 2: **The Multi-Worker Mutex Illusion:**
In `RedlockManager` (lines 178-198), `self._active_mutexes` is a Python dictionary in process RAM:
`self._active_mutexes[resource_id] = mutex`
If Worker 1 acquires the lock via Redis, it starts a watchdog thread stored in Worker 1's `_active_mutexes`. 
If Worker 1 crashes (`kill -9` or OOM), the watchdog thread dies. But what happens to the lock key in Redis?
It remains in Redis until `lease_ms` (30 seconds) expires. But what if Worker 2 is waiting to run? Worker 2 cannot release the lock because it does not possess the `lock_value` UUID generated by Worker 1!
Even worse: if Worker 1 is killed while a long-running Terraform job is executing on a remote runner node, and the Redis lease expires after 30 seconds, Worker 2 can acquire the lock for the *same resource* and begin modifying the *same infrastructure* concurrently! This is Martin Kleppmann's classic critique of Redlock in action: without monotonic fencing tokens verified at the storage or target resource, distributed locks cannot guarantee safety under GC pauses or process stalls!"

**Uncle Bob:**  
"Alex is spot-on. The domain port `ILockManager` in `backend/app/ports/interfaces.py:24-30` states:
*'Safely releases lock on resource_id using atomic compare-and-delete. Guarantees that expired locks held by other workers are never deleted.'*
Yet the interface signature made `owner_token: Optional[str] = None`! That was a catastrophic interface design error.
`owner_token` MUST BE MANDATORY on `release()`. It is not optional. You cannot release a lock unless you present the exact cryptographically random token returned during `acquire()`.

Furthermore, look at the S3 multipart upload adapter in `backend/app/adapters/s3_multipart_adapter.py`.
In lines 31-100, `initiate_multipart_upload` calculates 50MB chunks and creates presigned URLs.
In lines 101-127, `complete_multipart_upload` calls `s3_client.complete_multipart_upload`.
Where is `abort_multipart_upload`? It does not exist!
If a worker crashes after uploading 5 chunks of a 10GB payload, those 250MB of chunks sit in S3 storage forever, accumulating AWS storage charges indefinitely. In a bank running thousands of jobs per week, orphaned multipart parts will leak terabytes of ghost storage!"

**Alex Xu:**  
"Exactly. Here is the complete distributed locking and storage lifecycle we must implement:

1. **Mandatory Ownership & Atomic Compare-and-Delete Lua Script:**
   The Lua script in `redlock_adapter.py:17-23` is correct:
   ```lua
   if redis.call("get", KEYS[1]) == ARGV[1] then
       return redis.call("del", KEYS[1])
   else
       return 0
   end
   ```
   Every lock acquisition returns an `owner_token` (`f"{uuid4().hex}:{worker_id}"`). The `release` method requires `owner_token` as a positional argument. If the token does not match, Redis returns 0, and the adapter logs an unauthorized release attempt.

2. **Monotonic Fencing Tokens:**
   Every time a lock is acquired on `resource_id`, Redis atomically executes `INCR token:resource:{resource_id}`. This integer is the **fencing token** (e.g., `4102`). 
   When the runner calls CyberArk, ServiceNow, or Ansible, it passes the fencing token. If a delayed write arrives with token `4101` when the current token is `4102`, the downstream target rejects the request!

3. **Orphaned Lock Recovery & Heartbeat Watchdog:**
   The watchdog thread in `redlock_adapter.py:113-138` runs every 10 seconds (`lease_ms / 3`) executing `LUA_EXTEND_SCRIPT`. 
   If the runner worker process dies, the watchdog stops renewing the lease. The Redis key automatically expires after 30 seconds. 
   When a new worker attempts to acquire the lock after 30 seconds, Redis permits acquisition.

4. **S3 Multipart Lifecycle, Checksums, and Auto-Abort:**
   - The S3 adapter must implement `abort_multipart_upload(upload_id, s3_key)`.
   - The bucket must enforce an S3 Lifecycle Configuration Rule: `AbortIncompleteMultipartUpload` after 3 days.
   - Every completed upload must verify the `ETag` checksum and the full-file SHA-256 before the runner transitions the job to `RUNNING`."

**Jordan Walke:**  
"And what does the UI see during all of this? In the frontend audit debate, we found that `RadarPulse.tsx` and `TerminalActionBar.tsx` were simulating lock heartbeat pulses using a client-side `setInterval`!
The API must expose lock truth! When the UI polls or streams `GET /api/v1/jobs/{id}`, the response must contain:
```json
"lock_telemetry": {
  "resource_id": "f5-vip-01",
  "is_locked": true,
  "fencing_token": 4102,
  "lease_expires_in_sec": 24,
  "watchdog_active": true
}
```
The frontend can then render genuine distributed telemetry, not a hallucinated timer."

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           DISTRIBUTED MUTEX & FENCING ARCHITECTURE                               │
│                                                                                                  │
│   Worker Process 1                          Redis 7.2 Cluster                 Target Resource    │
│   ┌───────────────────┐                     ┌───────────────────┐             ┌────────────────┐ │
│   │ 1. SETNX resource │ ── px=30000,val ──> │ lock:res:f5-01    │             │                │ │
│   │ 2. INCR token_key │ ──────────────────> │ token:res:f5-01=42│             │                │ │
│   │ 3. Watchdog Thread│ ── pexpire every ──>│ (Lease renewed)   │             │                │ │
│   │    (Daemon)       │    10 seconds       │                   │             │                │ │
│   │ 4. Dispatch Job   │ ────────────────────────────────────────────────────> │ Check Token:42 │ │
│   │    with Token 42  │                     │                   │             │ [ACCEPTED]     │ │
│   │                   │                     │                   │             │                │ │
│   │ [Process Crash] ☠ │                     │                   │             │                │ │
│   │ Watchdog dies     │                     │ (30s TTL expires) │             │                │ │
│   └───────────────────┘                     │ Lock evaporated   │             │                │ │
│                                             └───────────────────┘             │                │ │
│   Worker Process 2                                                            │                │ │
│   ┌───────────────────┐                     ┌───────────────────┐             │                │ │
│   │ 5. SETNX resource │ ── px=30000,val ──> │ lock:res:f5-01    │             │                │ │
│   │ 6. INCR token_key │ ──────────────────> │ token:res:f5-01=43│             │                │ │
│   │ 7. Dispatch Job   │ ────────────────────────────────────────────────────> │ Check Token:43 │ │
│   │    with Token 43  │                     │                   │             │ [ACCEPTED]     │ │
│   └───────────────────┘                     └───────────────────┘             └────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### SPAWNED OPPORTUNITIES — SESSION 3
* **BKND-11: Mandatory Lock Ownership & Atomic Compare-and-Delete Verification**  
  *Problem Killed:* Kills the vulnerability in `redlock_adapter.py:228` where locks could be deleted without ownership tokens.  
  *Acceptance Criteria:* `ILockManager.release(resource_id, owner_token)` requires `owner_token: str` as a non-optional argument; atomic Lua release script executed across Redis cluster; attempting release with invalid or mismatched token returns `False` and emits a security alert log.  
  *Source:* Alex Xu & Uncle Bob

* **BKND-12: Monotonic Distributed Fencing Tokens**  
  *Problem Killed:* Prevents stale execution writes after process stalls or GC pauses (Kleppmann fencing hazard).  
  *Acceptance Criteria:* Redis `INCR` generates monotonic integers upon lock acquisition; runner injects fencing token into execution payload and audit log; target execution adapters reject tasks with stale tokens.  
  *Source:* Alex Xu

* **BKND-13: Watchdog Heartbeat Lease Extension with Process Death Guard**  
  *Problem Killed:* Prevents premature lock expiration during legitimate 20-minute Terraform deployments while ensuring dead workers release locks within 30 seconds.  
  *Acceptance Criteria:* Background watchdog thread executes Lua `pexpire` every `lease_ms / 3`; terminates immediately on job completion or exception; if worker process dies, lock naturally evaporates within 30 seconds without manual intervention.  
  *Source:* Alex Xu

* **BKND-14: S3 Multipart Upload Abort, Lifecycle Rules, & Checksum Gate**  
  *Problem Killed:* Prevents orphaned S3 multipart chunk leakage and verifies 10GB payload integrity before execution.  
  *Acceptance Criteria:* S3 gateway implements `abort_multipart_upload`; S3 bucket provisioned with 72-hour incomplete multipart cleanup lifecycle policy; `verify_artifact_checksum` validates full SHA-256 before worker unpacks payload.  
  *Source:* Alex Xu & Uncle Bob

* **BKND-15: Lock Telemetry Projection in Job API Model**  
  *Problem Killed:* Kills client-side fake `setInterval` lock radar simulations in the UI.  
  *Acceptance Criteria:* `GET /api/v1/jobs/{id}` returns `lock_telemetry` object containing active lock status, holder, fencing token, and remaining TTL in seconds.  
  *Source:* Jordan Walke

---

### SESSION 4: THE EXECUTION PLANE: SIMULATION HONESTY, FAIL-CLOSED ADAPTERS, & FLEET CAPACITY

**Uncle Bob:**  
"Now we come to Defect 2: **The Synthetic Governance Illusion**.
Look at `backend/app/adapters/servicenow_adapter.py:48-57`.
When `validate_chg("CHG-NONEXISTENT")` is called, what does it do?
It returns:
```python
return {
    "chg_number": chg_number,
    "state": "Scheduled",
    "ci_item": "pnc-prod-infra",
    "approved_by": "CAB_COMMITTEE"
}
```
And line 77 returns `True` for `is_within_maintenance_window`!
Do you realize what this means? If an attacker or a negligent operator sends ANY arbitrary string in `servicenow_chg`, the mock adapter accepts it as scheduled, CAB-approved, and within the maintenance window!
And look at `frontend/components/ChatAssistant.tsx:259`:
`servicenow_chg: ... || 'CHG-' + Math.floor(100000 + Math.random() * 900000)`
The frontend generates a random fake change number, the backend mock accepts it, and our test suite awards itself 60 green checks! We have built an automated control plane that colludes in fake governance!

And that is not all. Look at `backend/app/api/routes.py:408-450`, the `dispatch_task` endpoint.
When an operator launches a task from the launch card, what does `dispatch_task` do?
Does it call `BaseJobRunner.run`? **NO!**
Lines 414-450 define an inline, local function `run_simulation()` that calls `time.sleep()`, logs hardcoded fake ANSI text, and marks `job.status = SUCCESS`!
It never calls CyberArk! It never checks the maintenance window! It never acquires a Redlock! It never writes an audit record! It logs a fake message:
`ws_hub.emit_log(..., 'Synchronous pre-run cryptographic commit hash: ...')`
It logs that a hash was committed without ever calling `container.audit_logger.record()`!
Our API layer is literally faking execution and faking audit logging!"

**Alex Xu:**  
"That is an extraordinary forensic catch, Bob. `dispatch_task` completely circumvents `runner.py`! We have a robust, tested `BaseJobRunner` with 12 governance steps in `runner.py`, and the main route used by the Chat UI simply ignores it and runs a toy `time.sleep` thread!

And let's talk about execution capacity. In `routes.py:826`, when `trigger_execution` is called, it does:
```python
thread = threading.Thread(target=run_worker, daemon=True)
thread.start()
```
It spawns an unconstrained OS thread directly inside the Uvicorn web process!
Now let's do the capacity math. Project Vulcan is mandated to support **75 concurrent active runners** across Ansible and Terraform.
Let us apply **Little's Law**:
$$L = \lambda \times W$$
Where:
- $L$ = Average concurrency in the system (75 active jobs)
- $W$ = Average job duration ($60\text{ seconds}$ for a typical F5 cert renewal or VM patch)
- $\lambda$ = Arrival throughput:
$$\lambda = \frac{L}{W} = \frac{75\text{ jobs}}{60\text{ sec}} = 1.25\text{ jobs/second} = 75\text{ jobs/minute}$$

If each active job runs as a native OS thread inside the Uvicorn container:
1. Each Python thread running an Ansible/Terraform runner consumes 50MB to 200MB of RAM. 75 threads consume $75 \times 150\text{MB} \approx 11.25\text{GB}$ of memory!
2. The Python Global Interpreter Lock (GIL) stalls async I/O in FastAPI. The Uvicorn event loop latency spikes, causing health check timeouts and dropping WebSocket connections!
3. If the Uvicorn container restarts due to an OOM or rolling deployment, all 75 jobs are violently terminated mid-flight! Infrastructure is left in an indeterminate, partially modified state!

We must completely decouple the API control plane from the Execution Data Plane:
1. The FastAPI web processes only handle HTTP, validation, RBAC, and dispatch.
2. When a job is approved, FastAPI publishes a job message to **Redis Streams** or a **Celery/ARQ queue** (`vulcan:job:queue`).
3. An independent worker fleet of **Celery/ARQ runner workers** pulls jobs from the queue. The worker fleet is autoscaled based on queue depth.
4. If an API process crashes, the worker fleet continues executing. If a runner worker crashes, Redis Streams redelivers the message after visibility timeout, triggering fencing token validation and recovery."

**Andrej Karpathy:**  
"And let us fix the ServiceNow mock adapter so it is honest.
The mock adapter must have two modes:
1. **Deterministic Test Fixtures:** Pre-seeded with known valid tickets (`CHG001`, `CHG002`) and known expired/rejected tickets (`CHG_EXPIRED`, `CHG_REJECTED`).
2. **Fail-Closed Default:** If ANY unknown change number is passed (e.g., `CHG-FAKETICKET`), the adapter must return:
```json
{
  "valid": false,
  "state": "UNKNOWN_TICKET",
  "error": "Change Request [CHG-FAKETICKET] not found in ServiceNow CMDB."
}
```
And `is_within_maintenance_window` MUST return `False` for unknown tickets!
If the ticket is not verified, the runner must fail-closed into `MaintenanceWindowClosedError` (`ERR_VULCAN_MAINTENANCE_CLOSED`). No fake approvals. No fake windows."

**Jordan Walke:**  
"And `dispatch_task` must be completely rewritten. When an operator clicks 'Launch' in the UI:
1. It must submit the job to `POST /api/v1/jobs`.
2. If Maker-Checker is required, it enters `PENDING_APPROVAL`.
3. When approved, it delegates strictly to `runner.run(job)`.
The entire `run_simulation()` function in `routes.py` must be deleted. Every execution must pass through the identical, invariant-enforcing `BaseJobRunner` template method pipeline."

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             DECOUPLED EXECUTION FLEET TOPOLOGY                                   │
│                                                                                                  │
│   FastAPI Web Cluster (Uvicorn)            Redis 7.2 Core                   Execution Worker Fleet│
│   ┌─────────────────────────────┐         ┌─────────────────────┐          ┌───────────────────┐ │
│   │ POST /jobs/{id}/approve     │ ──────> │ Stream:             │ ───────> │ Worker Node 1     │ │
│   │ [RBAC Check: PASS]          │         │ vulcan:job:dispatch │          │ BaseJobRunner     │ │
│   │ [Transition -> QUEUED]      │         └─────────────────────┘          │ Ansible/Terraform │ │
│   └─────────────────────────────┘                    │                     └───────────────────┘ │
│                                                      │                                           │
│   WebSocket Fleet                                    │                     ┌───────────────────┐ │
│   ┌─────────────────────────────┐         ┌─────────────────────┐          │ Worker Node 2     │ │
│   │ WS /ws/jobs/{id}/logs       │ <────── │ Pub/Sub Channel:    │ <─────── │ BaseJobRunner     │ │
│   │ (Subscribes to Redis ch)    │         │ vulcan:ws:{id}      │          │ (Emits stdout)    │ │
│   └─────────────────────────────┘         └─────────────────────┘          └───────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### SPAWNED OPPORTUNITIES — SESSION 4
* **BKND-16: Fail-Closed Honest ServiceNow & CMDB Adapter**  
  *Problem Killed:* Kills Defect 2 (synthetic governance illusion). Prevents fake tickets from bypassing governance.  
  *Acceptance Criteria:* `ServiceNowGateway` mock mode rejects all unknown ticket numbers with `valid: false`; returns `is_within_maintenance_window = False` for unverified tickets; runner throws `MaintenanceWindowClosedError` on fabricated tickets; contract tests verify rejection.  
  *Source:* Robert C. Martin ("Uncle Bob") & Andrej Karpathy

* **BKND-17: Kill routes.py Fake Simulation & Route All Dispatches via BaseJobRunner**  
  *Problem Killed:* Deletes the fake `run_simulation()` bypass in `routes.py:414-450`. Ensures 100% of tasks execute through the audited, locked runner pipeline.  
  *Acceptance Criteria:* `run_simulation()` deleted from `routes.py`; `dispatch_task` delegates strictly to `container.create_runner().run(job)` or enqueues to execution fleet; all executions verified to acquire Redlock, check out CyberArk secrets, and commit to Merkle audit ledger.  
  *Source:* Robert C. Martin ("Uncle Bob") & Jordan Walke

* **BKND-18: Decoupled Worker Fleet for 75 Concurrent Runners (Little's Law)**  
  *Problem Killed:* Eliminates raw, unconstrained `threading.Thread` spawning in the API process. Protects FastAPI event loop from memory bloat and GIL stalls under 75 concurrent jobs.  
  *Acceptance Criteria:* Execution jobs enqueued to Redis Streams (`vulcan:job:dispatch`); handled by a standalone worker process pool sized for 75 concurrent workers; API process memory footprint remains $<250\text{MB}$ under peak load.  
  *Source:* Alex Xu

* **BKND-19: Real CyberArk PAM Vault Adapter with Ephemeral In-Memory Checkout**  
  *Problem Killed:* Replaces hardcoded mock secrets with an honest CyberArk Central Credential Provider (CCP) REST adapter.  
  *Acceptance Criteria:* `CyberArkPAMProvider` checks out credentials into RAM only; zero persistence to disk; guarantees lease revocation in `BaseJobRunner.run` `finally` block; contract test verifies credentials purged even on SIGTERM/unhandled exceptions.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **BKND-20: Automated Rollback Execution & Verification Rail**  
  *Problem Killed:* Ensures that when post-flight health checks fail on a job with a defined `rollback_path`, the rollback executes deterministically and commits `EXEC_REVERTED`.  
  *Acceptance Criteria:* Subclass executes `_execute_rollback`; verified by integration test asserting `job.status == JobStatus.REVERTED`, audit ledger contains `EXEC_REVERTED`, and ServiceNow ticket work notes state 'Execution degraded & reverted'.  
  *Source:* Robert C. Martin ("Uncle Bob")

---

### SESSION 5: THE API BOUNDARY AS CONTRACT: SINGLE STATE SOURCE, RBAC, & IDEMPOTENCY

**Jordan Walke:**  
"Now let us examine the API boundary. The REST and WebSocket APIs are not just HTTP routes; they are the **Single Source of Truth** for the entire user interface. Look at the defects in `backend/app/api/routes.py`:

Defect 4: **The Approval RBAC Void:**
Look at `routes.py:708-727`:
```python
@router.post("/jobs/{correlation_id}/approve")
def approve_job(correlation_id: str, req: ApproveJobRequest):
    decision = ApprovalDecision(
        decision=req.decision.upper(),
        approver_id=req.approver_id,
        ...
    )
    job.apply_approval_decision(...)
```
There is NO authentication header inspection, NO JWT validation, and NO check against `roles_and_policies.py`!
In `backend/app/domain/roles_and_policies.py:39-77`, we spent hundreds of lines defining `UserRole.OPERATOR`, `UserRole.APPROVING_LEAD`, and granular permissions like `Permission.JOB_APPROVE`.
Yet in `routes.py`, that entire policy engine is completely bypassed! Any caller can pass `approver_id: "random.user"` in the JSON body, and as long as `approver_id != requester_id`, the job is approved!
This is a fatal violation of Sarbanes-Oxley dual-control compliance!

Next: **Idempotency Keys on Job Creation:**
Look at `routes.py:365`, `POST /tasks/dispatch`, and lines 375-376:
```python
job_id = f"task-{uuid.uuid4().hex[:6]}"
correlation_id = f"EXEC-{uuid.uuid4().hex[:4].upper()}"
```
If an operator on a slow network double-clicks the 'Submit' button, or if an automated proxy retries a timed-out POST, the backend generates two completely distinct `correlation_id` values and dispatches two identical executions to the same database tablespace or F5 VIP!
Every mutation endpoint—`POST /jobs`, `POST /tasks/dispatch`, `POST /jobs/{id}/approve`—must require an `Idempotency-Key` header! If a request arrives with an existing key within 24 hours, the backend must return the cached response without re-executing!"

**Uncle Bob:**  
"Jordan is entirely right. Look at the RBAC failure. In Clean Architecture, authorization is an application-layer use case policy. We must implement an `ApproveJobUseCase`:
```python
class ApproveJobUseCase:
    def __init__(self, job_repo: IJobRepository, policy_mgr: PolicyManager, audit: IAuditLogger): ...
    
    def execute(self, job_id: str, approver_role: UserRole, approver_id: str, reason: str):
        if not self.policy_mgr.has_permission(approver_role, Permission.JOB_APPROVE):
            raise UnauthorizedRoleError(f"Role [{approver_role}] lacks JOB_APPROVE permission.")
        job = self.job_repo.get(job_id)
        job.apply_approval_decision(...)
```
The FastAPI route simply extracts the authenticated user's role from the verified JWT/mutual-TLS token, passes it to the use case, and handles the result. The route contains zero business logic, and the domain remains pristine."

**Alex Xu:**  
"And look at our WebSocket architecture in `backend/app/api/websockets.py`.
`ws_hub = WebSocketLogHub()`.
It is a process-local singleton with an in-memory dictionary `self.buffers`.
If we have 4 Uvicorn workers, and Worker 1 runs the job while Worker 2 terminates the client's WebSocket, how do the log events get from Worker 1 to Worker 2?
Right now, they don't! Worker 2's socket remains silent!

To fix this, we need a **WebSocket Dual-Write via Redis**:
1. When a runner emits a log line via `ws_hub.emit_log(correlation_id, line)`, it performs a dual write:
   - It appends the event to a Redis List: `RPUSH log:buffer:{correlation_id} json_entry`.
   - It publishes the event to a Redis Pub/Sub channel: `PUBLISH log:channel:{correlation_id} json_entry`.
2. When a WebSocket client connects to ANY Uvicorn worker:
   - The worker reads missed historical logs from the Redis List: `LRANGE log:buffer:{correlation_id} {last_seq} -1`.
   - The worker subscribes its local asyncio queue to the Redis Pub/Sub channel for live events.
3. If the WebSocket connection drops and reconnects with `?last_seq=42`, the worker replays lines from $43$ onwards. Zero missed lines, zero memory leaks, and 100% horizontal scalability across any number of Uvicorn workers!"

**Jordan Walke:**  
"And what about the API responses rendering policy, not forcing the UI to compute it?
In `ARCHITECTURE_DEBATE_UI_OPPORTUNITIES.md`, we attacked `TaskMatrixTable.tsx` for computing `isRequester = currentUser === task.requester_id` inline in React.
The reason the frontend did that is because `routes.py` never provided a `capabilities` object!
Every `JobResponse` emitted by `GET /jobs/{id}` or `GET /tasks` must include an explicit **Humble ViewModel**:
```json
"capabilities": {
  "can_approve": false,
  "can_reject": false,
  "can_execute": false,
  "can_cancel": true,
  "disabled_reasons": {
    "approve": "Current user is the job requester (Separation of Duties enforced)",
    "execute": "Job requires Maker-Checker approval before execution"
  }
}
```
The UI becomes a completely Humble Object. It simply binds `button.disabled = !capabilities.can_approve`, rendering the disabled reason in the tooltip. The UI never computes policy again!"

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             REDIS WEBSOCKET DUAL-WRITE ARCHITECTURE                              │
│                                                                                                  │
│   Worker Node (Runner)                          Redis 7.2 Core             API Node (Uvicorn)    │
│   ┌─────────────────────────────┐              ┌───────────────────┐       ┌───────────────────┐ │
│   │ emit_log("EXEC-101", line)  │ ── RPUSH ──> │ List:             │       │ Client Connects:  │ │
│   │                             │              │ log:buf:EXEC-101  │ <───  │ LRANGE from seq   │ │
│   │                             │              └───────────────────┘       │ (Late Join Replay)│ │
│   │                             │              ┌───────────────────┐       ├───────────────────┤ │
│   │                             │ ── PUBLISH ─>│ Channel:          │ ────> │ Async Redis Sub   │ │
│   │                             │              │ log:ch:EXEC-101   │       │ pushes to client  │ │
│   └─────────────────────────────┘              └───────────────────┘       └───────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### SPAWNED OPPORTUNITIES — SESSION 5
* **BKND-21: Mandatory RBAC & Separation-of-Duties Enforcement on Approval Routes**  
  *Problem Killed:* Kills Defect 4 (approval RBAC void). Prevents unauthorized or unprivileged users from approving changes.  
  *Acceptance Criteria:* `/api/v1/jobs/{id}/approve` and `/reject` verify caller identity and role; rejects any user lacking `Permission.JOB_APPROVE` (`APPROVING_LEAD` or `PLATFORM_ADMIN`) with HTTP 403; asserts caller $\ne$ requester; returns `ERR_VULCAN_RBAC_FORBIDDEN`.  
  *Source:* Robert C. Martin ("Uncle Bob") & Jordan Walke

* **BKND-22: Distributed Idempotency Keys on Mutation Routes**  
  *Problem Killed:* Prevents double-execution and duplicate job creation from network retries or double-clicking.  
  *Acceptance Criteria:* `POST /jobs`, `POST /tasks/dispatch`, and `POST /jobs/{id}/approve` require `Idempotency-Key` header; cached in Redis via `SET key val NX EX 86400`; duplicate requests return identical HTTP response with `X-Cache: IDEMPOTENT-HIT`.  
  *Source:* Jordan Walke & Alex Xu

* **BKND-23: Redis-Backed WebSocket Dual-Write & Late-Joiner Replay Hub**  
  *Problem Killed:* Kills split-brain WebSocket log loss across multiple Uvicorn workers.  
  *Acceptance Criteria:* `WebSocketLogHub` writes logs to Redis List (`RPUSH`) and Pub/Sub channel (`PUBLISH`); connecting WebSockets replay missed lines via `LRANGE` using `last_seq`; verified across 4 independent Uvicorn worker processes with zero dropped lines.  
  *Source:* Alex Xu & Jordan Walke

* **BKND-24: Standardized Error Envelope ({error_code, message, details})**  
  *Problem Killed:* Eliminates raw string parsing and disparate error formats in the frontend.  
  *Acceptance Criteria:* Global FastAPI exception handlers intercept all domain and validation errors; guarantee 100% of non-2xx responses adhere to `{error_code: str, message: str, details: dict, timestamp: str, request_id: str}`.  
  *Source:* Jordan Walke

* **BKND-25: Authoritative Capabilities & Policy Projection in Job ViewModels**  
  *Problem Killed:* Prevents frontend components from computing policy logic (`currentUser === requester_id`) in JSX.  
  *Acceptance Criteria:* Job API models return `capabilities` dictionary containing `can_approve`, `can_reject`, `can_execute`, and explicit `disabled_reasons` strings evaluated by backend policy engine for the requesting user context.  
  *Source:* Jordan Walke & Uncle Bob

---

### SESSION 6: AI PORTS, EVALS, AND THE FAKE MODEL

**Andrej Karpathy:**  
"Now we enter the AI subsystem inside the backend. We have three severe architectural defects to confront:
1. Defect 1: **The Zero-Score Trap** in `catalog_data.py:1213` and `resolve_intent.py:115`.
2. Defect 3: **The Tautological Token Budget** in `resolve_intent.py:201`.
3. Defect 5: **Doc-Only AI Ports** in `ports/interfaces.py`.

Let's dissect the Zero-Score Trap. In `resolve_intent.py:97-123`, we implemented Reciprocal Rank Fusion:
```python
for rank, item in enumerate(dense_ranked):
    rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + (0.6 / (k + rank + 1))
for rank, item in enumerate(sparse_ranked):
    rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + (0.4 / (k + rank + 1))
```
Notice what happens when an operator inputs utter gibberish, such as `'xyzzy unknown text 123'`:
- The dense similarity score for all 110 items is $0.0$.
- The BM25 sparse score for all 110 items is $0.0$.
- Yet, because `dense_ranked` and `sparse_ranked` stably sort all 110 items, item #0 receives:
$$\text{RRF} = \frac{0.6}{60 + 0 + 1} + \frac{0.4}{60 + 0 + 1} = \frac{1.0}{61} \approx 0.01639$$
Then `ranked[0]` is selected as `best_item`!
Then line 1264 in `catalog_data.py` computes:
`confidence = min(0.98, max(0.65, top_score / 12.0))`
It clamps the minimum confidence to **0.65**! And line 1267 hardcodes `'matched': True`!
The system confidently declares that the operator wants to renew an F5 SSL certificate with 65% confidence, pre-fills default IP addresses, and asks for the missing days!
There is **zero refusal path** for out-of-catalog queries! In a banking environment, that is completely unacceptable.

We must implement a **Calibrated Refusal Gate**:
1. Raw BM25 and dense cosine similarity must be evaluated *before* RRF.
2. If `max(dense_score) < 0.35` AND `max(sparse_score) == 0.0`, the resolver must fail-closed immediately:
   `status = "REFUSED"`, `refusal_reason = "Out-of-catalog intent: No playbook matches query with sufficient confidence."`
3. If two playbooks have close scores ($\Delta_{\text{score}} < 0.05$), the resolver must return `status = "DISAMBIGUATION_REQUIRED"`."

**Uncle Bob:**  
"And look at Defect 5: the doc-only ports.
In `backend/app/ports/interfaces.py`, there is no chat port!
If you cannot mock the LLM boundary, you cannot test the backend in a CI pipeline without burning API tokens and introducing non-deterministic latency!
We must define a formal domain port:
```python
class IChatModelProvider(abc.ABC):
    @abc.abstractmethod
    def complete(self, messages: List[Dict[str, str]], schema: Optional[Dict[str, Any]] = None, temperature: float = 0.0) -> str: pass

    @abc.abstractmethod
    def count_tokens(self, text: str) -> int: pass
```
Then, we create two adapters:
1. `DeterministicFakeChatProvider` (for CI and unit testing): returns deterministic pre-recorded JSON completions for known golden prompts, with microsecond latency and zero cost.
2. `OpenAIChatProvider` / `AnthropicChatProvider` (for production): wraps real LLM APIs with timeout, retries, and circuit breakers."

**Jordan Walke:**  
"And what about Defect 3, the token budget?
Look at `resolve_intent.py:201`:
`total_tokens = min(400 + prompt_tokens + schema_tokens + 150, 2500)`
It literally uses the `min()` function with `2500` as the upper bound!
Then `test_ai_reasoning_evals.py:79` asserts:
`self.assertLessEqual(res.tokens_used, 2500)`
A test that checks whether `min(x, 2500) <= 2500` is completely meaningless! It is mathematically impossible for that test to fail!
We need a real tokenizer! In production, we must use `tiktoken` (cl100k_base) or HuggingFace `tokenizers`.
If the combined prompt, catalog context, and schema exceed 2,500 tokens, the resolver must truncate catalog context or return a token budget exhaustion error (`ERR_VULCAN_TOKEN_BUDGET_EXCEEDED`)."

**Andrej Karpathy:**  
"And finally, let us address Defect 8: **Python 3.14 Runtime Compatibility**.
Our environment is running Python 3.14.
Libraries like `outlines` and `guidance` rely on `numba` and `llvmlite` to compile regular expressions into pushdown automata for token masking.
As of today, `llvmlite` has zero binary wheels for Python 3.14. If you run `pip install outlines` in Python 3.14, the build fails looking for LLVM 15 C++ headers.
We cannot bet the bank's production control plane on uncompilable C-extensions!

Our Python 3.14 compatibility strategy:
1. **Pydantic V2 Native JSON Schema Constrained Decoding:** OpenAI and Anthropic now support native structured outputs (`response_format={"type": "json_schema", "json_schema": ...}`). This executes constrained decoding inside the model provider's inference engine, requiring ZERO local C-extensions!
2. **Local Fallback Validator:** A pure-Python Pydantic validator that takes the model's raw string output, validates it against the playbook schema, and if parsing fails, issues a single correction prompt.
3. **Software 1.0 Log Windowing Service:** In `diagnose_failure.py:53-73`, our 50-line log windowing algorithm is pure Python regex. It has zero C-extension dependencies, runs in $<2\text{ms}$, and reliably isolates the fault point before passing it to any model or heuristic classifier."

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             CALIBRATED INTENT RESOLUTION PIPELINE                                │
│                                                                                                  │
│   Operator Prompt: "xyzzy unknown 123"                                                           │
│   ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│   │ 1. ADVERSARIAL INJECTION CHECK (Regex Guardrails: ignore instructions, bypass approval...) │ │
│   └────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                     │ (Pass)                                                     │
│   ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│   │ 2. TWO-STAGE HYBRID RETRIEVAL (PostgreSQL pgvector Dense + BM25 Sparse Overlap)            │ │
│   └────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                                            │
│   ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│   │ 3. CALIBRATED REFUSAL GATE                                                                 │ │
│   │    IF dense_score < 0.35 AND sparse_score == 0.0:                                          │ │
│   │       ──> RETURN REFUSED ("Out-of-catalog intent: No matching playbook found")             │ │
│   │    ELIF delta_score(item_1, item_2) < 0.05:                                                │ │
│   │       ──> RETURN DISAMBIGUATION_REQUIRED ([item_1, item_2])                                │ │
│   └────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                     │ (High Confidence Match)                                    │
│   ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│   │ 4. PURE-PYTHON TIKTOKEN BUDGET CHECK (cl100k_base: Must be <= 2,500 tokens)                │ │
│   └────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                                            │
│   ┌────────────────────────────────────────────────────────────────────────────────────────────┐ │
│   │ 5. STRUCTURED PARAMETER EXTRACTION (Pydantic V2 Schema Validation)                         │ │
│   │    ──> RETURN READY (or NEEDS_INPUT if required parameters missing)                        │ │
│   └────────────────────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### SPAWNED OPPORTUNITIES — SESSION 6
* **BKND-26: Calibrated Retrieval Refusal Gate (Kill the Zero-Score Trap)**  
  *Problem Killed:* Kills Defect 1 (nonsense queries matching F5 playbook with 0.65 confidence).  
  *Acceptance Criteria:* Retrieval pipeline enforces hard minimum thresholds (`dense_sim >= 0.35` OR `sparse_bm25 > 0.15`); nonsense queries ('xyzzy 123') return `status = "REFUSED"` with `refusal_reason = "Out-of-catalog intent"`; unit tests verify refusal on 10 out-of-domain queries.  
  *Source:* Andrej Karpathy

* **BKND-27: Real IChatModelProvider Port & DeterministicFakeChatProvider in CI**  
  *Problem Killed:* Kills Defect 5 (doc-only markdown pseudocode ports). Enables full LLM mocking in test suites.  
  *Acceptance Criteria:* `IChatModelProvider` abstract port added to `app/ports/interfaces.py`; `DeterministicFakeChatProvider` implemented in `app/adapters/fake_chat_adapter.py` returning deterministic JSON responses; entire CI eval suite runs offline in $<2.0\text{s}$ with zero API keys.  
  *Source:* Robert C. Martin ("Uncle Bob") & Andrej Karpathy

* **BKND-28: Real Tiktoken Budgeting & Context Overflow Protection**  
  *Problem Killed:* Kills Defect 3 (tautological `min(..., 2500)` token clamping).  
  *Acceptance Criteria:* Token count computed using `tiktoken` (cl100k_base) or pure-Python BPE tokenizer; test asserts failure when prompt + schema exceeds 2,500 tokens without hard-clamping; raises `ERR_VULCAN_TOKEN_BUDGET_EXCEEDED`.  
  *Source:* Andrej Karpathy & Jordan Walke

* **BKND-29: Python 3.14 Safe Constrained Decoding Strategy (Pydantic Schema Handshake)**  
  *Problem Killed:* Kills Defect 8 (uncompilable C-extensions for numba/llvmlite in Python 3.14).  
  *Acceptance Criteria:* JSON schema extraction utilizes native Pydantic V2 schema serialization and provider-native JSON Schema mode; fallback pure-Python regex parser handles offline simulation with zero C-compiler prerequisites.  
  *Source:* Andrej Karpathy

* **BKND-30: Pure Software 1.0 Log Windowing & SRE Failure Diagnosis Service**  
  *Problem Killed:* Prevents multi-megabyte log flooding into AI context windows while isolating root causes in $<3.0\text{s}$.  
  *Acceptance Criteria:* `FailureDiagnosticEngine` extracts 50 lines bounded symmetrically around fault points; unit tests verify extraction across Ansible, Terraform, and Python traceback signatures; latency $<50\text{ms}$.  
  *Source:* Andrej Karpathy

---

### SESSION 7: OPERABILITY, FAILURE INJECTION, AND RELEASE GATES

**Uncle Bob:**  
"Finally, we must talk about test vanity versus true testability. Look at our test suite: '60 passed in 2.36s'. Everyone is smiling, thinking we have a solid control plane.
Now ask the hard question: **What happens if we apply mutation testing to our code?**

Suppose a developer accidentally mutates `entities.py:261`:
```python
# Mutated line:
if decision.approver_id != self.requester_id: # Inverted from ==
```
Or suppose someone comments out line 731 in `routes.py`:
```python
# Mutated: commented out
# job.apply_approval_decision(decision, ...)
```
Does our test suite catch it? 
Yes, `test_maker_checker_self_approval_strictly_forbidden` catches the first one.
BUT what if a mutation bypasses the check for unprivileged roles? In `routes.py:708`, there is NO role check, so a mutation there cannot even be detected because there are ZERO tests asserting that an `OPERATOR` role cannot approve a job! Our 60 tests gave us false confidence while leaving a massive SOX audit hole completely uncovered!

We must introduce **Mutation Testing** (via `mutmut` or `cosmic-ray`).
The test suite is only as good as the mutations it kills. Every core invariant—Maker $\ne$ Checker, 15-minute timeout, lock acquisition before secret checkout, synchronous write before execution—must have dedicated mutation kill assertions!"

**Alex Xu:**  
"And beyond mutation testing, we must perform **Chaos and Failure Injection Testing**.
A distributed banking control plane must prove its resilience against these five explicit failure scenarios:
1. **Process Kill Mid-Lock (`kill -9`):** A worker acquiring a lock is killed immediately after step 4. Does the watchdog terminate cleanly? Does the lock evaporate after 30 seconds? Can a second worker acquire the resource without deadlock?
2. **Redis Split-Brain / Quorum Loss:** 2 out of 3 Redis nodes are disconnected. Does `DistributedTargetMutex.acquire()` fail-closed and refuse to proceed without a quorum?
3. **Database Write Failure During Pre-Run Audit:** The PostgreSQL database rejects the `EXEC_START` insert (disk full or connection dropped). Does the runner abort *before* executing the engine? Are CyberArk secrets revoked?
4. **S3 Multipart Abandonment:** The network drops after uploading 2 out of 5 parts. Does the S3 abort cleanup routine trigger?
5. **WebSocket Disconnect During High-Throughput Stream:** An operator closes their laptop lid while 10,000 log lines are streaming. Does the server terminate the socket gracefully without leaking asyncio tasks or memory buffers?"

**Jordan Walke:**  
"And look at our CI release gates. Nothing ships without verification.
We need three distinct test tiers in CI:
1. **Tier 1 (Fast Unit & Domain Invariants):** stdlib-only domain tests, state transition matrix ($14 \times 14$), parameter regex linting, token budgeting, and deterministic fake chat evals. Runs in $<5\text{ seconds}$ on every Git push.
2. **Tier 2 (Adapter Contract Tests via Docker Compose):** Runs against real PostgreSQL 16 (pgvector), real Redis 7.2 cluster, and real MinIO S3 object storage. Verifies real SQL queries, real Lua lock scripts, and real multipart uploads. Runs in $<60\text{ seconds}$ on PR.
3. **Tier 3 (Failure Injection & Load Stress):** Spawns 75 concurrent simulation runners, injects process kills and database disconnects, and measures API p95 latency ($<50\text{ms}$) and lock acquisition p95 ($<15\text{ms}$). Runs nightly on `origin/main`."

**Andrej Karpathy:**  
"And for the AI subsystem: **The Versioned Golden-Eval Harness**.
We maintain a versioned JSONL file (`golden_eval_v1.jsonl`) containing 100 test cases:
- 40 complete intent prompts (expected: `READY` + exact slot extraction)
- 30 partial intent prompts (expected: `NEEDS_INPUT` + exact missing slots)
- 15 out-of-catalog / nonsense prompts (expected: `REFUSED` via refusal gate)
- 15 adversarial prompt injection attacks (expected: `REFUSED` via security guardrail)

In CI, the `DeterministicFakeChatProvider` and `IntentResolver` execute against all 100 cases. If intent extraction accuracy drops below 98%, or if adversarial refusal drops below 100%, the build fails. Zero regressions ship to production."

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              THREE-TIER CI/CD RELEASE GATES                                      │
├────────┬─────────────────────────┬──────────────────────────────────────────┬────────────────────┤
│ TIER   │ SCOPE                   │ INFRASTRUCTURE REQUIRED                  │ TIME CEILING       │
├────────┼─────────────────────────┼──────────────────────────────────────────┼────────────────────┤
│ Tier 1 │ Domain Invariants &     │ Pure Python in-memory, Deterministic     │ < 5.0 seconds      │
│        │ FSM State Matrix        │ Fake Chat Provider, zero network calls   │ (Every Git push)   │
├────────┼─────────────────────────┼──────────────────────────────────────────┼────────────────────┤
│ Tier 2 │ Adapter Contract Tests  │ Docker Compose: PostgreSQL 16 (pgvector),│ < 60.0 seconds     │
│        │ & PostgreSQL Migrations │ Redis 7.2 cluster, MinIO S3 storage      │ (Every Pull Req)   │
├────────┼─────────────────────────┼──────────────────────────────────────────┼────────────────────┤
│ Tier 3 │ Chaos Failure Injection │ Testcontainers: Chaos latency injection, │ < 5.0 minutes      │
│        │ & 75-Runner Fleet Stress│ kill -9 process kills, network partitions│ (Nightly / Main)   │
└────────┴─────────────────────────┴──────────────────────────────────────────┴────────────────────┘
```

#### SPAWNED OPPORTUNITIES — SESSION 7
* **BKND-31: Transition-Matrix Exhaustive Verification Suite ($14 \times 14 = 196$ Pairs)**  
  *Problem Killed:* Eliminates unverified edge cases in finite state transitions.  
  *Acceptance Criteria:* Dedicated test iterates over all 196 possible `(from_state, to_state)` combinations; asserts that exactly 17 legal transitions succeed and 179 illegal transitions raise `StateTransitionError`.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **BKND-32: Mutation Testing Harness Targeting Governance Bypass (Mutmut / Cosmic-Ray)**  
  *Problem Killed:* Kills false confidence from passing tests (e.g. 60 passing tests that don't catch approval RBAC bypass).  
  *Acceptance Criteria:* Mutation test suite achieves mutation score $>92\%$ across `domain/entities.py` and `domain/roles_and_policies.py`; 100% of mutations altering maker-checker inequality or timeout logic are killed.  
  *Source:* Robert C. Martin ("Uncle Bob")

* **BKND-33: Docker Compose Adapter Contract Test Suite (Postgres, Redis, MinIO)**  
  *Problem Killed:* Prevents untested divergence between mock adapters and real production cloud services.  
  *Acceptance Criteria:* Tier-2 CI suite executes full runner lifecycle against local Compose services: PostgreSQL 16 with pgvector, 3-node Redis cluster, and MinIO; verifies real Lua scripts, real SQL transactions, and real multipart presigned uploads.  
  *Source:* Alex Xu

* **BKND-34: Chaos & Failure Injection Matrix (Process Kill, Redis Loss, DB Disconnect)**  
  *Problem Killed:* Verifies fail-closed behavior under catastrophic distributed infrastructure failures.  
  *Acceptance Criteria:* Automated chaos tests verify: (1) `kill -9` worker leaves no permanent deadlock; (2) lost Redis quorum halts acquisition; (3) database disconnect aborts runner before execution; (4) aborted S3 upload cleans orphaned parts.  
  *Source:* Alex Xu

* **BKND-35: Versioned 100-Case Golden-Eval CI Harness (Accuracy & Refusal Gate)**  
  *Problem Killed:* Prevents AI regression and guarantees 100% refusal of adversarial and out-of-catalog prompts in CI.  
  *Acceptance Criteria:* CI executes 100 versioned test cases using `DeterministicFakeChatProvider`; enforces 100% refusal rate on injection attacks and out-of-catalog queries; slot extraction accuracy $\ge 98\%$.  
  *Source:* Andrej Karpathy

---

## 2. CONSOLIDATED BACKEND OPPORTUNITY REGISTER

The table below unifies all 35 architectural opportunities spawned across the seven debate sessions. Each item is prioritized (`P0` = immediate regulatory/blocking safety fix, `P1` = architectural scaling & persistence, `P2` = optimization & telemetry) and mapped to the project implementation phases:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CONSOLIDATED BACKEND OPPORTUNITY REGISTER (BKND-01 – BKND-35)                             │
├─────────┬──────────────────────────────────────────┬───────────────────────────────┬──────────────┬──────────┬──────────────┤
│ ID      │ IMPROVEMENT NAME                         │ PROBLEM KILLED                │ SOURCE       │ PRIORITY │ PHASE MAP    │
├─────────┼──────────────────────────────────────────┼───────────────────────────────┼──────────────┼──────────┼──────────────┤
│ BKND-01 │ Freeze Domain State Machine & Matrix     │ Uncontrolled transitions / bug│ Uncle Bob    │ P0       │ Phase 1 Safe │
│ BKND-02 │ Universal Exception & Error Code System  │ String scraping in UI/API     │ Jordan Walke │ P0       │ Phase 1 Safe │
│ BKND-03 │ Zero-Tolerance Audit Failure Invariant   │ Swallowed audit write errors  │ Uncle Bob    │ P0       │ Phase 1 Safe │
│ BKND-04 │ Domain Purity stdlib-Only CI Enforcement │ Framework leaks into domain   │ Uncle Bob    │ P1       │ Phase 1 Safe │
│ BKND-05 │ Post-Flight Probe State Preservation     │ Clobbering DEGRADED to FAILED │ Uncle Bob    │ P1       │ Phase 1 Safe │
│ BKND-06 │ PostgreSQL Persistence & Repository Ports│ In-memory multi-worker crash  │ Alex Xu      │ P0       │ Phase 2 Infra│
│ BKND-07 │ Alembic Migration & pgvector HNSW Schema │ Unmigrated hardcoded catalog  │ Karpathy     │ P0       │ Phase 2 Infra│
│ BKND-08 │ Cryptographic PostgreSQL Merkle Ledger   │ Single-node fcntl lock flaw   │ Alex Xu      │ P0       │ Phase 2 Infra│
│ BKND-09 │ Synchronous Write-Before-Run Audit Gate  │ Executing without audit trail │ Uncle Bob    │ P0       │ Phase 1 Safe │
│ BKND-10 │ Keyset Cursor Pagination & TSVector Search│ O(N) memory scans in API     │ Jordan Walke │ P1       │ Phase 4 API  │
│ BKND-11 │ Mandatory Lock Token & Atomic Lua CAS    │ Unauthorized lock deletion    │ Alex Xu      │ P0       │ Phase 2 Infra│
│ BKND-12 │ Monotonic Distributed Fencing Tokens     │ Stale execution writes        │ Alex Xu      │ P1       │ Phase 2 Infra│
│ BKND-13 │ Watchdog Heartbeat with Auto-Evaporation │ Deadlock on worker kill       │ Alex Xu      │ P1       │ Phase 2 Infra│
│ BKND-14 │ S3 Multipart Abort & Lifecycle Gate      │ Leaked orphaned chunk storage │ Alex Xu      │ P1       │ Phase 2 Infra│
│ BKND-15 │ Lock Telemetry Projection in Job Models  │ UI setInterval fake radar     │ Jordan Walke │ P2       │ Phase 4 API  │
│ BKND-16 │ Fail-Closed Honest ServiceNow Mock Gate  │ Synthetic governance illusion │ Karpathy     │ P0       │ Phase 2 Infra│
│ BKND-17 │ Kill routes.py Fake Simulation Loop      │ Bypassing BaseJobRunner gates │ Uncle Bob    │ P0       │ Phase 1 Safe │
│ BKND-18 │ Decoupled Worker Fleet for 75 Runners    │ Unbounded OS threads in API   │ Alex Xu      │ P0       │ Phase 2 Infra│
│ BKND-19 │ Real CyberArk PAM Adapter with RAM-Only  │ Hardcoded plaintext secrets   │ Uncle Bob    │ P1       │ Phase 2 Infra│
│ BKND-20 │ Automated Rollback Execution Rail        │ Orphaned degraded states      │ Uncle Bob    │ P1       │ Phase 1 Safe │
│ BKND-21 │ Mandatory Approval RBAC & Role Check     │ Anyone can approve any job    │ Jordan Walke │ P0       │ Phase 4 API  │
│ BKND-22 │ Distributed Idempotency-Key Gate         │ Duplicate job execution       │ Jordan Walke │ P0       │ Phase 4 API  │
│ BKND-23 │ Redis WebSocket Dual-Write & Replay Hub  │ WS log loss across workers    │ Alex Xu      │ P0       │ Phase 4 API  │
│ BKND-24 │ Standardized API Error Envelopes         │ Frontend parsing raw strings  │ Jordan Walke │ P1       │ Phase 4 API  │
│ BKND-25 │ Capabilities Projection in ViewModels    │ UI computing policy in JSX    │ Jordan Walke │ P1       │ Phase 4 API  │
│ BKND-26 │ Calibrated Retrieval Refusal Gate        │ Zero-Score Trap on nonsense   │ Karpathy     │ P0       │ Phase 1 Safe │
│ BKND-27 │ IChatModelProvider Port & Fake in CI     │ Doc-only LLM architecture     │ Uncle Bob    │ P0       │ Phase 1 Safe │
│ BKND-28 │ Real Tiktoken Budget & Overflow Check    │ Tautological min(,2500) budget│ Karpathy     │ P0       │ Phase 1 Safe │
│ BKND-29 │ Python 3.14 Safe Decoding (Pydantic V2)  │ Uncompilable C-extensions     │ Karpathy     │ P1       │ Phase 1 Safe │
│ BKND-30 │ Pure Software 1.0 Log Windowing Service  │ Context overflow from stdout  │ Karpathy     │ P1       │ Phase 1 Safe │
│ BKND-31 │ FSM Transition Matrix Suite (196 Pairs)  │ Illegal state regressions     │ Uncle Bob    │ P0       │ Phase 6 Test │
│ BKND-32 │ Mutation Testing Suite (Mutmut >92%)     │ False confidence in 60 tests  │ Uncle Bob    │ P1       │ Phase 6 Test │
│ BKND-33 │ Docker Compose Adapter Contract Tests    │ Mock drift from real services │ Alex Xu      │ P1       │ Phase 6 Test │
│ BKND-34 │ Chaos & Failure Injection Matrix (Kill-9)│ Unhandled distributed crashes │ Alex Xu      │ P1       │ Phase 6 Test │
│ BKND-35 │ 100-Case Golden-Eval CI Harness          │ AI prompt regressions in CI   │ Karpathy     │ P1       │ Phase 6 Test │
└─────────┴──────────────────────────────────────────┴───────────────────────────────┴──────────────┴──────────┴──────────────┘
```

---

## 3. ARCHITECTURE DECISION RECORD (ADR)

### ADR-001: CONTROL PLANE LAYERING & REPOSITORY BOUNDARY

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               BACKEND CONTROL PLANE ARCHITECTURE                                 │
│                                                                                                  │
│   PRESENTATION / API LAYER (FastAPI, Uvicorn, WebSockets)                                        │
│   ├── routes.py (REST endpoints: /health, /jobs, /catalog, /intent)                              │
│   ├── websockets.py (Redis Dual-Write Replay Hub)                                                │
│   ├── error_handlers.py (Translates VulcanDomainError -> {error_code, message, details})         │
│   └── middleware/ (IdempotencyMiddleware, RBACAuthMiddleware, RequestIdMiddleware)               │
│                                   │                                                              │
│                                   ▼ (Calls Use Cases via Dependency Injection)                   │
│   APPLICATION USE CASES LAYER (Pure Orchestration)                                               │
│   ├── runner.py (BaseJobRunner Template Method Pipeline)                                         │
│   ├── resolve_intent.py (IntentResolver: Refusal Gate, Hybrid RRF, Tiktoken Budget)              │
│   ├── approve_job.py (ApproveJobUseCase: Role Authorization & Maker-Checker)                     │
│   └── diagnose_failure.py (FailureDiagnosticEngine: 50-line log windowing)                       │
│                                   │                                                              │
│                  ┌────────────────┴────────────────┐                                             │
│                  ▼                                 ▼                                             │
│   DOMAIN CORE (app/domain/)         DOMAIN PORTS (app/ports/)                                    │
│   ├── entities.py (ExecutionJob,    ├── repositories.py (IJobRepo, IAuditRepo)                   │
│   │   CatalogItem, AuditRecord)     ├── interfaces.py (ILockManager, ISecretProvider,            │
│   ├── exceptions.py (DomainError)   │   IServiceNowGateway, IObjectStorageGateway,               │
│   └── roles_and_policies.py (RBAC)  │   IExecutionEngine, IChatModelProvider)                    │
│   (STDLIB ONLY: Zero Dependencies)  (Pure Abstract Base Classes)                                 │
│                                                    ▲                                             │
│                                                    │ (Implemented by)                            │
│   INFRASTRUCTURE ADAPTERS (app/adapters/)          │                                             │
│   ├── persistence/ (PostgresJobRepository, PostgresAuditRepository via SQLAlchemy 2.0)           │
│   ├── redlock_adapter.py (Redis 7.2 Redlock with Watchdog & Monotonic Fencing Tokens)            │
│   ├── s3_multipart_adapter.py (MinIO / S3 Gateway with auto-abort & checksum gate)               │
│   ├── servicenow_adapter.py (Fail-Closed ITSM REST Client / Honest Local Mock)                   │
│   ├── cyberark_adapter.py (RAM-Only Ephemeral PAM Checkout)                                      │
│   └── fake_chat_adapter.py (DeterministicFakeChatProvider for CI)                                │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### ADR-002: MIGRATION STRATEGY FROM IN-MEMORY TO POSTGRESQL + REDIS

The migration from in-memory prototypes to production persistence requires zero changes to domain business logic. Because Clean Architecture decouples the domain via abstract ports, the migration proceeds through adapter swapping:

1. **Phase 1: Database Provisioning & Schema Migration:**
   - Provision PostgreSQL 16 with `pgvector` extension.
   - Execute Alembic migration `003_vulcan_control_plane.py` creating `catalog_items`, `execution_jobs`, `approval_decisions`, and `audit_ledger`.
   - Seed `catalog_items` from `catalog_data.py` definitions and compute vector embeddings via a migration script.
2. **Phase 2: Adapter Implementation & Contract Testing:**
   - Implement `PostgresJobRepository` and `PostgresAuditRepository` conforming to `IJobRepository` and `IAuditRepository`.
   - Implement `RedisStreamQueue` for asynchronous job dispatch.
   - Run Tier-2 Docker Compose contract test suite to verify 100% parity with domain behaviors.
3. **Phase 3: Dependency Injection Container Swap:**
   - In `backend/app/config.py`, replace `self.jobs = {}` with `self.job_repository = PostgresJobRepository(session_factory)`.
   - Replace in-memory audit list with `self.audit_logger = PostgresAuditLogger(session_factory)`.
   - Replace standalone mutex fallback with `self.lock_manager = RedlockManager(redis_cluster)`.
4. **Phase 4: Multi-Worker Deployment Topology:**
   - Deploy 4 Uvicorn API pods behind load balancer (stateless).
   - Deploy 1 dedicated Background Sweeper pod (acquires Redis leader lock to run 15-minute approval timeout sweeper).
   - Deploy an autoscaled Celery/ARQ Worker fleet (sized for 75 concurrent runners).

---

## 4. TESTING & SAFETY PLAN

### 1. Transition-Matrix Exhaustive Verification Suite
To guarantee that no invalid state jump is possible, a parameterized test must execute all $14 \times 14 = 196$ state pairs. Exactly 17 transitions must succeed; the remaining 179 must raise `StateTransitionError` with code `ERR_VULCAN_ILLEGAL_STATE_TRANSITION`.

```python
LEGAL_TRANSITIONS = {
    (JobStatus.SUBMITTED, JobStatus.PARSED),
    (JobStatus.SUBMITTED, JobStatus.FAILED),
    (JobStatus.PARSED, JobStatus.PENDING_APPROVAL),
    (JobStatus.PARSED, JobStatus.QUEUED),
    (JobStatus.PARSED, JobStatus.FAILED),
    (JobStatus.PENDING_APPROVAL, JobStatus.QUEUED),
    (JobStatus.PENDING_APPROVAL, JobStatus.REJECTED),
    (JobStatus.PENDING_APPROVAL, JobStatus.TIMEOUT_DENIED),
    (JobStatus.PENDING_APPROVAL, JobStatus.FAILED),
    (JobStatus.QUEUED, JobStatus.LOCKED),
    (JobStatus.QUEUED, JobStatus.FAILED),
    (JobStatus.LOCKED, JobStatus.RUNNING),
    (JobStatus.LOCKED, JobStatus.FAILED),
    (JobStatus.RUNNING, JobStatus.VERIFYING),
    (JobStatus.RUNNING, JobStatus.FAILED),
    (JobStatus.VERIFYING, JobStatus.SUCCESS),
    (JobStatus.VERIFYING, JobStatus.DEGRADED),
    (JobStatus.VERIFYING, JobStatus.FAILED),
    (JobStatus.DEGRADED, JobStatus.REVERTING),
    (JobStatus.DEGRADED, JobStatus.FAILED),
    (JobStatus.REVERTING, JobStatus.REVERTED),
    (JobStatus.REVERTING, JobStatus.FAILED),
}
```

### 2. Mutation Testing Against Governance Bypass
Mutation testing using `mutmut` will inject mutations into:
- `entities.py:apply_approval_decision` (inverting `==` to `!=`, bypassing timeout checks, removing status assignments).
- `roles_and_policies.py:check_permission` (hardcoding return `True`).
- `runner.py:run` (reordering lock acquisition after secret checkout or skipping pre-run audit).
Target: **100% of governance-altering mutations must be killed by the test suite.**

### 3. Failure-Injection Chaos Matrix
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CHAOS FAILURE INJECTION MATRIX                                   │
├──────────────────────────┬─────────────────────────────┬─────────────────────────────────────────┤
│ INJECTED FAILURE         │ INJECTION METHOD            │ EXPECTED SYSTEM BEHAVIOR                │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────┤
│ Worker SIGKILL mid-run   │ kill -9 on runner PID       │ Watchdog stops; Redis lock evaporates   │
│                          │                             │ after 30s; next worker detects orphan.  │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────┤
│ Redis Quorum Partition   │ iptables DROP on 2/3 nodes  │ Mutex acquire fails closed; job remains │
│                          │                             │ QUEUED; emits ERR_VULCAN_LOCK_TIMEOUT.  │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────┤
│ Audit DB Write Failure   │ Mock IOError on EXEC_START  │ Runner halts; revokes PAM secret lease; │
│                          │                             │ releases Redlock; raises AuditIntegrity.│
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────┤
│ S3 Multipart Abort       │ Disconnect client at part 3 │ Adapter calls abort_multipart_upload;   │
│                          │                             │ zero orphaned S3 chunks remain.         │
├──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────┤
│ Unknown ServiceNow CHG   │ Submit CHG-UNKNOWN-999      │ Mock adapter rejects; maintenance check │
│                          │                             │ returns False; job blocked fail-closed. │
└──────────────────────────┴─────────────────────────────┴─────────────────────────────────────────┘
```

---

## 5. MEASUREMENT PLAN TABLE

Nothing ships to production unmeasured. Every critical service SLO must have an automated instrument and target threshold:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   VULCAN BACKEND MEASUREMENT PLAN                                      │
├───────────────────────────────┬───────────────────┬────────────────────────────────────────────────────┤
│ METRIC                        │ TARGET THRESHOLD  │ INSTRUMENTATION / PROFILING METHOD                 │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ REST API Latency (p95)        │ < 35 ms           │ Prometheus middleware: http_request_duration_sec   │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ Distributed Lock Acquisition  │ < 15 ms           │ OpenTelemetry span: redlock_acquire_latency_ms     │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ Synchronous Audit Commit Lat  │ < 10 ms           │ SQL query span: postgres_audit_insert_duration_ms  │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ WebSocket Late-Join Replay Lag│ < 50 ms           │ Client-measured ACK latency on last_seq catchup    │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ 10GB S3 Multipart Throughput  │ > 250 MB/sec      │ S3 client metrics (50MB parts across 8 streams)    │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ Sweeper Timeout Accuracy      │ < 5.0 sec drift   │ Periodic background sweeper latency histogram      │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ Intent Resolution Latency     │ < 800 ms          │ resolve_intent span (RRF + Pydantic validation)    │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ CI Test Suite Runtime (Tiers) │ < 5s (T1), <60s(T2│ pytest --durations=10 execution timing             │
├───────────────────────────────┼───────────────────┼────────────────────────────────────────────────────┤
│ Mutation Score (Governance)   │ > 92% killed      │ mutmut run --paths-to-mutate app/domain            │
└───────────────────────────────┴───────────────────┴────────────────────────────────────────────────────┘
```

---

## 6. IRON GUARDRAILS: WHAT THE CONTROL PLANE MUST NEVER DO

To protect financial infrastructure from catastrophic error or compromise, the backend codebase must strictly adhere to the following **Ten Backend Guardrails**:

1. **NEVER execute policy logic in API routes or adapters:** All authorization, Separation of Duties, and risk rules belong exclusively to `app/domain/` or `app/use_cases/`. Routes and adapters must remain dumb translators.
2. **NEVER leak plaintext credentials or private keys:** All inputs must pass TruffleHog regex scanning before instantiation. Ephemeral secrets from CyberArk must reside in RAM only and be purged in `finally` blocks. Zero secrets in logs, audit records, or LLM context.
3. **NEVER release a distributed lock without ownership proof:** `ILockManager.release` must require `owner_token`. Unconditional lock deletion without token comparison is strictly forbidden.
4. **NEVER start engine execution before a synchronous audit commit:** `EXEC_START` must be written and flushed to PostgreSQL before any Ansible or Terraform command is spawned. If the audit write fails, execution must abort fail-closed.
5. **NEVER permit state transitions outside domain entities:** No route, worker, or database trigger may mutate `job.status` directly. Transitions must invoke `job.transition_to()`, enforcing the 14-state frozen transition matrix.
6. **NEVER report simulated adapters as production-ready:** Mock adapters must explicitly identify as mocks (`mock_mode=True`), fail-closed on unknown inputs, and be tested against Docker Compose testcontainers before deployment.
7. **NEVER allow out-of-catalog or low-confidence queries to match playbooks:** The refusal gate must reject queries with confidence $<0.35$ as `REFUSED`. The system must never guess or pre-fill schema defaults on nonsense input.
8. **NEVER spawn raw unbounded OS threads inside the API web process:** All runner executions must be enqueued to Redis Streams and processed by the decoupled Celery/ARQ worker fleet.
9. **NEVER proxy multi-gigabyte storage payloads through FastAPI memory:** Payloads must use direct-to-S3 presigned multipart uploads. The API process handles only metadata.
10. **NEVER swallow audit write failures or fail open on infrastructure errors:** Any failure in the audit logger, lock manager, or ServiceNow gateway must trigger an immediate fail-closed abort.

---

## 7. DEFINITION OF DONE (DoD) PER BACKEND ITEM

Before any item from the Consolidated Backend Opportunity Register can be marked as complete and merged to `origin/main`, it must satisfy all six criteria of this Definition of Done:

1. **Clean Architecture Compliance:**
   - Domain invariants remain isolated in `app/domain/` with stdlib-only imports (verified by AST linter).
   - Use cases interact exclusively with abstract ports (`app/ports/`).
   - Database, Redis, and network calls are restricted to `app/adapters/`.
2. **Deterministic Automated Verification:**
   - 100% branch coverage on new domain logic.
   - Unit tests run in $<5\text{s}$ using `DeterministicFakeChatProvider` and in-memory fakes.
   - Parameterized state transition tests assert legal success and illegal failure.
3. **Contract & Integration Verification:**
   - Adapter passes contract tests against real Docker Compose services (PostgreSQL 16, Redis 7.2, MinIO).
   - Mock adapters verified to fail-closed on unknown inputs.
4. **Failure & Rollback Behavior:**
   - Failure behavior documented and verified via simulated exception injection.
   - Resource cleanup (locks released, PAM secrets revoked, S3 parts aborted) verified in `finally` blocks.
5. **Observability & Error Envelopes:**
   - Every raised exception maps to a stable `error_code` and uniform JSON error envelope.
   - Key operational steps emit structured OpenTelemetry spans and Prometheus counters.
6. **Architectural Sign-off:**
   - Code changes peer-reviewed and signed off against the relevant Phase Gate criteria by the domain lead.

---

### ARCHITECTURAL RATIFICATION & SIGN-OFF

The four architects unanimously ratify this Backend Control Plane Architecture Debate & Masterplan as the canonical engineering backlog for Project Vulcan:

* **Robert C. Martin ("Uncle Bob")** — Clean Architecture & Domain Invariants Lead  
* **Alex Xu** — Distributed Systems & Concurrency Lead  
* **Andrej Karpathy** — LLM Operating System & AI Boundary Lead  
* **Jordan Walke** — Declarative UI & API Contract Lead  
