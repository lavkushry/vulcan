# Progress — Explorer 2 (Security & Demo Survey)
Last visited: 2026-09-14T16:02:00Z

## Status
- [x] Initialized BRIEFING.md and progress.md
- [x] 1. Key audit & git tracking status (R2) — Completed
  - Found committed OpenSSH Ed25519 private keys:
    * `backend/ansible/keys/id_ed25519` (blob a6d8fe75ba3539762cf6bafbad7825d52b655c83)
    * `deploy/sandbox/keys/id_ed25519` (blob a6d8fe75ba3539762cf6bafbad7825d52b655c83)
    * `deploy/sandbox/keys/id_ed25519.pub` (blob ce77465ed66dd0e5c32a1d89a6711c0193fd33d1)
  - Committed in commit 5f3fd772d1710088983c57af0a6c21ad6475b442
  - Also identified mock key strings in test_cyberark_pam.py, scenarios.v2.jsonl, build_golden_scenarios.py
- [x] 2. .gitignore audit (R2) — Completed
  - Discovered explicit whitelist bypass in .gitignore lines 94-95 (!deploy/sandbox/keys/* and !backend/ansible/keys/*)
  - Identified missing wildcard key patterns (**/keys/id_*, **/keys/*.pem)
  - Identified .env.* rule preventing .env.example tracking unless negated
- [x] 3. Secrets audit (compose, env, MinIO anonymous download) (R2) — Completed
  - deploy/docker-compose.yml line 61 explicitly enables anonymous downloads: `mc anonymous set download local/...`
  - backend/.env.example line 19 contains plaintext secret `S3_SECRET_KEY=vulcan_minio_secret_2026`
  - deploy/docker-compose.yml uses `${MINIO_ROOT_PASSWORD}` and `${POSTGRES_PASSWORD}` without `:-` fallback
- [x] 4. SECURITY.md review (R2) — Completed
  - Confirmed SECURITY.md does NOT exist at repository root
  - Detailed required sections: responsible disclosure, key revocation & rotation, zero-leak startup generation
- [x] 5. Makefile, compose, seed scripts, migrations, health checks review (R3) — Completed
  - Confirmed Makefile does NOT exist in the repository
  - Audited deploy/docker-compose.yml (7 services: postgres, redis, minio, minio-init, sandbox, backend, frontend)
  - Audited scripts/run_migrations.py & backend/migrations/ (10 migrations: 003-012)
  - Audited scripts/seed_candidates.py & PostgresExternalResourceRepository._seed_defaults
  - Audited health checks: /healthz (liveness), /ready (readiness), frontend :3000
- [x] 6. Flagship demo flow design (R3) — Completed
  - Complete 9-step architecture designed (Inception -> Catalog Selection -> Policy Evaluation -> Maker-Checker -> Sandbox Execution -> Live Terminal Logs -> Independent Probes -> Merkle Audit Chain -> Controlled Failure & Rollback)
- [x] 7. make demo & make demo-reset implementation specifications (R3) — Completed
  - Complete specifications with prerequisite checks, credential generation, container orchestration, migration/seeding, health wait loops, and <30s teardown
- [x] 8. Comprehensive handoff.md report generation — Completed
- [x] 9. Completion message to parent agent — Ready to send
