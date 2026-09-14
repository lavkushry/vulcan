# DISPATCH: Worker M1 (CI Fixes & Datetime Serialization)
Original Request: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/ORIGINAL_REQUEST.md
Scope Document: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_orchestrator_2/PROJECT.md
Working Directory: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_worker_m1
Explorer Report: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_explorer_hackathon_1/handoff.md

## Exclusive File Ownership
- backend/app/agentos/repository.py
- backend/app/agentos/kernel.py
- backend/app/agentos/adapters/execution_adapter.py
- backend/app/adapters/postgres_job_repository.py
- backend/app/api/websockets.py

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Tasks
1. In `backend/app/agentos/repository.py`:
   Add `default=str` to all 24 `json.dumps(...)` calls in `_persist_workflow_postgres()` (lines 289-296) serializing `WorkflowContext` fields.
2. In `backend/app/agentos/kernel.py`:
   Add `default=str` to `json.dumps(ctx.desired_state, sort_keys=True)` hashing calls on lines 473, 706, 813.
3. In `backend/app/agentos/adapters/execution_adapter.py`:
   Add `default=str` to `json.dumps(extravars)` on line 341.
4. In `backend/app/adapters/postgres_job_repository.py`:
   Add `default=str` to `json.dumps(job.parameters)` on line 140.
5. In `backend/app/api/websockets.py`:
   Add `default=str` to `json.dumps(entry)` and `json.dumps(message)` on lines 165, 189.
6. Verify:
   - Run `backend/.venv/bin/pytest backend/tests/ -q` and confirm 100% pass (0 failures).
   - Run `PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/agentos/test_50_eval_scenarios.py -v` and confirm 50/50 scenarios pass.
   - Run `npm run build` in `frontend/` and confirm clean build.
   - Run serialization unit verification in Python confirming datetime objects serialize without error.

Document all changes, test commands, and exact outputs in `handoff.md`.

## 2026-09-14T16:04:24Z
You are Worker M1 on Project Vulcan.
Working directory: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_worker_m1
Original Request: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/ORIGINAL_REQUEST.md
Scope Document: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_orchestrator_2/PROJECT.md
Explorer Report: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_explorer_hackathon_1/handoff.md
Dispatch Instructions: /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_worker_m1/DISPATCH.md

Exclusive File Ownership:
- backend/app/agentos/repository.py
- backend/app/agentos/kernel.py
- backend/app/agentos/adapters/execution_adapter.py
- backend/app/adapters/postgres_job_repository.py
- backend/app/api/websockets.py

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task:
1. Implement default=str across all json.dumps serialization calls touching WorkflowContext fields and job parameters in your owned files.
2. Run backend/.venv/bin/pytest backend/tests/ -q to verify 100% test pass (all 620+ tests pass with 0 failures).
3. Run PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/agentos/test_50_eval_scenarios.py -v to verify 50/50 scenarios pass.
4. Run npm run build in frontend/ to verify clean build.
5. Write your complete handoff report to /Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/.agents/teamwork_preview_worker_m1/handoff.md and send a completion message.
