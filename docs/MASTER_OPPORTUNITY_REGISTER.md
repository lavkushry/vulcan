# Project Vulcan: Master Opportunity Register & Delivery Audit

**Document Version:** 4.0.0-PROD  
**Authority:** Architectural Review Board (Uncle Bob, Alex Xu, Andrej Karpathy, Jordan Walke, Platform Lead)  
**Scope:** Consolidated tracking across all five architectural war room debate registers:
- `UI-01` through `UI-23` (Operator Console & Declarative Ergonomics)
- `CHAT-01` through `CHAT-24` (AI Chat Subsystem, Intent Compilation & Safety)
- `BKND-01` through `BKND-35` (Backend Control Plane, State Machine, Mutexes & Storage)
- `INFRA-01` through `INFRA-30` (Platform, CI/CD, Observability & Release Engineering)
- `REG-01` through `REG-08` (Registry Crawling, Curation Gate & Steel Cage Invariants)

---

## 1. Executive Summary & Delivery Posture

The Master Opportunity Register unifies **120 architectural opportunities** mined during the War Room audit sessions. Each item maps directly to a banking governance invariant, performance budget, or reliability contract.

### Progress by Subsystem

| Subsystem | Total Items | 🟢 Implemented | 🟡 In Progress | ⚪ Planned | Implementation Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Frontend Console (`UI-XX`)** | 23 | 14 | 5 | 4 | **60.9%** |
| **AI Chat Subsystem (`CHAT-XX`)** | 24 | 16 | 5 | 3 | **66.7%** |
| **Backend Control Plane (`BKND-XX`)** | 35 | 26 | 5 | 4 | **74.3%** |
| **Platform & Infra (`INFRA-XX`)** | 30 | 20 | 6 | 4 | **66.7%** |
| **Registry & Curation (`REG-XX`)** | 8 | 7 | 1 | 0 | **87.5%** |
| **Total Across Architecture** | **120** | **83** | **22** | **15** | **69.2%** |

---

## 2. Master Register: Frontend Console (`UI-01` – `UI-23`)

| ID | Initiative Name | Problem Killed | Persona | Prio | Phase | Status | Verification Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **UI-01** | Domain Invariant Presenter | Policy logic leaking into JSX components | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `frontend/components/TaskMatrixTable.tsx` |
| **UI-02** | Real-Time Attestation Ledger | Hardcoded mock policy evaluation arrays | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `frontend/components/SeparationOfDutiesProofCard.tsx` |
| **UI-03** | Zero-Trust Error Boundary | Silent error-swallowing synthesizing fake cards | Karpathy | P0 | Phase 1 | 🟢 Implemented | `frontend/components/ChatAssistant.tsx` |
| **UI-04** | Server-Telemetry Redlock Radar | Client-side setInterval lock simulation | Alex Xu | P0 | Phase 1 | 🟢 Implemented | `frontend/components/RedlockHeartbeatBar.tsx` |
| **UI-05** | RAF-Batched WebSocket Streamer | 500+ re-renders/s tab freezing and storm | Alex Xu | P0 | Phase 1 | 🟢 Implemented | `frontend/hooks/useJobStream.ts` |
| **UI-06** | GPU-Accelerated WebGL Terminal | DOM node explosion under 100k stdout lines | Jordan Walke | P0 | Phase 1 | 🟢 Implemented | `frontend/components/Terminal.tsx` |
| **UI-07** | Canvas S3 Swarm Grid | Fake Canvas claims using 205 React `<div>`s | Alex Xu | P1 | Phase 2 | 🟡 In Progress | `frontend/components/S3MultipartSwarmGrid.tsx` |
| **UI-08** | Working Memory Tokenomics HUD | Hardcoded static tokenomics in UI | Karpathy | P1 | Phase 2 | 🟢 Implemented | `frontend/components/TokenomicsHUD.tsx` |
| **UI-09** | Semantic Disambiguation Bento | Autonomous guessing when queries match twins | Karpathy | P0 | Phase 2 | 🟢 Implemented | `frontend/components/DisambiguationBentoCard.tsx` |
| **UI-10** | Pydantic Grammar Slot Chips | Parameter hallucination blindspots | Uncle Bob | P1 | Phase 2 | 🟢 Implemented | `frontend/components/ChatAssistant.tsx` |
| **UI-11** | Adversarial Refusal Cockpit | Generic or silent errors on injection refusal | Karpathy | P2 | Phase 3 | 🟢 Implemented | `frontend/components/ChatAssistant.tsx` |
| **UI-12** | Maker-Checker Cockpit Deck | Ambiguous approval surfaces & self-sign-off | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `frontend/components/MakerCheckerDeck.tsx` |
| **UI-13** | Server-Sync Circuit Breaker | Client timer drift causing 408 surprise errors | Alex Xu | P0 | Phase 1 | 🟢 Implemented | `frontend/components/SeparationOfDutiesProofCard.tsx` |
| **UI-14** | Topology Blast Radius Drawer | Approvers unaware of downstream collateral | Karpathy | P1 | Phase 2 | ⚪ Planned | `frontend/components/JobDetail.tsx` |
| **UI-15** | Merkle Audit Chain UI Verifier | Unverifiable historical job audit ledger | Uncle Bob | P2 | Phase 3 | 🟡 In Progress | `frontend/components/SeparationOfDutiesProofCard.tsx` |
| **UI-16** | Resizable Dual-Pane Splitter | Rigid 50/50 split crowding small laptops | Jordan Walke | P2 | Phase 3 | 🟢 Implemented | `frontend/components/ResizableDualPane.tsx` |
| **UI-17** | Linear-Grade Keyboard Hotkeys | Slow mouse-bound navigation in high-stress SRE | Jordan Walke | P1 | Phase 2 | 🟢 Implemented | `frontend/components/UniversalCommandPalette.tsx` |
| **UI-18** | Forensic Terminal Action Bar | Viewport autoscroll snapping & ANSI corruption | Jordan Walke | P1 | Phase 2 | 🟢 Implemented | `frontend/components/TerminalActionBar.tsx` |
| **UI-19** | AST Failure Pinpoint & Rollback | Fake rollback DAGs with setTimeout buttons | Karpathy | P0 | Phase 1 | 🟢 Implemented | `frontend/components/JobDetail.tsx` |
| **UI-20** | Fuzzy Universal Command Palette | Static 4-item mock palette | Jordan Walke | P1 | Phase 2 | 🟢 Implemented | `frontend/components/UniversalCommandPalette.tsx` |
| **UI-21** | Virtualized Task Table Engine | DOM bloat when rendering 500+ tasks | Alex Xu | P1 | Phase 2 | 🟡 In Progress | `frontend/components/TaskMatrixTable.tsx` |
| **UI-22** | Pruning Dead Prototype Code | 100KB orphaned prototype components | Uncle Bob | P1 | Phase 2 | 🟢 Implemented | Clean repository checkout |
| **UI-23** | Monaco HCL/YAML Diff Inspector | Missing raw declarative code inspect before run | Jordan Walke | P2 | Phase 3 | ⚪ Planned | `frontend/components/MonacoDiffModal.tsx` |

---

## 3. Master Register: AI Chat Subsystem (`CHAT-01` – `CHAT-24`)

| ID | Initiative Name | Problem Killed | Persona | Prio | Phase | Status | Verification Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **CHAT-01** | `JobSubmissionCommand` Port | Leaking presentation state to domain | Uncle Bob | P0 | Phase 3 | 🟢 Implemented | `backend/app/domain/entities.py` |
| **CHAT-02** | Kill Client Mock Fallbacks | Fake CHG ticket generation & silent errors | Uncle Bob | P0 | Phase 5 | 🟢 Implemented | `frontend/components/ChatAssistant.tsx` |
| **CHAT-03** | Distributed Session Repository | Conversational memory loss across pod restarts | Alex Xu | P1 | Phase 4 | 🟡 In Progress | `backend/app/adapters/redis_chat_repository.py` |
| **CHAT-04** | Boundary Intent State Machine | Brittle scripts and dual-endpoint conflict | Karpathy | P0 | Phase 3 | 🟢 Implemented | `backend/app/use_cases/resolve_intent.py` |
| **CHAT-05** | pgvector HNSW Vector Index | In-memory catalog scaling bottleneck | Alex Xu | P0 | Phase 3 | 🟢 Implemented | `backend/app/adapters/postgres_catalog_repository.py` |
| **CHAT-06** | Two-Stage Hybrid RRF Search | Dense search missing exact IPs, CVEs, tags | Karpathy | P0 | Phase 3 | 🟢 Implemented | `backend/app/adapters/postgres_catalog_repository.py` |
| **CHAT-07** | Deterministic Keyword Fallback | Service failure when embedding API unavailable | Uncle Bob | P1 | Phase 3 | 🟢 Implemented | `backend/app/adapters/embedding_providers.py` |
| **CHAT-08** | Ambivalence Disambiguation Card | Autonomous guessing on twin playbooks | Jordan Walke | P0 | Phase 5 | 🟢 Implemented | `frontend/components/DisambiguationBentoCard.tsx` |
| **CHAT-09** | Pydantic Grammar Slot Decoding | LLM parameter hallucinations & schema errors | Karpathy | P0 | Phase 3 | 🟢 Implemented | `backend/app/use_cases/resolve_intent.py` |
| **CHAT-10** | Absolute Prohibition of Defaults | Silent pre-filling of unconfirmed values | Uncle Bob | P0 | Phase 3 | 🟢 Implemented | `backend/app/use_cases/resolve_intent.py` |
| **CHAT-11** | Parameter Slot Provenance Badges| Unverified source of input parameters | Karpathy | P1 | Phase 3 | 🟢 Implemented | `frontend/components/ChatAssistant.tsx` |
| **CHAT-12** | Inline Slot Bento Tab-Flow Card | Clunky multi-turn prose for slot collection | Jordan Walke | P0 | Phase 5 | 🟢 Implemented | `frontend/components/ChatAssistant.tsx` |
| **CHAT-13** | Working Memory Cap (2,500 Tok) | Context explosion and slow TTFT latency | Karpathy | P0 | Phase 3 | 🟢 Implemented | `backend/app/use_cases/resolve_intent.py` |
| **CHAT-14** | ServiceNow CHG & CMDB Hydration | Manual typing of infrastructure parameters | Alex Xu | P1 | Phase 4 | 🟡 In Progress | `backend/app/adapters/servicenow_adapter.py` |
| **CHAT-15** | Visual Provenance Conflict Alerts | Unchecked mismatch between prompt & CMDB | Uncle Bob | P1 | Phase 5 | 🟡 In Progress | `frontend/components/ChatAssistant.tsx` |
| **CHAT-16** | Telemetry Failure Warning Banner| Generic errors without historical context | Jordan Walke | P2 | Phase 5 | ⚪ Planned | `frontend/components/ChatAssistant.tsx` |
| **CHAT-17** | 4-Stage Prompt Injection Refusal| Prompt jailbreaks and instruction override | Karpathy | P0 | Phase 3 | 🟢 Implemented | `backend/tests/test_ai_prompt_injection_golden.py` |
| **CHAT-18** | OpenTelemetry Dynamic HUD | Static hardcoded metrics in frontend | Alex Xu | P1 | Phase 5 | 🟢 Implemented | `frontend/components/TokenomicsHUD.tsx` |
| **CHAT-19** | Conversational Merkle Binding | Inability to audit conversational intent later | Uncle Bob | P0 | Phase 4 | 🟢 Implemented | `backend/app/adapters/crypto_audit_adapter.py` |
| **CHAT-20** | 500-Scenario Golden Eval Gate | Silent regressions in intent routing & safety | Karpathy | P0 | Phase 3 | 🟢 Implemented | `backend/tests/test_ai_reasoning_evals.py` |
| **CHAT-21** | Zero-CLS Bento Streaming Render | UI freezing during conversational resolution | Jordan Walke | P1 | Phase 5 | 🟡 In Progress | `frontend/components/ChatAssistant.tsx` |
| **CHAT-22** | SSE Transport over HTTP/2 | WebSocket drops across corporate proxies | Alex Xu | P1 | Phase 4 | ⚪ Planned | `backend/app/api/routes.py` |
| **CHAT-23** | Cryptographic Stream Sentinel | Half-completed submissions on dropped streams | Uncle Bob | P0 | Phase 5 | 🟢 Implemented | `backend/app/api/websockets.py` |
| **CHAT-24** | Keyboard-First Intent Navigation| Friction from mandatory mouse clicks in chat | Jordan Walke | P1 | Phase 5 | 🟢 Implemented | `frontend/components/ChatAssistant.tsx` |

---

## 4. Master Register: Backend Control Plane (`BKND-01` – `BKND-35`)

| ID | Initiative Name | Problem Killed | Persona | Prio | Phase | Status | Verification Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **BKND-01** | Freeze State Machine & Matrix | Uncontrolled transitions and state bugs | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `backend/app/domain/entities.py` |
| **BKND-02** | Universal Error Code System | String scraping in API/UI error handlers | Jordan Walke | P0 | Phase 1 | 🟢 Implemented | `backend/app/domain/exceptions.py` |
| **BKND-03** | Zero-Tolerance Audit Failure | Swallowed audit write errors causing drift | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `backend/app/use_cases/runner.py` |
| **BKND-04** | Domain Purity stdlib-Only CI | Framework dependencies leaking into domain | Uncle Bob | P1 | Phase 1 | 🟢 Implemented | `backend/tests/test_domain_invariants.py` |
| **BKND-05** | Probe State Preservation | Clobbering DEGRADED to generic FAILED | Uncle Bob | P1 | Phase 1 | 🟢 Implemented | `backend/app/use_cases/runner.py` |
| **BKND-06** | PostgreSQL Persistence Ports | In-memory store crashing at 2+ workers | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `backend/app/adapters/postgres_catalog_repository.py` |
| **BKND-07** | Alembic pgvector HNSW Schema | Unmigrated hardcoded catalog data | Karpathy | P0 | Phase 2 | 🟢 Implemented | `backend/migrations/003_vulcan_core_schema.sql` |
| **BKND-08** | Cryptographic Merkle Ledger | Single-node fcntl file-lock vulnerability | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `backend/app/adapters/crypto_audit_adapter.py` |
| **BKND-09** | Synchronous Write-Before-Run | Executing changes without recorded audit | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `backend/app/use_cases/runner.py` |
| **BKND-10** | Keyset Cursor Pagination & TSV | O(N) memory scans in API endpoints | Jordan Walke | P1 | Phase 4 | 🟢 Implemented | `backend/app/adapters/postgres_catalog_repository.py` |
| **BKND-11** | Lock Token & Atomic Lua CAS | Unauthorized lock release across workers | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `backend/app/adapters/redlock_adapter.py` |
| **BKND-12** | Monotonic Fencing Tokens | Stale worker execution race condition | Alex Xu | P1 | Phase 2 | 🟢 Implemented | `backend/app/adapters/redlock_adapter.py` |
| **BKND-13** | Watchdog Heartbeat Extension | Deadlock on worker crash during long jobs | Alex Xu | P1 | Phase 2 | 🟢 Implemented | `backend/app/adapters/redlock_adapter.py` |
| **BKND-14** | S3 Multipart Abort & Cleanup | Orphaned chunk storage leaks in MinIO | Alex Xu | P1 | Phase 2 | 🟢 Implemented | `backend/app/adapters/s3_multipart_adapter.py` |
| **BKND-15** | Lock Telemetry in Job Models | UI guessing lock status via setInterval | Jordan Walke | P2 | Phase 4 | 🟢 Implemented | `backend/app/domain/entities.py` |
| **BKND-16** | Fail-Closed ServiceNow Gate | Synthetic governance illusion in test runs | Karpathy | P0 | Phase 2 | 🟢 Implemented | `backend/app/adapters/servicenow_adapter.py` |
| **BKND-17** | Kill routes.py Simulation Loop | Bypassing BaseJobRunner safety template | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `backend/app/api/routes.py` |
| **BKND-18** | Decoupled 75-Runner Fleet | Unbounded thread spawn in API process | Alex Xu | P0 | Phase 2 | 🟡 In Progress | `backend/app/use_cases/runner.py` |
| **BKND-19** | CyberArk PAM RAM-Only Secrets | Hardcoded plaintext credentials in memory | Uncle Bob | P1 | Phase 2 | 🟢 Implemented | `backend/app/adapters/cyberark_adapter.py` |
| **BKND-20** | Automated Rollback Execution | Orphaned degraded states after failure | Uncle Bob | P1 | Phase 1 | 🟢 Implemented | `backend/app/use_cases/runner.py` |
| **BKND-21** | Mandatory Approval RBAC Gate | Any authenticated user approving any job | Jordan Walke | P0 | Phase 4 | 🟢 Implemented | `backend/app/api/routes.py` |
| **BKND-22** | Distributed Idempotency Gate | Duplicate executions on double-click | Jordan Walke | P0 | Phase 4 | 🟢 Implemented | `backend/app/api/routes.py` |
| **BKND-23** | Redis WebSocket Dual-Write | WS log lines lost across uvicorn workers | Alex Xu | P0 | Phase 4 | 🟢 Implemented | `backend/app/api/websockets.py` |
| **BKND-24** | Standardized Error Envelopes | Frontend parsing unstructured error strings | Jordan Walke | P1 | Phase 4 | 🟢 Implemented | `backend/app/api/routes.py` |
| **BKND-25** | Capabilities in ViewModels | Frontend re-implementing banking policy | Jordan Walke | P1 | Phase 4 | 🟢 Implemented | `backend/app/api/routes.py` |
| **BKND-26** | Calibrated Refusal Gate | Zero-Score Trap on out-of-catalog noise | Karpathy | P0 | Phase 1 | 🟢 Implemented | `backend/app/adapters/postgres_catalog_repository.py` |
| **BKND-27** | `IEmbeddingProvider` Port | Hardcoded token-hash noise vectors | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `backend/app/adapters/embedding_providers.py` |
| **BKND-28** | Real Tiktoken Budget Gate | Tautological min(x, 2500) budget formula | Karpathy | P0 | Phase 1 | 🟢 Implemented | `backend/app/use_cases/resolve_intent.py` |
| **BKND-29** | Python 3.14 Compatible FSM | C-extension compiler breakages in runtime | Karpathy | P1 | Phase 1 | 🟢 Implemented | `backend/app/use_cases/resolve_intent.py` |
| **BKND-30** | Software 1.0 Log Windowing | Diagnostic context overflow from large stdout | Karpathy | P1 | Phase 1 | 🟢 Implemented | `backend/app/use_cases/diagnose_failure.py` |
| **BKND-31** | FSM Transition Matrix Suite | Undetected state transition regressions | Uncle Bob | P0 | Phase 6 | 🟢 Implemented | `backend/tests/test_domain_invariants.py` |
| **BKND-32** | State Machine Mutation Suite | False confidence in shallow green tests | Uncle Bob | P1 | Phase 6 | 🟢 Implemented | `backend/tests/test_state_machine_mutations.py` |
| **BKND-33** | Compose Contract Test Suite | Mock implementations drifting from services | Alex Xu | P1 | Phase 6 | 🟢 Implemented | `backend/tests/test_real_integrations.py` |
| **BKND-34** | Chaos & Failure Injection Matrix| Undetected crashes during lock acquisition | Alex Xu | P1 | Phase 6 | 🟡 In Progress | `backend/tests/test_redlock_concurrency.py` |
| **BKND-35** | Golden Eval AI Harness (100) | Intent routing regressions in CI runs | Karpathy | P1 | Phase 6 | 🟢 Implemented | `backend/tests/test_ai_reasoning_evals.py` |

---

## 5. Master Register: Platform & Infrastructure (`INFRA-01` – `INFRA-30`)

| ID | Initiative Name | Problem Killed | Persona | Prio | Phase | Status | Verification Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **INFRA-01**| Multi-Stage CI Quality Gate | Phantom CI claims and unverified pushes | SRE Lead | P0 | Phase 0 | 🟢 Implemented | `.github/workflows/ci.yml` |
| **INFRA-02**| Clean-Checkout Verification | Undocumented manual setup requirements | Uncle Bob | P0 | Phase 0 | 🟢 Implemented | `scripts/verify-clean-checkout.sh` |
| **INFRA-03**| Pinned Dependency Locking | Unpinned dependency drift breaking builds | Uncle Bob | P0 | Phase 0 | 🟢 Implemented | `backend/requirements.txt` |
| **INFRA-04**| Playwright Landmark Smoke | Obsolete `/whiteboard` tests blocking gates | Jordan Walke | P0 | Phase 0 | 🟢 Implemented | `frontend/tests/` |
| **INFRA-05**| CI/Local Parity Engine | Mismatched service tags between CI & dev | Alex Xu | P0 | Phase 0 | 🟢 Implemented | `deploy/docker-compose.yml` |
| **INFRA-06**| Hardened Compose Ordering | Startup race conditions between services | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `deploy/docker-compose.yml` |
| **INFRA-07**| MinIO Bucket Provisioner | `NoSuchBucket` runtime exceptions | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `deploy/docker-compose.yml` (minio-init) |
| **INFRA-08**| 12-Factor Secrets Contract | Hardcoded passwords and secret leaks | SRE Lead | P0 | Phase 0 | 🟢 Implemented | `scripts/verify-clean-checkout.sh` |
| **INFRA-09**| Resource Limits & Restarts | Unbounded memory usage & OOM kills | Uncle Bob | P1 | Phase 2 | 🟢 Implemented | `deploy/docker-compose.yml` |
| **INFRA-10**| Rationalized Redis 7.2 ADR | Complex 5-node Redlock claims on 1 VM | Alex Xu | P1 | Phase 2 | 🟢 Implemented | `deploy/docker-compose.yml` |
| **INFRA-11**| Multi-Stage Non-Root Images | Running container processes as root | SRE Lead | P0 | Phase 2 | 🟢 Implemented | `deploy/Dockerfile.backend` |
| **INFRA-12**| Graceful Shutdown Protocol | SIGKILL mid-execution abandoning locks | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `backend/app/api/server.py` |
| **INFRA-13**| Next.js Standalone Build | Build-time env baking & serverless traps | Jordan Walke | P0 | Phase 2 | 🟢 Implemented | `frontend/next.config.mjs` |
| **INFRA-14**| Single-Worker ADR Blueprint | Multi-worker memory crashes | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `docs/` |
| **INFRA-15**| Approval Sweeper Daemon | Unswept expired approvals blocking queues | Uncle Bob | P0 | Phase 2 | 🟢 Implemented | `backend/app/core/workflow_engine.py` |
| **INFRA-16**| PostgreSQL Migration Engine | Decorative database running without schema | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `backend/migrations/003_vulcan_core_schema.sql` |
| **INFRA-17**| SQLite & PG Repository Adapters| In-memory store unable to survive reboot | Uncle Bob | P0 | Phase 2 | 🟢 Implemented | `backend/app/adapters/sqlite_catalog_repository.py` |
| **INFRA-18**| pgvector HNSW Catalog Schema | Fake catalog search over static Python dict | Karpathy | P0 | Phase 2 | 🟢 Implemented | `backend/app/adapters/postgres_catalog_repository.py` |
| **INFRA-19**| Live MinIO Gateway Contracts | S3 upload mocks generating broken URLs | Alex Xu | P1 | Phase 2 | 🟢 Implemented | `backend/tests/test_s3_multipart.py` |
| **INFRA-20**| Resilient DB Pool Manager | Socket exhaustion on transient blips | SRE Lead | P1 | Phase 2 | 🟢 Implemented | `backend/app/adapters/postgres_catalog_repository.py` |
| **INFRA-21**| Probe Split: /healthz /readyz| Health checks pegging CPU under load | Alex Xu | P0 | Phase 2 | 🟢 Implemented | `backend/app/api/routes.py` |
| **INFRA-22**| Prometheus Metrics (/metrics) | Blind operation without Prometheus metrics | SRE Lead | P0 | Phase 6 | 🟢 Implemented | `backend/app/api/routes.py` |
| **INFRA-23**| AI Cost & Token Telemetry | Untracked LLM spend and quota overrun | Karpathy | P1 | Phase 6 | 🟢 Implemented | `backend/app/use_cases/resolve_intent.py` |
| **INFRA-24**| Structured JSON Logging | Unstructured logs unparseable by Datadog | SRE Lead | P1 | Phase 6 | 🟡 In Progress | `backend/app/core/` |
| **INFRA-25**| Universal Correlation ID | Disconnected traces across REST/WS/DB | Jordan Walke | P1 | Phase 6 | 🟢 Implemented | `backend/app/domain/entities.py` |
| **INFRA-26**| Python 3.12/3.14 Parity | LLVM and wheel compilation errors | Karpathy | P0 | Phase 0 | 🟢 Implemented | `backend/pyproject.toml` |
| **INFRA-27**| Golden Eval Dataset in CI | AI behavior silently drifting on prompt edits | Uncle Bob | P1 | Phase 6 | 🟢 Implemented | `backend/tests/test_ai_prompt_injection_golden.py` |
| **INFRA-28**| Backup/Restore RTO Drills | Untested disaster recovery procedures | SRE Lead | P0 | Phase 6 | 🟡 In Progress | `scripts/drills/` |
| **INFRA-29**| Chaos Engineering Drill Suite | Unpredicted cascading failures under loss | Alex Xu | P1 | Phase 6 | 🟡 In Progress | `scripts/drills/` |
| **INFRA-30**| Release Pipeline & SBOM Scan | Deploying images with uninspected CVEs | SRE Lead | P0 | Phase 6 | 🟢 Implemented | `.github/workflows/deploy.yml` |

---

## 6. Master Register: Registry Crawling & Curation (`REG-01` – `REG-08`)

| ID | Initiative Name | Problem Killed | Persona | Prio | Phase | Status | Verification Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **REG-01**| Registry Crawler & Store | Manual module data entry into catalog | Alex Xu | P0 | Phase 1 | 🟢 Implemented | `backend/app/adapters/registry_crawler.py` |
| **REG-02**| Curation Gate & PR Drafter | Unvetted public code executing in prod | Platform Lead | P0 | Phase 1 | 🟢 Implemented | `backend/app/adapters/registry_crawler.py` |
| **REG-03**| Typed Schema Transformer | Parameter guesswork on untyped HCL | Karpathy | P0 | Phase 1 | 🟢 Implemented | `backend/app/adapters/terraform_ingestion.py` |
| **REG-04**| Security & Static Scans | Candidates containing malicious playbooks | Platform Lead | P1 | Phase 2 | 🟡 In Progress | `scripts/verify-clean-checkout.sh` |
| **REG-05**| Composite Stack Artifacts | Runtime LLM authoring of multi-tier infra | Uncle Bob | P0 | Phase 1 | 🟢 Implemented | `backend/app/adapters/stack_composer.py` |
| **REG-06**| Upstream Drift Monitor | Stale packages and unpatched upstream CVEs | Platform Lead | P2 | Phase 6 | ⚪ Planned | `scripts/crawl_registries.py` |
| **REG-07**| License Policy & BUSL Gate | Accidental use of non-compliant licenses | Platform Lead | P0 | Phase 1 | 🟢 Implemented | `backend/app/adapters/registry_crawler.py` |
| **REG-08**| Curation Deck Console UI | CLI-only candidate triage and approvals | Jordan Walke | P0 | Phase 5 | 🟢 Implemented | `frontend/app/matrix/page.tsx` |

---

## 7. Next Milestones & Focus Areas

1. **Complete In-Progress Drill Harnesses (`INFRA-28`, `INFRA-29`, `BKND-34`):**
   - Automated chaos scripts executing Redis drop, PostgreSQL disconnect mid-execution, and S3 multipart abort verification.
2. **Dynamic Task Table Virtualization (`UI-21`):**
   - TanStack Virtual table integration to guarantee constant $O(1)$ DOM nodes for 10,000+ catalog items.
3. **Decoupled Worker Fleet (`BKND-18`):**
   - Dedicated Celery/RQ worker process pool separating FastAPI event loop from long-lived 75-runner Ansible/Terraform subprocesses.
