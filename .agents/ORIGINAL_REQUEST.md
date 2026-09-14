# Original User Request

## Initial Request — 2026-09-14T11:38:18Z

Upgrade Vulcan's infrastructure automation agent system to produce trustworthy, verifiable outcomes. Fix confirmed runtime honesty bugs, strengthen verification, improve planner selection logic, replace fabricated confidence with measured uncertainty, and build regression evaluation infrastructure. The existing codebase is a Python backend with a multi-agent kernel (`AgentOSKernel`) orchestrating ~17 specialist agents through a governed state machine.

Working directory: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane
Integrity mode: development

## Requirements

### R1. Runtime Honesty — Fix FoundryAgentRuntime fake-provider fallback and fabricated confidence

In `backend/app/agentos/adapters/foundry_adapter.py`, `FoundryAgentRuntime._resolve_chat_provider()` silently falls back to `DeterministicFakeChatProvider` while reporting `is_simulation=False`. After invalid LLM output, the `invoke()` method constructs replacement fields with `confidence=0.95`, fabricating successful results.

Fix this:
- Allow a configurable number of retries (default 3) before raising a clear `ProviderUnavailableError` when no real provider is available. Never silently substitute a fake provider.
- After bounded repair attempts on malformed LLM responses, raise a structured `InvalidAgentOutputError` rather than fabricating fields.
- Add an `execution_mode` field to `BaseAgentOutput` in `schemas.py` that distinguishes `live`, `simulated`, `unavailable`, and `failed`. Ensure all agents populate it correctly.
- Update `DeterministicAgentRuntime` to report `is_simulation=True` (already correct) and ensure downstream code respects this distinction.

### R2. Verifier Completion — Implement real telemetry and backup verification probes

In `backend/app/agentos/agents/verifier.py`, the `ProductionProbeRunner` has two unimplemented probe types:
- `telemetry_active` (lines 186-195): Returns unconditional `passed=True` without checking anything.
- `backup_accessible` (lines 186-195): Same problem.

Additionally, the catch-all `else` clause (lines 197-206) returns `passed=True` for unknown probe types.

Fix this:
- `telemetry_active`: Make a real HTTP health check to the monitoring agent's status endpoint (e.g., Datadog agent `/status` endpoint). Use configurable endpoint URL from probe_config or environment variables. Fail clearly if credentials/endpoints are not configured.
- `backup_accessible`: Make a real API call to verify the backup target exists and has a recent snapshot (e.g., S3 HeadBucket + ListObjectsV2 for recent objects). Use boto3 with standard AWS credential chain. Fail clearly if credentials are missing.
- Unknown probe types: Return `passed=False` with details explaining the probe type is unsupported.

### R3. Planner Selection Logic — Rank candidates with evidence

In `backend/app/agentos/agents/planner.py`, `PlannerAgent.execute()` selects `curated_candidates[0]` (first match) and returns hardcoded `confidence=0.97`.

Fix this:
- Score and rank ALL discovered candidates using: required capability match, platform version compatibility, evidence of previous success (from context), rollback support, and trust state.
- Add a `rejected_candidates` field to `PlannerOutput` in `schemas.py` listing each rejected candidate with the specific reason for rejection.
- Compute confidence from actual evidence signals, not a fixed value.
- When no candidates have sufficient evidence, confidence must reflect uncertainty (not 0.97).

### R4. Confidence Calibration — Replace assumed defaults with measured uncertainty

In `backend/app/agentos/confidence.py`, `ConfidenceEngine.calculate_confidence()` uses optimistic defaults (e.g., `historical_accuracy=0.95`, `evidence_coverage=0.85`, `retrieval_score=0.80`).

Fix this:
- Change all parameter defaults to `None`. When a signal is `None` (unknown), exclude it from the weighted calculation and reduce the maximum achievable score proportionally.
- Failed authorization or failed verification must force `ConfidenceTier.LOW` regardless of other signals (already partially done for `deterministic_validation_passed`, extend to authorization).
- Add a `CalibrationRecord` Pydantic model for tracking predicted confidence vs. actual outcome, enabling future threshold calibration against held-out data.
- Add an `unknown_signals` list to `ConfidenceAssessment` documenting which signals were unavailable.

### R5. Evaluation Infrastructure — Build 50-scenario full-pipeline regression test suite

Create a structured evaluation dataset with 50 scenarios that test the complete agent pipeline end-to-end via `AgentOSKernel`:

| Scenario Group | Count | What it tests |
|---|---|---|
| Supported tasks and paraphrases | 15 | Equivalent requests produce equivalent specifications and successful workflows |
| Missing information and ambiguity | 10 | Ambiguous requests trigger useful clarification (WAITING_FOR_INPUT state) |
| Permission violations and malicious instructions | 10 | Unauthorized or injected instructions are rejected (SECURITY_REJECTED or POLICY_DENIED) |
| Tool failures, timeouts, and partial execution | 10 | Runtime/tool failures are handled gracefully (EXECUTION_FAILED, accurate error reporting) |
| Rollback and restart recovery | 5 | Failed executions trigger rollback, rollback outcome is verified |

Requirements:
- Each scenario is a structured data object with: id, group, input request, setup function, expected terminal state, expected behaviors (list of assertions), and acceptance criteria.
- A runner script (`scripts/run_eval.py`) executes all scenarios against the kernel and produces a JSON report.
- Report includes: verified completion rate, false-success rate (reached SUCCESS without meeting postconditions), unauthorized action count, p95 completion time, and cost metrics.
- Deterministic scenarios produce consistent results across repeated runs.
- Scenarios use `SimulationProbeRunner` and `SimulationPolicyEngine` (the existing test infrastructure), not production resources.

## Acceptance Criteria

### Runtime Honesty
- [ ] `FoundryAgentRuntime._resolve_chat_provider()` does NOT fall back to any fake provider — raises `ProviderUnavailableError` after configurable retries
- [ ] `FoundryAgentRuntime.invoke()` does NOT fabricate fields with assumed confidence after parse failures — raises `InvalidAgentOutputError` after bounded repair
- [ ] `BaseAgentOutput` has an `execution_mode` field (enum: `live`, `simulated`, `unavailable`, `failed`) populated by all agents
- [ ] All existing tests in `backend/tests/` pass after these changes (adapt mocks and assertions as needed)

### Verifier Completion  
- [ ] `telemetry_active` probe makes a real HTTP request to a configurable monitoring endpoint and reports actual pass/fail
- [ ] `backup_accessible` probe makes a real API call to verify backup target accessibility and recency
- [ ] Unknown probe types return `passed=False` with `details` explaining the type is unsupported
- [ ] `ProductionProbeRunner` tests verify correct behavior when endpoints are unreachable or credentials missing

### Planner Selection
- [ ] All discovered candidates are scored and ranked, not just the first match
- [ ] `PlannerOutput` includes `rejected_candidates: List[RejectedCandidate]` with rejection reasons
- [ ] Confidence is derived from evidence signals via `ConfidenceEngine`, not hardcoded
- [ ] When zero candidates have strong evidence, confidence is below 0.7

### Confidence Calibration
- [ ] All `calculate_confidence()` signal parameters default to `None`
- [ ] Unknown signals are excluded from the weighted calculation and reduce the maximum achievable score
- [ ] Failed authorization forces `ConfidenceTier.LOW` regardless of other signal values
- [ ] `ConfidenceAssessment` includes `unknown_signals: List[str]` listing unavailable signals
- [ ] `CalibrationRecord` model exists for tracking predictions vs. outcomes

### Evaluation Infrastructure
- [ ] 50 test scenarios exist as structured Python data in `backend/tests/eval/` or `scripts/`
- [ ] `scripts/run_eval.py` executes all scenarios and writes a JSON report to `eval_results/`
- [ ] Report includes verified completion rate, false-success rate, unauthorized action count, p95 time
- [ ] Scenario IDs are stable across runs for regression tracking
- [ ] Deterministic scenarios produce identical results when run twice consecutively

## 2026-09-14T15:41:04Z

Make the Vulcan AI control plane hackathon-submission-ready. The implementation is broad and technically impressive, but the latest CI is red (5 failures out of 620 tests), a private SSH key is committed publicly, deployment is blocked, and the README contains outdated claims. Fix all blockers, build one reliable demo, and prepare honest submission materials.

Working directory: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane
Integrity mode: development

GitHub repository: https://github.com/lavkushry/vulcan
Failing CI run: https://github.com/lavkushry/vulcan/actions/runs/34862879174
Blocked deployment run: https://github.com/lavkushry/vulcan/actions/runs/34862881168

## Requirements

### R1. Fix all CI failures and make both GitHub Actions workflows green

The latest CI run has 5 failed tests out of 620. Three are workflow tests that stop at `WAITING_FOR_RESOURCE` because only PROD resources are seeded by default. Two are acceptance tests that assumed workflows reach `EXECUTION_READY` or `SUCCESS` in DEV mode. The `_seed_defaults` method in `backend/app/adapters/postgres_external_resource_repository.py` was recently updated to include DEV resources — verify that this fix is committed, pushed, and resolves CI.

Additionally, fix the PostgreSQL datetime serialization issue: logs show `datetime is not JSON serializable` during workflow persistence. Audit every `json.dumps` call touching `WorkflowContext` fields and add `default=str` where missing.

Restore the 50-scenario evaluation gate: only 48/50 scenarios currently pass. Identify and fix the 2 failing scenarios in `backend/tests/agentos/test_50_eval_scenarios.py`.

Both CI workflows (Enterprise CI and Deployment) must pass end-to-end after pushing fixes.

### R2. Remove committed secrets and harden security defaults

Remove `backend/ansible/keys/id_ed25519` (a complete OpenSSH private key tracked publicly) and any similar keys under `deploy/sandbox/keys/`. Add key directories to `.gitignore`. Remove `MINIO_ROOT_PASSWORD`-style example secrets from tracked files and disable anonymous bucket downloads in Docker Compose defaults.

Do NOT attempt to rewrite git history — just remove the files, add `.gitignore` entries, and document in `SECURITY.md` that the key has been rotated. Create `SECURITY.md` with responsible disclosure instructions and note that all demo keys must be generated at container startup, never committed.

### R3. Build one reliable end-to-end demo with `make demo`

Create a single flagship demo journey (not all 11 screens):

1. User asks: "Deploy PostgreSQL 16 on the approved target."
2. Vulcan resolves intent and selects an immutable catalog artifact.
3. Policy engine displays risk and approval requirements.
4. A different user approves it.
5. Vulcan executes against the sandbox.
6. Live logs appear in the terminal.
7. Real verification probes confirm the result.
8. The audit page proves the event chain.
9. A controlled failure demonstrates rollback.

Implement `make demo` that: validates prerequisites, generates demo-only credentials, starts Docker Compose, applies migrations, seeds users/targets/catalog, waits for health checks, and prints the URL and demo accounts. Also implement `make demo-reset` for quick recovery during judging.

### R4. Rewrite README and create HACKATHON.md with honest, verifiable claims

Replace the current README opening with: one-sentence problem statement, what Vulcan does differently, 60-second quick start, demo credentials, architecture diagram (can reference an existing one or create a simple mermaid diagram), flagship demo flow, current auto-generated test badge, honest limitations, and hackathon category alignment.

Remove claims of co-architecture by Robert C. Martin, Alex Xu, Andrej Karpathy, and Jordan Walke (present as design inspirations only). Remove "PNC Bank Engineering Standard" phrasing (replace with "designed for regulated enterprise infrastructure"). Remove outdated "287 tests passed" count.

Create `HACKATHON.md` containing: Problem, Target users, Solution, Architecture, Responsible AI and safety controls, What is genuinely live, What is simulated, Reproduction steps, Evaluation methodology, Known limitations, and Demo script. Include machine-generated evidence: commit SHA, CI run URL, test counts, evaluation results, false-success rate, unauthorized-action count, P95 latency, deployment health.

### R5. Add repository professionalism files and create a tagged release

Add: `LICENSE` (MIT or Apache-2.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue and PR templates (`.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`). Update repository description and topics.

Pin GitHub Actions to specific commit SHAs. Add Dependabot configuration (`.github/dependabot.yml`).

Create a tagged release `v0.1.0-hackathon` with release notes summarizing the demo, test results, and known limitations.

## Acceptance Criteria

### CI and Tests
- [ ] `backend/.venv/bin/pytest backend/tests/ -q` reports 0 failures (all 620+ tests pass)
- [ ] All 50 evaluation scenarios in `test_50_eval_scenarios.py` pass
- [ ] No `datetime is not JSON serializable` errors appear in test logs or application logs
- [ ] `npm run build` in `frontend/` exits with code 0 and no TypeScript errors
- [ ] The GitHub Actions "Enterprise CI" workflow passes on the pushed commit
- [ ] The GitHub Actions "Deployment" workflow passes (not skipped) on the pushed commit

### Security
- [ ] `git log --all --full-history -- backend/ansible/keys/` shows the key file is deleted in the latest commit
- [ ] `grep -r "BEGIN OPENSSH PRIVATE KEY" .` finds zero results in tracked files
- [ ] `.gitignore` contains entries for `**/keys/id_*`, `**/keys/*.pem`, and similar patterns
- [ ] `MINIO_ROOT_PASSWORD` does not appear as a plaintext value in any tracked Docker Compose or env file (use `${MINIO_ROOT_PASSWORD:-}` with generation at startup)
- [ ] `SECURITY.md` exists with responsible disclosure instructions

### Demo
- [ ] `make demo` completes without errors on a machine with Docker and Docker Compose installed
- [ ] After `make demo`, the application URL is accessible and the demo user can log in
- [ ] The flagship demo flow (PostgreSQL deploy → approve → execute → verify → controlled failure → rollback) completes end-to-end
- [ ] `make demo-reset` returns the environment to a clean state within 30 seconds

### Documentation
- [ ] `README.md` does not contain "287 tests" or "co-architected by" or "PNC Bank Engineering Standard"
- [ ] `README.md` contains a working quick-start section, architecture overview, and current test badge
- [ ] `HACKATHON.md` exists with all required sections and machine-generated evidence
- [ ] `LICENSE` file exists at the repository root

### Repository
- [ ] `.github/ISSUE_TEMPLATE/` directory exists with at least one template
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` exists
- [ ] `.github/dependabot.yml` exists
- [ ] `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` exist
- [ ] A git tag `v0.1.0-hackathon` exists

