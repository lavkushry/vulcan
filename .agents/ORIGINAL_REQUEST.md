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
