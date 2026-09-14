## Task Assignment: Survey Phase - Test Infrastructure & Evaluation (R5)
**Assigned Agent**: teamwork_preview_explorer_survey_3
**Working Directory**: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_explorer_survey_3
**Project Root**: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane
**Authoritative Request**: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/ORIGINAL_REQUEST.md

### Objective
You are an Explorer surveying the Vulcan codebase specifically for Requirement R5 (Evaluation Infrastructure with 50-scenario regression suite) and the existing test framework.
Read `ORIGINAL_REQUEST.md` first.

### Investigation Focus
1. Inspect the existing test suite:
   - What test framework is used (pytest, etc.)? Where are tests located (`backend/tests/`)?
   - How to run tests (e.g. `pytest`, virtualenv/poetry/uv, python path)?
   - Current test status: how do existing tests run?
2. Inspect `AgentOSKernel` in `backend/app/agentos/kernel.py`:
   - State machine, execution flow, inputs/outputs, states (e.g., WAITING_FOR_INPUT, SECURITY_REJECTED, POLICY_DENIED, EXECUTION_FAILED, SUCCESS).
   - How `SimulationProbeRunner` and `SimulationPolicyEngine` work with `AgentOSKernel`.
3. Survey R5 requirements:
   - 50 scenarios across 5 groups (15 supported tasks/paraphrases, 10 missing info/ambiguity, 10 permission violations/malicious instructions, 10 tool failures/timeouts/partial execution, 5 rollback/restart recovery).
   - Runner script requirements (`scripts/run_eval.py`), JSON report schema (completion rate, false-success rate, unauthorized actions, p95 time, cost metrics).
   - Location for evaluation scenarios (`backend/tests/eval/` or `scripts/`).

### Deliverable
Write your detailed report to `/Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_explorer_survey_3/handoff.md` and update `progress.md`.
Send a message when complete.
