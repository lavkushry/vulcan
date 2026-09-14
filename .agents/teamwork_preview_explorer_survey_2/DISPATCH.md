## Task Assignment: Survey Phase - Verifier, Planner & Confidence Calibration (R2, R3, R4)
**Assigned Agent**: teamwork_preview_explorer_survey_2
**Working Directory**: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_explorer_survey_2
**Project Root**: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane
**Authoritative Request**: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/ORIGINAL_REQUEST.md

### Objective
You are an Explorer surveying the Vulcan codebase specifically for Requirements R2 (Verifier Completion), R3 (Planner Selection Logic), and R4 (Confidence Calibration).
Read `ORIGINAL_REQUEST.md` first.

### Investigation Focus
1. Inspect `backend/app/agentos/agents/verifier.py`:
   - Inspect `ProductionProbeRunner` and `SimulationProbeRunner`.
   - Lines 186-206: `telemetry_active`, `backup_accessible`, and the catch-all `else` clause.
   - What configuration (`probe_config`), environment variables, or dependencies (e.g. `boto3`, HTTP client) are available/used.
2. Inspect `backend/app/agentos/agents/planner.py`:
   - Inspect `PlannerAgent.execute()`, candidate discovery, candidate scoring/ranking, `curated_candidates[0]`.
   - How `PlannerOutput` in `schemas.py` is defined and how `rejected_candidates: List[RejectedCandidate]` should be structured.
   - How confidence is currently produced (fixed 0.97) and how to link to `ConfidenceEngine`.
3. Inspect `backend/app/agentos/confidence.py`:
   - Inspect `ConfidenceEngine.calculate_confidence()`, current parameter defaults (0.95, 0.85, 0.80, etc.).
   - How unknown signals should be handled (`None` defaults, proportional penalty/exclusion, `unknown_signals` list in `ConfidenceAssessment`).
   - Authorization check & deterministic validation failure rules (forcing `ConfidenceTier.LOW`).
   - Design for `CalibrationRecord` Pydantic model.
4. Inspect existing tests in `backend/tests/`:
   - Tests for verifier, planner, confidence engine, and probe runners.

### Deliverable
Write your detailed report to `/Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_explorer_survey_2/handoff.md` and update `progress.md`.
Send a message when complete.
