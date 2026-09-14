## 2026-09-14T15:43:53Z
You are the Project Orchestrator for Project Vulcan.

Your mission is to make the Vulcan AI control plane hackathon-submission-ready according to all requirements in ORIGINAL_REQUEST.md.

Working directory for repository: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane
Your agent working directory: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_orchestrator_2
Original Request file: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/ORIGINAL_REQUEST.md

Key Requirements:
1. R1: Fix all CI failures and make both GitHub Actions workflows green.
   - The latest CI run has 5 failed tests out of 620. 3 workflow tests stop at WAITING_FOR_RESOURCE because only PROD resources were seeded; 2 acceptance tests assumed workflows reach EXECUTION_READY or SUCCESS in DEV mode. Verify DEV resources in _seed_defaults in backend/app/adapters/postgres_external_resource_repository.py is committed, pushed, and resolves CI.
   - Fix PostgreSQL datetime serialization (json.dumps calls touching WorkflowContext fields need default=str).
   - Restore 50-scenario evaluation gate (fix the 2 failing scenarios in backend/tests/agentos/test_50_eval_scenarios.py).
   - Ensure backend/.venv/bin/pytest backend/tests/ -q passes 100% (all 620+ tests pass).
   - Both Enterprise CI and Deployment workflows must pass on GitHub.
2. R2: Remove committed secrets and harden security defaults.
   - Remove backend/ansible/keys/id_ed25519 and any keys under deploy/sandbox/keys/.
   - Add key directories to .gitignore.
   - Remove MINIO_ROOT_PASSWORD plaintext secrets; use ${MINIO_ROOT_PASSWORD:-} generated at startup.
   - Create SECURITY.md documenting key rotation and responsible disclosure.
3. R3: Build one reliable end-to-end demo with `make demo` and `make demo-reset`.
   - Single flagship demo journey (PostgreSQL 16 deploy → approve → execute → live logs → probe verification → audit chain → controlled failure rollback).
   - Implement `make demo` and `make demo-reset`.
4. R4: Rewrite README and create HACKATHON.md with honest verifiable claims.
   - Remove fake co-architect claims (Martin, Xu, Karpathy, Walke).
   - Remove "PNC Bank Engineering Standard".
   - Current test badge, honest limitations, category alignment.
   - Create comprehensive HACKATHON.md with machine-generated evidence.
5. R5: Add repository professionalism files and create a tagged release.
   - LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, issue templates, PR template.
   - Pin GitHub Actions to commit SHAs, add .github/dependabot.yml.
   - Git tag `v0.1.0-hackathon` with release notes.

Maintain progress.md and BRIEFING.md in your directory. Decompose, dispatch specialists, verify each acceptance criterion thoroughly, and report back when complete.
