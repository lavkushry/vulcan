# Architecture Reality Matrix — Project Vulcan
**Document Version:** 1.0.0-CANONICAL  
**Last Updated:** 2026-09-07  
**Host Target:** Oracle OCI Ubuntu 22.04 LTS (`141.148.195.233`)  
**Production Endpoints:**  
- Web Console: [http://141.148.195.233:3000/](http://141.148.195.233:3000/)  
- Backend Control Plane: [http://141.148.195.233:8000/](http://141.148.195.233:8000/)  
- Swagger API Docs: [http://141.148.195.233:8000/docs](http://141.148.195.233:8000/docs)  
- Readiness Probe: [http://141.148.195.233:8000/ready](http://141.148.195.233:8000/ready)  

---

## 1. Executive Summary & Philosophy

This document represents the single authoritative source of truth for the implementation reality of Project Vulcan. Every subsystem and component is cataloged with an explicit **Status** and an **Evidence Quality** standard. No feature or property is claimed as "production-ready" without a reproducible, captured verification trace.

### Status Taxonomy
* 🟢 **PROVEN / LIVE-VERIFIED:** Functional code running against live infrastructure (or Docker services), backed by automated CI gates, unit tests, and captured empirical logs.
* 🟢🟡 **FUNCTIONAL WITH BOUNDED CAVEATS:** Architecturally complete and contract-tested, with specific operational caveats explicitly documented (e.g., local semantic clustering vs external cloud LLMs, single-node Redis vs 5-node Redlock).
* 🟡 **PARTIAL / DESIGNED:** Working mechanics present in code, but running in single-node/prototype mode or lacking formal production backends.
* 🔴 **EXPLICITLY STUBBED / MOCK:** Explicitly bounded non-goals or simulated adapters (e.g., real ServiceNow instances, real CyberArk PAM vaults, multi-worker HA).

---

## 2. The Architecture Reality Matrix

| Subsystem | Component | Status | Reality & Evidence Quality | Verification Artifacts / Commits |
| :--- | :--- | :---: | :--- | :--- |
| **CI/CD** | Gated Pipeline (test $\to$ gitleaks $\to$ probes $\to$ deploy) | 🟢 | **Live-verified:** Dual GitHub Actions workflows (`CI Gate` & `CD Deploy`). Gated by Gitleaks secrets scanner, clean-checkout gate, 234 backend tests across 25 suites, and 16/16 Playwright E2E tests across 6 suites. Zero push-without-gates. | [`.github/workflows/ci.yml`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.github/workflows/ci.yml)<br>[`.github/workflows/deploy.yml`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.github/workflows/deploy.yml)<br>Runs: `34057402070`, `34057402217` |
| **Infra** | 6 Containers on OCI VM | 🟢 | **Live-verified:** All 6 containers (`frontend`, `backend`, `postgres`, `redis`, `sandbox`, `minio`) healthy. Verified `/ready` contract checking catalog, audit chain, and lock manager. | [`deploy/docker-compose.yml`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/deploy/docker-compose.yml)<br>`docker ps` on `141.148.195.233` |
| **Network Security** | Public UI/API & Hardened Data Plane | 🟢 | **Live-verified:** Ports 3000 (Next.js) and 8000 (FastAPI) exposed on `0.0.0.0`. Internal data services (`postgres:5432`, `redis:6379`, `sandbox:22`, `minio:9000/9001`) strictly unexposed to host or bound to loopback. | [`deploy/docker-compose.yml`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/deploy/docker-compose.yml)<br>Commit `fb12f5a` |
| **Secrets** | Zero-leak Rotation & Scanning | 🟢 | **Live-verified:** Environment-based injection, zero plaintext credentials in git, CLI arguments, or docker commands. Gitleaks scan gate enforced in CI on every push. | [`.github/workflows/deploy.yml`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.github/workflows/deploy.yml)<br>[`scripts/deploy-server.sh`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/scripts/deploy-server.sh) |
| **API Auth** | Bearer Middleware & Server Token Map | 🟢 | **Live-verified:** Constant-time token authentication against server-side map (`VULCAN_API_TOKENS`). Rejects missing/invalid tokens with 401 `ERR_VULCAN_UNAUTHENTICATED`. Fails closed (503) when unconfigured. | [`backend/app/api/auth.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/api/auth.py)<br>[`backend/tests/test_api_token_auth.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_api_token_auth.py) |
| **Approval RBAC (D4)** | Separation of Duties + Role Enforcement | 🟢 | **Live-verified:** 403 on self-approval (`MakerCheckerViolationError`). 403 when approved by unauthorized role (Operator). 200 OK only when approved by user possessing `Permission.JOB_APPROVE` (`lead.bob`). | [`backend/app/domain/roles_and_policies.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/domain/roles_and_policies.py)<br>[`backend/tests/test_rbac_governance.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_rbac_governance.py) |
| **Execute RBAC (Gap 2)** | Workflow Dispatch Role & Audit Ledger | 🟢 | **Live-verified:** Operator dispatch blocked (403); Lead dispatch authorized (200). Generates explicit `EXECUTION_TRIGGERED` audit ledger record before execution commences. | [`backend/app/api/routes.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/api/routes.py)<br>[`backend/tests/test_rbac_governance.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_rbac_governance.py) |
| **WebSocket Auth** | Query-param Token & Event Hub | 🟢 | **Live-verified:** Missing or invalid token terminates socket with code 4401 (`ERR_VULCAN_UNAUTHENTICATED`). Authenticated connection streams live stdout events and replays buffered history via `last_seq`. | [`backend/app/api/websockets.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/api/websockets.py)<br>[`backend/tests/test_websocket_auth.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_websocket_auth.py) |
| **Domain FSM** | 14-State Frozen Matrix + Invariant Suite | 🟢 | **Live-verified:** 150+ illegal `(from, to)` state transitions strictly rejected (`StateTransitionError`). Fail-closed timeout sweeper transitions to `TIMEOUT_DENIED` after 900s. RUNNING $\to$ QUEUED race fixed. | [`backend/app/domain/entities.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/domain/entities.py)<br>[`backend/tests/test_state_machine_mutations.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_state_machine_mutations.py) |
| **Maker-Checker** | Full Flagship Lifecycle & OS Execution | 🟢 | **Live-verified:** Submit $\to$ self-403 $\to$ Lead approve $\to$ dispatch-403 $\to$ Lead dispatch $\to$ **real Ansible execution over SSH on sandbox container** $\to$ exit code 0. Ledger persisted in Docker volume. | Flagship Job: `EXEC-569F5E`<br>SQLite Job: `job-9fb4cbc3`<br>Lines 32–34 in `audit_ledger.jsonl` |
| **Audit Ledger** | Merkle SHA-256 Chain & Tamper Detection | 🟢 | **Live-verified:** Every state mutation commits a cryptographic row with `prev_hash` $\to$ `current_hash`. Tamper detection test verifies modifying any historical payload invalidates the entire Merkle chain. | [`backend/app/adapters/crypto_audit_adapter.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/crypto_audit_adapter.py)<br>[`backend/tests/test_sqlite_persistence.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_sqlite_persistence.py) |
| **Job Persistence** | SQLite WAL & Container Volume | 🟢 | **Live-verified:** Jobs, events, and approvals persist in SQLite with WAL mode. Verified across container restarts and redeployments on named volume `deploy_backend_data`. | [`backend/app/adapters/sqlite_repositories.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/sqlite_repositories.py)<br>Volume: `deploy_backend_data` |
| **Playbook Execution** | Real Ansible over SSH on `vulcan-sandbox` | 🟢 | **Live-verified:** Live SSH execution into Ubuntu sandbox. Applied real system hardening (`sshd_config`, `issue.net`), exit code 0. Post-flight health probes verify target configuration. | [`backend/app/use_cases/runner.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/use_cases/runner.py)<br>Sandbox Container: `vulcan-sandbox` |
| **Object Storage** | Live MinIO Multipart + Presigned URLs | 🟢 | **Live-verified:** Decoupled data plane handles chunked uploads. Tested end-to-end: initiate $\to$ PUT 5MB parts $\to$ complete $\to$ SHA256 checksum $\to$ orphaned upload sweeper. Browser host-header rewrite verified. | [`backend/app/adapters/s3_multipart_adapter.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/s3_multipart_adapter.py)<br>[`backend/tests/test_s3_multipart.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_s3_multipart.py) |
| **Redis** | Authenticated Mutex & Pub/Sub Backplane | 🟢 | **Live-verified:** Protected by `requirepass`. Reject with `NOAUTH` without password, responds `PONG` with password. Backend connects via credentialed URL. | [`deploy/docker-compose.yml`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/deploy/docker-compose.yml)<br>[`backend/app/adapters/redlock_adapter.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/redlock_adapter.py) |
| **Catalog Substrate** | PostgreSQL 16 pgvector, 10,467 Items, Hybrid RRF | 🟢 | **Live-verified:** Cutover to PostgreSQL 16 with HNSW cosine index (`m=16, ef=64`) and `tsvector` GIN index. EXPLAIN-driven optimization eliminated WindowAgg seq scan (123ms $\to$ 14.28ms). Refusal gate 100% fail-closed. | [`backend/app/adapters/postgres_catalog_repository.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/postgres_catalog_repository.py)<br>Capture: [`docs/benchmark_semantic_capture.log`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/docs/benchmark_semantic_capture.log) |
| **Curation Gate** | CandidateStore Quarantine + DB CHECK Constraint | 🟢 | **Live-verified:** Candidate playbooks quarantined under INV-1 (`PolicyViolationError` on run). PostgreSQL table enforces `chk_catalog_curated_sha` CHECK constraint: promoting to CURATED requires a valid 40-character Git SHA. | [`backend/migrations/004_catalog_pgvector.sql`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/migrations/004_catalog_pgvector.sql)<br>[`backend/tests/test_postgres_catalog.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_postgres_catalog.py) |
| **Intent Resolution** | IEmbeddingProvider Multi-Provider Port & Disambiguation Gate | 🟢 | **Live-verified:** Abstract port implemented across Hermetic Fake, Hugging Face Serverless (`BAAI/bge-large-en-v1.5`), OpenRouter (`openai/text-embedding-3-small`), Gemini, and OpenAI. Dual-threshold refusal gate kills zero-score trap with provider-specific empirical calibration (`min_dense_no_sparse: 0.58` for HF). Ambiguous twins trigger `DISAMBIGUATION` ($\Delta_{\text{sim}} < 0.05$). Live 500-scenario golden evaluation on HF achieved 84.00% Top-1, 97.33% Top-3, 92.0% Operator-Reachable (+2.7% gain), 0.0% dead-ends (-2.7% reduction to zero), 100% slot F1, 100% adversarial refusal, and fail-closed quota handling (`INV-AI-01`). Gemini verified operational until daily quota (538.7/1,000 requests spent), then verified fail-closed. OpenRouter integrated with contract tests (live-call verified for auth & format; eval slot-filling staged). OpenAI staged/unverified. Attribution: routing & retrieval is live-AI verified (`bge-large`); slot extraction is deterministic grammar/regex FSM. | [`backend/app/ports/interfaces.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/ports/interfaces.py)<br>Live Eval: [`docs/EVAL_BASELINE_LIVE.md`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/docs/EVAL_BASELINE_LIVE.md)<br>Capture: [`docs/INTENT_RESOLUTION_CAPTURE.md`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/docs/INTENT_RESOLUTION_CAPTURE.md) |
| **Token Budget** | Real BPE Tokenizer & Working Memory | 🟢 | **Live-verified:** Real BPE tokenizer calculates token counts against 2,500-token budget. Clamped mock formulas permanently eliminated. | [`backend/app/use_cases/tokenizer.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/use_cases/tokenizer.py)<br>[`backend/tests/test_token_budget.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_token_budget.py) |
| **Registry Crawler** | Terraform Registry + Galaxy Ingestion Engine | 🟢 | **Live-verified:** Paginated crawling with rate-limiting backoff. 500 real public modules crawled, normalized, and ingested into PostgreSQL on the remote VM. | [`scripts/crawl_registries.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/scripts/crawl_registries.py)<br>Data: [`data/corpus/candidates_500.json`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/data/corpus/candidates_500.json) |
| **Frontend Console** | Next.js 15 Obsidian Glass, WebGL xterm.js | 🟢 | **Live-verified:** Production standalone build. Dynamic origin detection (`window.location.hostname`). Live xterm.js terminal stream. 16 static routes, 0 TypeScript errors. 16/16 Playwright E2E browser tests passing across 6 suites (including UI-14, UI-23, UI-25, UI-27). *Caveat: UI-25 Cluster Radar UI is browser-verified, but backend cluster consensus telemetry (/api/v1/clusters) is deterministic simulation.* | [`frontend/lib/env.ts`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/frontend/lib/env.ts)<br>[http://141.148.195.233:3000/](http://141.148.195.233:3000/) |
| **Distributed Mutex** | Redis Redlock Lua Scripts + Watchdog Heartbeat | 🟡 | **Functional:** Atomic lock acquisition with unique fencing token and lease auto-extension thread. Bounded caveat: Single-node Redis today (5-node quorum unearned for current pilot scale). | [`backend/app/adapters/redlock_adapter.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/redlock_adapter.py)<br>[`backend/tests/test_redlock_adapter.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_redlock_adapter.py) |
| **Opportunity Register** | 127 Consolidated Architectural Opportunities | 🟢 | **Frozen:** Version `4.1.0-FROZEN`. Complete canon across all domains (`UI-01`..`UI-28`, `CHAT-01`..`CHAT-26`, `BKND-01`..`BKND-35`, `INFRA-01`..`INFRA-30`, `REG-01`..`REG-08`). 126/127 items implemented (99.2%). 1 remaining item tracked in progress/planned: CHAT-26. | [`docs/MASTER_OPPORTUNITY_REGISTER.md`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/docs/MASTER_OPPORTUNITY_REGISTER.md) |

---

## 3. Explicitly Scoped Non-Goals (Still Genuinely 🔴)

The following items are intentionally isolated and must never be represented as production-ready without external integrations:

1. **Uncalibrated External LLM Calls:** Multi-provider architecture is fully implemented across `HuggingFaceEmbeddingProvider` (`BAAI/bge-large-en-v1.5`, live-verified & calibrated for routing), `OpenRouterEmbeddingProvider` / `OpenRouterChatProvider` (integrated with 34 contract tests; live-call verified for API connectivity), `GeminiEmbeddingProvider` (verified operational until daily quota, then fail-closed `INV-AI-01`), and `OpenAIEmbeddingProvider` (staged/unverified). Live LLM slot-filling remains staged (deterministic grammar/regex FSM is active for parameter extraction). In hermetic CI, offline `HermeticFakeEmbeddingProvider` is used to prevent external network flakiness.
2. **CyberArk PAM Production Safe Binding:** The enterprise Central Credential Provider (CCP) REST adapter (`CyberArkPAMProvider`) is fully implemented with mTLS client certificates, fail-closed handling, RAM-only checkout, and deterministic memory zeroization (`BKND-19`). Live production deployment requires binding to an enterprise-hosted CyberArk vault certificate and safe.
3. **Enterprise ServiceNow Instance Binding:** The ServiceNow adapter now implements real Table API and CMDB CI integration with multi-format date parsing, sub-200ms latency budget, and fail-closed handling (`CHAT-14`), with rich mock support for air-gapped dev environments. Live enterprise deployment requires binding to an enterprise ServiceNow instance with provisioned service account credentials.
4. **DAG Multi-Step Orchestration:** The runner executes single Ansible playbooks and Terraform plans sequentially. Multi-node DAG workflow dependency resolution is a future milestone.
5. **Full-Source AST Mutation Testing:** The codebase uses comprehensive state machine invariant mutation tests ([`test_state_machine_mutations.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/tests/test_state_machine_mutations.py)) covering all illegal state transitions and bypass vectors. Automated `mutmut` AST mutation testing remains a long-term testing enhancement.
6. **Horizontal Multi-Worker Clustering:** Uvicorn runs in single-worker mode. The background approval sweeper and WebSocket pub/sub backplane run within a single process loop. Horizontal scale-out to multi-worker fleets requires dedicated Celery/Temporal workers.

---

## 4. Maintenance Contract & Verification Protocol

Any change claiming to transition a component's status must satisfy the following verification protocol:

### Gate 1: Clean Checkout & Local Invariants
Must pass without manual intervention from a clean git clone:
```bash
./scripts/verify-clean-checkout.sh
```

### Gate 2: Live Remote Probing (Zero Plaintext Secrets)
Probes executed against the live remote deployment must use server-side token resolution and avoid plaintext credentials in shell history:
```bash
# Verify health and readiness
curl -s http://141.148.195.233:8000/healthz
curl -s http://141.148.195.233:8000/ready

# Run intent resolution probes
python3 scripts/probe_intent.py --url http://141.148.195.233:8000 --output /tmp/intent_probe_results.json
```

### Gate 3: Reproducible Empirical Benchmark Capture
All documented latencies, recall percentages, and refusal rates must be generated by re-running the benchmark suite with console capture:
```bash
python3 scripts/benchmark_catalog_search.py --embedding-provider semantic --scale-all | tee docs/benchmark_semantic_capture.log
```
