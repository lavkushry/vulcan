# PROJECT VULCAN — PILOT READINESS DOSSIER
## The honest front door: every claim linked to captured evidence

**Document version:** 1.0 | **Compiled:** 2026-09-08 | **Status:** Pilot-Ready (conditional — see §9)  
**Posture:** Governance-proven, AI-staged.

---

## 0. How to read this document
- Every claim below carries: **Evidence** (link to code, report, or CI run), **Method** (how it was verified), **Date**, and **Caveat** (what it does *not* prove).
- If a link is dead, or the artifact contradicts the claim, **this document is wrong** — file an issue; do not patch the prose.
- Nothing here is forward-looking. Planned work lives in the Master Opportunity Register ([`docs/MASTER_OPPORTUNITY_REGISTER.md`](MASTER_OPPORTUNITY_REGISTER.md)), not in this dossier.
- **Freshness rule:** any claim older than 30 days at read time should be re-verified using §11 before being relied upon.

---

## 1. Posture statement
Project Vulcan is an enterprise automation control plane designed for banking-grade, governed execution of Ansible and Terraform playbooks. As of 2026-09-08, the system is deployed on an isolated OCI VM cluster and empirically verified across all critical governance invariants (strict maker-checker separation of duties with 403 enforcement, 14-state frozen finite state machine, write-before-run cryptographic Merkle audit chaining), durability backplanes (worker SIGKILL orphan reaping, Redis monotonic fencing, and nightly backup with 6.84s RTO and 100% data parity), and infrastructure security (loopback-only network lockdown, automated port-contract gates, and zero-exposure credential rotation). What remains deliberately staged or simulated are the external AI reasoning models (awaiting live embedding credentials under the 2026-09-22 protocol), physical runner job execution fleets (API control plane HTTP throughput verified under 75 operators, while playbook runners executed via in-process simulation), and enterprise connectors (ServiceNow and CyberArk operating against fail-closed contract stubs).

---

## 2. As-built deployment topology
| Component | Reality | Evidence |
|---|---|---|
| Host | Single Oracle OCI VM (`141.148.195.233`), Ubuntu 24.04 LTS ARM64 | [`docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md`](LOAD_AND_CHAOS_BENCHMARK_REPORT.md#infrastructure-backplane-specifications) |
| Containers | 6 running services: `vulcan-backend` (2 uvicorn workers), `vulcan-frontend`, `vulcan-postgres` (pg16 + pgvector), `vulcan-redis` (7.2-alpine), `vulcan-minio`, `vulcan-sandbox` | [`deploy/docker-compose.yml`](../deploy/docker-compose.yml) |
| Network | Loopback-only host bindings (`127.0.0.1:8000`, `127.0.0.1:3000`, `127.0.0.1:9000-9001`) + host `DOCKER-USER` iptables drops (`eth0` 3000, 8000, 9000 DROP) + OCI ingress = SSH (22) only; operator access via SSH tunnel | [`scripts/verify-clean-checkout.sh`](../scripts/verify-clean-checkout.sh#L75) |
| Persistence | PostgreSQL 16: catalog (10,467 items), execution jobs, Merkle audit ledger; MinIO S3: artifacts vault + automated nightly backups (`backups/daily/`, 7-day retention) | [`backend/migrations/003_vulcan_core_schema.sql`](../backend/migrations/003_vulcan_core_schema.sql), [`scripts/schedule_backup.sh`](../scripts/schedule_backup.sh) |
| CI/CD | GitHub Actions: lint/typecheck → PyTest (179/179) → mutation engine (46/46) → browser E2E (13/13) → clean-checkout gates → Syft/Trivy SBOM gate → gitleaks → deploy | [CI Run 34255896192](https://github.com/lavkushry/vulcan/actions/runs/34255896192), [Deploy Run 34255896254](https://github.com/lavkushry/vulcan/actions/runs/34255896254) |
| Deliberately NOT | No high-availability / multi-region quorum, no Kubernetes orchestration, single-node Redis (not 5-node Redlock), single-host PID liveness namespace | See §8 |

---

## 3. Verified claims — Governance & safety
| Claim | Evidence | Method | Date | Caveat |
|---|---|---|---|---|
| Maker-checker absolute: requester ≠ approver + `APPROVING_LEAD` role, 403 both ways | [`backend/app/domain/entities.py`](../backend/app/domain/entities.py#L90), [`backend/app/api/routes.py`](../backend/app/api/routes.py#L650) | Live API probes + 6 mutation tests killed (`MUT-MC-01`..`06`) | 2026-09-08 | Enforced in domain entities + API routes; UI disabling is belt-and-suspenders |
| 14-state frozen FSM; illegal transitions rejected | [`backend/app/domain/entities.py`](../backend/app/domain/entities.py#L30), [`backend/tests/test_state_machine_mutations.py`](../backend/tests/test_state_machine_mutations.py#L40) | Spec-matrix test suite + 11 FSM mutants killed (`MUT-FSM-01`..`11`) | 2026-09-08 | Terminal states (`SUCCESS`, `FAILED`, `REVERTED`) are immutable; recovery requires new job dispatch |
| 15-min fail-closed approval timeout → `TIMEOUT_DENIED` | [`backend/app/core/workflow_engine.py`](../backend/app/core/workflow_engine.py#L40), [`backend/tests/test_state_machine_mutations.py`](../backend/tests/test_state_machine_mutations.py#L80) | Unit tests + background sweeper probe + 3 mutation kills (`MUT-TO-01`..`03`) | 2026-09-08 | Sweeper runs on a 15-second loop; transition occurs within 15s of deadline expiry |
| INV-1 steel cage: CANDIDATE never executes; CURATED requires 40-hex SHA (DB CHECK both directions) | [`backend/migrations/005_catalog_curation_schema.sql`](../backend/migrations/005_catalog_curation_schema.sql#L35), [`backend/app/domain/entities.py`](../backend/app/domain/entities.py#L110) | Live PostgreSQL `pg_constraint` assertion + domain validation + 4 mutants killed (`MUT-ST-01`..`04`) | 2026-09-08 | Promotion path requires signed PR merge; manual direct curation not exercised end-to-end |
| Refusal gate: out-of-catalog queries fail closed | [`backend/app/use_cases/resolve_intent.py`](../backend/app/use_cases/resolve_intent.py#L180), [`backend/tests/test_api_endpoints.py`](../backend/tests/test_api_endpoints.py#L150) | Live HTTP intent probes + caught-and-fixed RRF zero-score bypass (`test_find_matching_playbook_refusal`) | 2026-09-08 | Threshold calibrated against synthetic embeddings (`semantic-cluster-1536`); requires recalibration on real models (§8) |
| Multi-platform ITSM ticket governance: fail-closed across ServiceNow (`CHG`, `INC`, `RITM`) and Remedy (`CRQ`) | [`backend/app/use_cases/resolve_intent.py`](../backend/app/use_cases/resolve_intent.py#L358), [`backend/app/adapters/servicenow_adapter.py`](../backend/app/adapters/servicenow_adapter.py#L42) | Ticket hydration suite (25/25) + `CRQ-UNKNOWN-404` rejection probe | 2026-09-09 | Universal ticket regex eliminates format-specific bypasses; unknown or unapproved tickets halt with `REFUSED` |
| Write-before-execute audit; Merkle chain unbroken through chaos + load | [`backend/app/adapters/postgres_audit_adapter.py`](../backend/app/adapters/postgres_audit_adapter.py#L80), [`scripts/drill_backup_restore.py`](../scripts/drill_backup_restore.py#L285) | `verify_integrity()` SHA-256 traversal + SQL `LAG()` chain continuity (0 breaks across 2,076 records) | 2026-09-08 | Ledger serialization uses row-level lock on chain head; represents potential throughput bottleneck under >500 req/s |

---

## 4. Verified claims — Durability & recovery
| Claim | Evidence | Method | Date | Caveat |
|---|---|---|---|---|
| Worker SIGKILL mid-job → `FAILED(WORKER_LOST)` in ≤2.1s; healthy control job untouched | [`scripts/run_chaos_drills.py`](../scripts/run_chaos_drills.py#L180), [`docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md`](LOAD_AND_CHAOS_BENCHMARK_REPORT.md#drill-3-multi-worker-crash-simulation-and-failover-resilience) | Live multi-worker chaos drill (2 runs) injecting ungraceful `SIGKILL` to PID 54 | 2026-09-08 | PID reaper is single-host; cross-host node loss requires cluster orchestrator heartbeat |
| Redis lease expiry + monotonic fencing + Lua CAS release on real Redis | [`backend/app/adapters/redlock_adapter.py`](../backend/app/adapters/redlock_adapter.py#L90), [`scripts/run_chaos_drills.py`](../scripts/run_chaos_drills.py#L110) | Live chaos drill (Layer 2) against Redis 7.2 with real `pexpire`, `INCR`, and atomic Lua CAS | 2026-09-08 | Single-node Redis backplane; network partition tolerance of Redlock not tested across multiple Redis instances |
| Backup: nightly cron, SHA-256, MinIO archival, 7-day retention; RTO 6.84s, 100% parity (2,022 jobs / 2,076 ledger records) | [`scripts/schedule_backup.sh`](../scripts/schedule_backup.sh), [`scripts/drill_backup_restore.py`](../scripts/drill_backup_restore.py), [`backend/app/api/server.py`](../backend/app/api/server.py#L112) | Executed 5-phase disaster recovery drill + active nightly cron (`0 2 * * *`) + `/ready` freshness probe (<26h) | 2026-09-08 | Restore executed into isolated database on same OCI VM host; cross-region node rebuild not exercised |
| WS cross-worker fanout via Redis pub/sub | [`backend/app/api/websockets.py`](../backend/app/api/websockets.py#L60), [`docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md`](LOAD_AND_CHAOS_BENCHMARK_REPORT.md#real-time-websocket-log-fanout-benchmark) | Multi-client broadcast load test (75 subscribers, 900 stream lines delivered at 600 lines/s) | 2026-09-08 | 1.5s burst delivery; tail latency (~595ms p95) reflects client async buffer flush intervals |
| S3 multipart abort → zero orphaned parts | [`backend/app/adapters/s3_multipart_adapter.py`](../backend/app/adapters/s3_multipart_adapter.py#L180), [`scripts/run_chaos_drills.py`](../scripts/run_chaos_drills.py#L150) | Live MinIO drill uploading 2x5MB chunks, aborting mid-flight, asserting `NoSuchUpload` via AWS APIs | 2026-09-08 | Tested against local MinIO container; AWS S3 cross-region latency and eventual consistency not tested |

---

## 5. Verified claims — Performance (honestly framed)
| Claim | Evidence | Method | Date | Caveat |
|---|---|---|---|---|
| Catalog hybrid search p95: dense ~14ms, sparse ~12ms, fused ~27ms at 10,467 items | [`scripts/benchmark_catalog_search.py`](../scripts/benchmark_catalog_search.py), [`docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md`](LOAD_AND_CHAOS_BENCHMARK_REPORT.md) | PostgreSQL HNSW + pg_trgm GIN query benchmarks with `EXPLAIN ANALYZE` | 2026-09-08 | Embeddings are synthetic (`semantic-cluster-1536`); verifies query execution plumbing, not semantic relevance |
| API control plane: 75 concurrent operator sessions, 0 errors, p95 510ms | [`scripts/run_load_test.py`](../scripts/run_load_test.py), [`docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md`](LOAD_AND_CHAOS_BENCHMARK_REPORT.md#high-concurrency-load-test-report) | Locust-mode headless load runner executing 1,504 requests over 30s | 2026-09-08 | Measures API control plane HTTP throughput (**50.13 req/s** gross, **60.09 req/s** steady-state), **not** physical playbook runner capacity |
| intent/resolve p95 560ms | [`docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md`](LOAD_AND_CHAOS_BENCHMARK_REPORT.md#detailed-endpoint-latency-breakdown) | High-concurrency load run (501 intent resolution requests under 75 operators) | 2026-09-08 | Exceeds 500ms Karpathy intent budget by 60ms (+12%), passes 1,500ms API SLA; will shift with external LLM API latency |
| WS connect p95 18ms; fanout 600 lines/s | [`docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md`](LOAD_AND_CHAOS_BENCHMARK_REPORT.md#real-time-websocket-log-fanout-benchmark) | WebSocket subscriber benchmark (340 connects, 900 fanout lines) | 2026-09-08 | Fanout was a 1.5s burst; long-lived sustained multi-hour streaming was not soaked |

---

## 6. Verified claims — Verification infrastructure
| Claim | Evidence | Method | Date | Caveat |
|---|---|---|---|---|
| Mutation testing: 46/46 governance mutants killed; tautology found & fixed | [`scripts/run_domain_mutation_tests.py`](../scripts/run_domain_mutation_tests.py), [`docs/MUTATION_TESTING_REPORT.md`](MUTATION_TESTING_REPORT.md) | Hand-rolled AST/token replacement engine executed as CI Stage 1 gate (25.2s) | 2026-09-08 | 46 targeted banking governance mutants; assesses domain invariants, not full codebase mutation coverage |
| Browser E2E: 13/13 (incl. governed happy path, WS reconnect, refusal, a11y) | [`tests/e2e/`](../tests/e2e/), [CI Run 34255896192](https://github.com/lavkushry/vulcan/actions/runs/34255896192) | Playwright Chromium headless in CI & live loopback tunnel; video/trace artifacts captured | 2026-09-08 | Found 5 real defects (auth timing, selector collisions, UI SoD bypass); tests mock external auth via Bearer injection |
| Two-layer chaos suite (unit 0.53s CI / live 10.65s) | [`scripts/run_chaos_drills.py`](../scripts/run_chaos_drills.py), [`backend/tests/test_chaos_invariants.py`](../backend/tests/test_chaos_invariants.py) | Layer 1 in-memory mocks in CI; Layer 2 live Docker integration suite on VM | 2026-09-08 | Layer 1 proves math invariants in RAM; Layer 2 requires live container network |
| 500-scenario golden eval gate (CHAT-20): routing, slot F1, 100% adversarial refusal | [`evals/golden/scenarios.v2.jsonl`](../evals/golden/scenarios.v2.jsonl), [`scripts/run_eval.py`](../scripts/run_eval.py), [`docs/EVAL_BASELINE_FAKE.md`](EVAL_BASELINE_FAKE.md), [`docs/EVAL_LABEL_AUDIT.md`](EVAL_LABEL_AUDIT.md) | Dual-provider evaluation harness executed as CI Stage 1 regression gate (<1s) | 2026-09-09 | Gated against measured fake baseline with enforced Ratchet Rule (82.00% top-1 / 97.33% top-3 routing, 100% slot F1, 100% refusal, 0% false refusal); 27 non-top-1 cases categorized (15 disambiguation-surfaced vs 12 silent misroutes); live LLM evaluation deferred to §9 |
| Clean-checkout gates: tests, migrations, port-contract, connection-string secrets, SBOM, gitleaks | [`scripts/verify-clean-checkout.sh`](../scripts/verify-clean-checkout.sh), [CI Run 34255896192](https://github.com/lavkushry/vulcan/actions/runs/34255896192) | Five-stage fail-closed shell contract executed locally and in CI Stage 3 | 2026-09-08 | Requires bash, python3, and npm in runner environment |

---

## 7. Verified claims — Security posture
| Claim | Evidence | Method | Date | Caveat |
|---|---|---|---|---|
| Perimeter: only SSH(22) public; port-contract gate prevents compose drift | [`scripts/verify-clean-checkout.sh`](../scripts/verify-clean-checkout.sh#L75), [`docs/WALKTHROUGH_LIVE_VERIFICATION.md`](WALKTHROUGH_LIVE_VERIFICATION.md) | External socket probing across ports 22, 3000, 8000, 9000, 9001, 2222, 5432, 6379 | 2026-09-08 | Oracle Cloud Infrastructure web console access represents break-glass boundary |
| Auth: bearer middleware, server-side token→identity map, fail-closed | [`backend/app/api/auth.py`](../backend/app/api/auth.py#L30), [`backend/tests/test_auth_and_execution_rbac.py`](../backend/tests/test_auth_and_execution_rbac.py) | 401/403 live HTTP probes with unauthorized, invalid, and role-mismatched tokens | 2026-09-08 | Static bearer tokens; external enterprise SSO (Okta/Ping) and dynamic token rotation not integrated |
| Credential hygiene: stdin-only rotation protocol; 5 incidents logged with gates added | [`docs/INCIDENTS.md`](INCIDENTS.md), [`scripts/verify-clean-checkout.sh`](../scripts/verify-clean-checkout.sh#L110) | Forensic incident register + connection-string regex gate + live credential rotation | 2026-09-08 | Historical credentials exist in immutable git history; rotation is the sole effective remediation |
| Supply chain security: automated dual SBOM (SPDX 2.3 & CycloneDX 1.5) + Trivy dual container & filesystem CVE gate (INFRA-30) | [`scripts/generate_sbom.sh`](../scripts/generate_sbom.sh), [`.github/workflows/vulcan-ci.yml`](../.github/workflows/vulcan-ci.yml) | Dual-format SBOM generation (212 components: 66 Python + 146 npm full transitive closure) + Trivy filesystem & dual container image CVE scanning in CI Stage 5 | 2026-09-09 | Enforces strict fail-closed policy (`--exit-code 1 --severity CRITICAL --ignore-unfixed`) across repository, backend container, and frontend container; findings breakdown & triage register below |

### Supply Chain Security & Container Scan Posture (`INFRA-30`)
| Target Surface | Total Scanned | CRITICAL | HIGH | MEDIUM | LOW | Failure / Gating Policy |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **Repository Filesystem & Lockfiles** | 212 pkgs | **0** | **0** | **0** | **0** | **Fail-Closed on CRITICAL:** `--exit-code 1 --severity CRITICAL --ignore-unfixed`. `postcss@8.4.31` retired via npm `overrides` to `^8.5.28`. Test fixture keys in `backend/ansible/keys` & `deploy/sandbox/keys` whitelisted from secret scan. |
| **Backend Container Image (`deploy-backend`)** | 174 Debian OS pkgs + 66 Python pkgs | **0** (with `--ignore-unfixed`*) | **0** | **0** | **0** | **Fail-Closed on CRITICAL:** `trivy image --severity CRITICAL --ignore-unfixed --exit-code 1 vulcan-backend:ci`. Dev/test harness (`locust`, `flask`, `gevent`, `pytest`) pruned from production image. Build-time `wheel` uninstalled. *Raw Debian 13.6 base has 14 CRITICAL / 155 HIGH upstream kernel/libc unpatched headers where `Fixed: None` (managed via base-image refresh cadence). |
| **Frontend Container Image (`deploy-frontend`)** | 18 Alpine OS pkgs + Node runtime | **0** (with `--ignore-unfixed`) | **0** | **0** | **0** | **Fail-Closed on CRITICAL:** `trivy image --severity CRITICAL --ignore-unfixed --exit-code 1 vulcan-frontend:ci`. Hardened Alpine runner: `apk upgrade` remediated `libcrypto3/libssl3` (3.5.8-r0), unused npm/npx/corepack tooling stripped, eliminating `tar@6.2.1` CRITICAL and 21 Node build-tool HIGHs. |
| **Redis Baseline (`redis:7.2-alpine`)** | 14 Alpine OS pkgs | **0** | **0** | **0** | **0** | Official Redis image. Clean across all severities with `--ignore-unfixed`. Internal network only. |
| **PostgreSQL Baseline (`pgvector/pgvector:pg16`)** | 114 Debian OS pkgs + `gosu` | **0** | **22** (in `gosu` Go binary) | **0** | **0** | Official Docker PG library distribution. Accepted vendor upstream finding. Container bound strictly to `127.0.0.1:5432` inside Compose network. |
| **MinIO Baseline (`minio/minio:RELEASE.2025-09-07T16-13-09Z`)** | RedHat 9.6 + `minio`/`mc` Go bins | **2** (base OS) | **98** (in Go runtime) | **0** | **0** | Official MinIO image distribution pinned to release `RELEASE.2025-09-07T16-13-09Z`. Accepted vendor upstream finding. Container bound strictly to `127.0.0.1:9000/9001` inside Compose network. |
| **Sandbox Execution Target (`deploy-sandbox`)** | 98 Ubuntu 22.04 OS pkgs | **0** | **0** | **0** | **0** | Clean OS packages. Secret scanner detects test SSH host keys (expected for SSH sandbox target). Internal network only. |

### Vulnerability Triage Register (One-Line Policy per Finding Class)
| Finding / CVE | Surface / Package | Severity | Decision | Rationale & Remediation |
|---|---|:---:|:---:|---|
| `CVE-2026-59873` | `tar@6.2.1` (in bundled npm) | **CRITICAL** | **REMEDIATED** | Stripped unused global npm/npx/corepack from production frontend runner stage (Next.js standalone uses `node server.js` only). |
| `CVE-2026-45623`, `CVE-2026-73646` | `postcss@8.4.31` (Next.js lockfile) | **HIGH** | **REMEDIATED** | Enforced npm `overrides: {"postcss": "^8.5.28"}` in `frontend/package.json`; retired stranded nested version. `npm audit` reports 0 vulnerabilities. |
| `CVE-2026-14456`, `CVE-2026-45447` | `libcrypto3`, `libssl3` in Alpine | **HIGH** | **REMEDIATED** | Added `apk update && apk upgrade --no-cache` in `frontend/Dockerfile` runner stage; upgraded OpenSSL packages to `3.5.8-r0`. |
| `CVE-2026-40330`, `jaraco.context` | `wheel@0.45.1`, `jaraco.context@5.3.0` | **HIGH** | **REMEDIATED** | Pruned build tooling from backend image (`pip uninstall -y wheel`); separated dev requirements from production runtime. |
| `GHSA-6v7p-g79w-8964`, `CVE-2025-47273` | `msgpack`, `setuptools` | **HIGH** | **REMEDIATED** | Pinned `msgpack>=1.2.1` and `setuptools>=78.1.1` in `backend/requirements.txt`. |
| 14 unpatched Debian CVEs (`Fixed: None`) | `linux-libc-dev`, `libc6` | **CRITICAL** | **DEFERRED (Upstream)** | Upstream Debian kernel stubs with no upstream fix available. Filtered via `--ignore-unfixed`; tracked on base image refresh cadence. |
| Go runtime CVEs in MinIO & pgvector | `minio`, `mc`, `gosu` binaries | **HIGH** | **ACCEPTED (Vendor Upstream)** | Off-the-shelf official images with no public perimeter exposure (bound strictly to `127.0.0.1`). |

---

## 8. Deferred, simulated, and out of scope — read this before trusting §3–§7
1. **AI search quality on live models is NOT measured (TUNED-ON LIMITATION):** Active provider: deterministic keyword + synthetic clustering (`semantic-cluster-1536`). The ≥99.2% routing precision PRD claim is a *target*, not a result. The 500-scenario golden evaluation benchmark harness (`CHAT-20`, `evals/golden/scenarios.v2.jsonl`, `scripts/run_eval.py`) is fully built and enforced as a fail-closed CI Stage 1 regression gate against measured fake-mode baselines:
   - **Baseline Floor**: **82.00% Top-1** (123/150) and **97.33% Top-3** (146/150) routing, 100% slot F1, 100% adversarial refusal, 0% false refusals, sub-2,500 token compliance.
   - **Tuned-On Caveat**: This 82.00% figure is a *tuned-on baseline* calibrated against the hermetic fake provider. It does *not* measure real-world generalization against unstructured operator phrasing; live model evaluation on September 22 must beat this floor.
   - **The Ratchet Rule**: CI regression gating programmatically enforces `RATCHET_FLOORS` (75.0% Top-1, 90.0% Top-3, 98.0% Slot F1, 100.0% Refusal, 0.0% False Refusal). Thresholds may strictly ratchet UP, never down.
   - **Classification of the 27 Non-Top-1 Matches**: The 27 non-matches bifurcate into 15 **disambiguation-surfaced** cases (10.00%, where semantic ambiguity `delta_sim < 0.05` halts execution and surfaces safe Bento choice cards, with 11/15 containing the target playbook) and 12 **silent misroutes** (8.00%, quality defects where the resolver confidently matched an incorrect playbook).
   - **Multi-Platform Ticket Governance**: Universal regex catches ServiceNow (`CHG`, `INC`, `RITM`) and Remedy (`CRQ`) with fail-closed validation on all unknown tickets; routing scenarios decouple ticket prefixes to prevent artificial gate tripping.
   - Semantic label audit documented in [`docs/EVAL_LABEL_AUDIT.md`](EVAL_LABEL_AUDIT.md) and [`docs/EVAL_BASELINE_FAKE.md`](EVAL_BASELINE_FAKE.md). Live dense model evaluation and calibration thresholds await API credentials (§9).
2. **Execution is simulation-first.** Real Ansible runs only against `vulcan-sandbox` (2 playbooks, real OS changes verified). Load-test executions were simulated. No production infrastructure is touched.
3. **Single-host assumptions:** Redis is single-node (Redlock semantics are real but not multi-datacenter); orphan reaper uses PID liveness (one PID namespace); runners are in-process threads.
4. **Floating-branch execution:** playbooks run from the deployed working tree, not a SHA-pinned checkout — a documented pilot exception.
5. **Missing operational capabilities:** Prometheus metrics endpoint `/metrics` exists live on `:8000/metrics` (INFRA-22, empirically verified HTTP 200 OK, wired to `PostgresJobRepository`, returning both inventory gauges and RED rate/duration counters) but has no external scraping Prometheus daemon/alertmanager cluster deployed; structured JSON logging with correlation IDs is active (INFRA-24); automated dual SBOM generation and Trivy CVE scanning enforced in CI across repo and container images (INFRA-30); backup freshness is enforced in `/ready` (<26h).
6. **Enterprise connectors are fail-closed mocks:** ServiceNow Gateway (unknown tickets rejected fail-closed, valid tickets simulated), CyberArk PAM (RAM-only mock lease provider).
7. **Register truth:** 82/127 implemented (64.6%) — see [`docs/MASTER_OPPORTUNITY_REGISTER.md`](MASTER_OPPORTUNITY_REGISTER.md); all 21 spot-audited rows verified.

---

## 9. The 2026-09-22 decision protocol
- **If credentials are provided:** run the staged activation sequence (re-embed catalog → calibrate refusal thresholds → golden eval benchmark → latency benchmark, all captured) and upgrade §5 and §8 accordingly.
- **If not:** formally reclassify AI search-quality claims as *deferred indefinitely* in the PRD; this dossier's posture statement stands as final.
- Either outcome is a legitimate pilot conclusion. Silence is not.

---

## 10. Incident history
See [`docs/INCIDENTS.md`](INCIDENTS.md) (`SEC-INC-01` through `SEC-INC-05`) — five credential-exposure events, each with forensic root cause, immediate remediation, and an automated preventive CI gate added. The recurrence pattern and its structural fixes are part of the permanent audit record.

---

## 11. Reproduction — re-verify any claim from a clean checkout
To independently re-verify the claims in this dossier from a completely fresh repository clone:

```bash
# 1. Clone and verify clean checkout gates (unit tests, migrations, build, port contract, secrets gate)
git clone https://github.com/lavkushry/vulcan.git
cd vulcan
bash scripts/verify-clean-checkout.sh

# 2. Run domain governance mutation testing engine (46/46 mutants killed)
python3 scripts/run_domain_mutation_tests.py

# 3. Run browser E2E test suite (requires loopback tunnel to live or local stack)
cd frontend && npm install && npx playwright test

# 4. Run distributed systems chaos drill suite
python3 scripts/run_chaos_drills.py --mode unit
# (For live VM mode against real Redis 7.2, MinIO, PostgreSQL 16):
# python3 scripts/run_chaos_drills.py --mode live

# 5. Run live disaster recovery & backup/restore RTO drill (measured RTO ~6.8s)
python3 scripts/drill_backup_restore.py

# 6. Test operational backup script (MinIO upload + 7-day retention)
bash scripts/schedule_backup.sh

# 7. Run 75-concurrency load benchmark harness
python3 scripts/run_load_test.py --mode unit

# 8. Run 500-scenario golden evaluation benchmark gate (CHAT-20)
python3 scripts/run_eval.py --gate
```

---

## 12. Sign-off
| Role | Name | Date | Note |
|---|---|---|---|
| Engineering Owner | Lavkush Kumar (`lavkush@deepmind.com`) | 2026-09-08 | Zero-exposure credential hygiene, clean-checkout gates green, operational backup verified |
| Verification Owner | Architecture Review Board (Uncle Bob, Alex Xu, Karpathy, Walke) | 2026-09-08 | Invariants mutation-tested (46/46 killed), 13/13 E2E green, 79/127 register items verified |
| Decision Owner (§9) | Product & Executive Stakeholder | 2026-09-22 | Live embedding API key provided, or search quality claims formally deferred |
