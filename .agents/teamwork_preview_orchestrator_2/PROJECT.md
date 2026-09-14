# Project: Vulcan AI Control Plane Hackathon Submission Readiness

## Architecture
Vulcan is a governed multi-agent control plane for enterprise infrastructure automation. It implements Clean Architecture across 5 tiers:
1. **Presentation Tier**: Next.js 15 App Router, dual-pane AI assistant, xterm.js streaming console.
2. **Gateway & Security Tier**: FastAPI control plane, RBAC middleware, secret redaction, rate limiting.
3. **Governance Kernel**: AgentOS 22-state finite state machine, 17 specialist agents, calibrated confidence engine, Maker-Checker dual control gate.
4. **Execution & Verification Tier**: HMAC-SHA256 capability tokens, Ansible Runner isolated sandbox, `ProductionProbeRunner` (live TCP, HTTP, SQL probes), automated rollback engine.
5. **Storage & Audit Tier**: PostgreSQL 16 + pgvector, Redis Redlock, MinIO S3 object store, SHA-256 Merkle hash chain audit ledger.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---|---|---|---|
| 1 | JSON Datetime Serialization | Add `default=str` to `json.dumps` calls serializing `WorkflowContext` fields (started_at, completed_at, probe timestamps) to fix `datetime is not JSON serializable` in PostgreSQL persistence | M1 | Survey (R1) |
| 2 | DEV Resource Seeding Verification | Verify that `_seed_defaults()` in `backend/app/adapters/postgres_external_resource_repository.py` includes DEV resources and avoids `WAITING_FOR_RESOURCE` halts | M1 | Survey (R1) |
| 3 | 50-Scenario Eval Gate | Verify that all 50 scenarios in `backend/tests/agentos/test_50_eval_scenarios.py` pass (100% completion, 0 false-success, 0 unauthorized) | M1 | Survey (R1) |
| 4 | Pytest Suite 100% Green | Ensure `backend/.venv/bin/pytest backend/tests/ -q` reports 0 failures across all 620+ tests | M1 | Survey (R1) |
| 5 | Frontend Build & Typecheck | Ensure `npm run build` and `npx tsc --noEmit` in `frontend/` exit 0 with 0 errors | M1 | Survey (R1) |
| 6 | Remove Committed Keys | Delete `backend/ansible/keys/id_ed25519` and `deploy/sandbox/keys/id_ed25519*` from git tracking | M2 | Survey (R2) |
| 7 | Harden `.gitignore` | Remove negative ignores `!backend/ansible/keys/*`, add wildcard exclusions `**/keys/*`, `id_*`, `.env*` | M2 | Survey (R2) |
| 8 | Harden Compose & MinIO Secrets | Disable anonymous bucket download (`set none`), add `${MINIO_ROOT_PASSWORD:-}` fallback, scrub `backend/.env.example` | M2 | Survey (R2) |
| 9 | Sanitize Test Mock Keys | Replace literal `BEGIN OPENSSH PRIVATE KEY` headers in test mocks with `BEGIN MOCK OPENSSH PRIVATE KEY` so grep finds 0 hits | M2 | Survey (R2) |
| 10 | Author `SECURITY.md` | Document responsible disclosure policy and explicit revocation/rotation notice for commit `5f3fd77` keys | M2 | Survey (R2) |
| 11 | Flagship 9-Step Demo Script | Implement `scripts/run_flagship_demo.py` exercising the complete 9-step PostgreSQL 16 journey including rollback | M3 | Survey (R3) |
| 12 | Root `Makefile` Automation | Implement `make demo`, `make demo-reset` (<30s), and `make demo-run` with automated credential generation | M3 | Survey (R3) |
| 13 | Sandbox Container Key Mount | Update `deploy/sandbox/Dockerfile` and compose volume mounts to mount ephemeral demo keys at runtime | M3 | Survey (R3) |
| 14 | Rewrite `README.md` | Remove false co-architect and banking claims, update to 620+ tests badge, add 60s demo guide, personas, architecture | M4 | Survey (R4) |
| 15 | Author `HACKATHON.md` | Create comprehensive 11-section report with machine-generated evidence extraction commands | M4 | Survey (R4) |
| 16 | Repo Professionalism Files | Add `LICENSE` (Apache-2.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md` | M5 | Survey (R5) |
| 17 | Pin GitHub Actions & Dependabot | Add `.github/dependabot.yml` and pin actions in `deploy.yml` and `vulcan-ci.yml` to immutable commit SHAs | M5 | Survey (R5) |
| 18 | Tagged Release `v0.1.0-hackathon` | Create annotated git tag `v0.1.0-hackathon` with release notes and verify both CI workflows pass on GitHub | M5 | Survey (R5) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1 | CI Fixes & Datetime Serialization | Features 1-5: Add `default=str` to JSON dumps, verify DEV resource seeding, verify 50-scenario eval gate, ensure 100% pytest pass (0 failures) and clean frontend build | none | PLANNED |
| M2 | Security Hardening & Key Removal | Features 6-10: Remove tracked private keys, harden .gitignore, set MinIO anonymous downloads to none, scrub example secrets, sanitize test mocks, author SECURITY.md | none | PLANNED |
| M3 | Flagship Demo & Makefile | Features 11-13: Implement `scripts/run_flagship_demo.py`, root `Makefile` (`make demo`, `make demo-reset`, `make demo-run`), ephemeral key runtime generation | M1, M2 | PLANNED |
| M4 | Honest Documentation & Hackathon Report | Features 14-15: Rewrite `README.md` with honest claims and test badges, author `HACKATHON.md` with live vs simulated matrix and machine-generated proof | M1, M2, M3 | PLANNED |
| M5 | Repo Professionalism, Action Pinning & Release | Features 16-18: Add LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, templates, dependabot, pin workflow action SHAs, commit, push, tag `v0.1.0-hackathon`, verify green CI | M1, M2, M3, M4 | PLANNED |

## Interface Contracts
### M1 ↔ M2: Key & Secret Storage
- Code using `id_ed25519` private key must look in gitignored `/app/ansible/keys/id_ed25519` or `deploy/sandbox/keys/id_ed25519` generated ephemerally at runtime.
- No source file or test file shall contain literal `BEGIN OPENSSH PRIVATE KEY`.

### M2 ↔ M3: Demo Automation & Docker Sandbox
- `make demo` will generate `deploy/sandbox/keys/id_ed25519` and `backend/ansible/keys/id_ed25519` with mode 600 before launching containers.
- `deploy/docker-compose.yml` mounts the public key into sandbox authorized keys and private key into backend container.

### M3 ↔ M4/M5: Documentation & Evidence
- `README.md` and `HACKATHON.md` reference verified working commands: `make demo`, `make demo-reset`, `make demo-run`.
- Test count badge must display `620 passed`.
- Evaluation scenario badge must display `50/50 passed`, `0.0% false success`.

## Code Layout
- `backend/app/agentos/repository.py`: Workflow persistence and JSON serialization.
- `backend/app/adapters/postgres_external_resource_repository.py`: Default resource seeding.
- `backend/tests/agentos/test_50_eval_scenarios.py`: 50-scenario regression evaluation gate.
- `backend/ansible/keys/`, `deploy/sandbox/keys/`: Private keys directory (gitignored).
- `deploy/docker-compose.yml`: Container definitions and MinIO configuration.
- `SECURITY.md`: Security disclosure policy and key rotation disclosure.
- `scripts/run_flagship_demo.py`: 9-step demo journey.
- `Makefile`: Project automation entry point.
- `README.md`: Honest public project documentation.
- `HACKATHON.md`: Comprehensive hackathon submission document.
- `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`: Repository professionalism files.
- `.github/workflows/`: CI and deployment workflow definitions.
- `.github/dependabot.yml`: Automated dependency updates.
