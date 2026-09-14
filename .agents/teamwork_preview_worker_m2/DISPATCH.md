# DISPATCH: Worker M2 (Security Hardening & Secret Removal)
Original Request: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/ORIGINAL_REQUEST.md
Scope Document: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_orchestrator_2/PROJECT.md
Working Directory: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_worker_m2
Explorer Report: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_explorer_hackathon_2/handoff.md

## Exclusive File Ownership
- backend/ansible/keys/*
- deploy/sandbox/keys/*
- .gitignore
- deploy/docker-compose.yml
- backend/.env.example
- SECURITY.md
- backend/tests/test_cyberark_pam.py
- evals/golden/scenarios.v2.jsonl
- scripts/build_golden_scenarios.py

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Tasks
1. Remove committed keys from git tracking:
   `git rm backend/ansible/keys/id_ed25519 deploy/sandbox/keys/id_ed25519 deploy/sandbox/keys/id_ed25519.pub`
   (Do NOT rewrite git history).
2. Update `.gitignore`:
   Remove negative rules `!deploy/sandbox/keys/*` and `!backend/ansible/keys/*`.
   Add rules:
   ```gitignore
   **/keys/
   **/keys/*
   **/keys/id_*
   **/keys/*.pem
   **/keys/*.pub
   **/keys/*.key
   deploy/sandbox/keys/
   backend/ansible/keys/
   id_*
   *.pem
   *.key
   *.cert
   *.crt
   .env
   .env.*
   !.env.example
   !*.env.example
   !**/.env.example
   .secrets*
   *.secrets.env
   ```
3. In `deploy/docker-compose.yml`:
   - Change line 61: `/usr/bin/mc anonymous set download ...` to `/usr/bin/mc anonymous set none local/$${S3_BUCKET_NAME:-vulcan-artifacts} || true;`
   - Use `${MINIO_ROOT_PASSWORD:-}` fallback on lines 43 and 92.
   - Use `${POSTGRES_PASSWORD:-}` fallback on line 10.
4. In `backend/.env.example`:
   - Replace line 19 `vulcan_minio_secret_2026` with `replace_with_secure_minio_password_32_chars`.
5. Sanitize test mocks containing private key headers:
   - In `backend/tests/test_cyberark_pam.py` line 105: replace `-----BEGIN OPENSSH PRIVATE KEY-----` with `-----BEGIN MOCK OPENSSH PRIVATE KEY-----`.
   - In `evals/golden/scenarios.v2.jsonl` line 375 and `scripts/build_golden_scenarios.py` line 667: replace with `BEGIN MOCK OPENSSH PRIVATE KEY`.
   - Verify `git grep "BEGIN OPENSSH PRIVATE KEY"` finds 0 matches in tracked files.
6. Create `SECURITY.md`:
   - Follow the complete specification from Explorer 2's handoff (responsible disclosure, key rotation disclosure for commit `5f3fd77`, ephemeral keys).
7. Verify all changes:
   - `git ls-files backend/ansible/keys/ deploy/sandbox/keys/` returns empty.
   - `git grep "BEGIN OPENSSH PRIVATE KEY"` returns 0 results.
   - `backend/.venv/bin/pytest backend/tests/ -q` passes without regressions.


## 2026-09-14T16:24:38Z
Dispatched as Worker M2 (Replacement) on Project Vulcan.
Tasks:
1. Remove tracked keys from git index (`git rm backend/ansible/keys/id_ed25519 deploy/sandbox/keys/id_ed25519 deploy/sandbox/keys/id_ed25519.pub`).
2. Update `.gitignore` with wildcard patterns for keys, credentials, and env files as specified in DISPATCH.md.
3. Harden `deploy/docker-compose.yml` (set MinIO anonymous download to none, add `${MINIO_ROOT_PASSWORD:-}` fallback).
4. Scrub plaintext example secrets in `backend/.env.example`.
5. Sanitize test mocks in `test_cyberark_pam.py`, `scenarios.v2.jsonl`, `build_golden_scenarios.py` so `git grep "BEGIN OPENSSH PRIVATE KEY"` finds 0 matches in tracked files.
6. Create `SECURITY.md` documenting responsible disclosure and key revocation for commit 5f3fd77.
7. Verify all changes and run tests.
8. Write complete handoff report to `/Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_worker_m2/handoff.md` and send a completion message.
