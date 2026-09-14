# Project Plan: Vulcan Infrastructure Automation Upgrade

## Objective
Upgrade Vulcan's infrastructure automation agent system to produce trustworthy, verifiable outcomes covering requirements R1-R5:
- R1: Runtime Honesty (FoundryAgentRuntime fake-provider fallback, fabricated confidence removal, execution_mode)
- R2: Verifier Completion (Real HTTP telemetry and S3/boto3 backup probes, unsupported probe rejection)
- R3: Planner Selection Logic (Rank all candidates, rejected_candidates reasons, evidence-based confidence)
- R4: Confidence Calibration (None defaults, unknown signals tracking, auth failure override, CalibrationRecord)
- R5: Evaluation Infrastructure (50-scenario full-pipeline regression suite across 5 scenario groups, runner script, metrics report)

## Execution Phases

### Phase 0: Survey & Technical Mapping
- Spawn 3 parallel `teamwork_preview_explorer` agents:
  - Explorer 1: R1 focus — `backend/app/agentos/adapters/foundry_adapter.py`, `schemas.py`, runtime resolution & execution modes.
  - Explorer 2: R2, R3, R4 focus — `backend/app/agentos/agents/verifier.py`, `planner.py`, `confidence.py`, and probe implementations.
  - Explorer 3: R5 & Test Infra focus — existing test harness in `backend/tests/`, simulation engines, runner scripts, dependencies.
- Synthesize reports into unified Feature Inventory and Architecture specification.

### Phase 1: PROJECT.md & Decomposition
- Formulate `PROJECT.md` with Feature Inventory, Milestones, Interface Contracts, and Code Layout.
- Assign all requirements to distinct, module-bounded milestones.

### Phase 2: Dual-Track Execution
- **Implementation Track**:
  - Milestone 1 (R1 & Schemas): Runtime Honesty & Execution Modes
  - Milestone 2 (R2): Verifier Completion (Real telemetry & backup probes)
  - Milestone 3 (R3 & R4): Planner Selection & Confidence Calibration
- **E2E Testing Track**:
  - Milestone E2E (R5): Evaluation Infrastructure & 50-Scenario Suite (`scripts/run_eval.py`, scenarios dataset, reporting)

### Phase 3: Final Verification & Audit
- Execute all unit tests and full test suite (`backend/tests/`).
- Execute full 50-scenario regression evaluation suite via `scripts/run_eval.py`.
- Run Reviewers, Challengers, and Forensic Auditor for integrity gating.

### Phase 4: Project Wrap-Up & Parent Handoff
- Synthesize outcomes, verification results, and metrics.
- Report completion to parent agent via `send_message`.
