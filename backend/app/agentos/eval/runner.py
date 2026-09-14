"""
Project Vulcan: Full-Pipeline Evaluation Runner Engine
"""
import os
import time
from typing import Any, Dict, List, Optional
from app.agentos.kernel import AgentOSKernel
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, ExecutionMode, ValidationCheck, ValidationCheckStatus, ValidatorOutput
from app.agentos.policy_engine import SimulationPolicyEngine, PolicyDecision
from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository
from app.agentos.adapters.execution_adapter import SimulationExecutionAdapter, ExecutionResult
from app.agentos.agents.verifier import SimulationProbeRunner, VerificationProbe
from app.agentos.eval.schemas import EvalReport, EvalScenario, ScenarioExecutionResult, ScenarioGroup
from app.agentos.eval.scenarios import build_50_eval_scenarios


class ConfigurableSimulationExecutionAdapter(SimulationExecutionAdapter):
    """Simulation adapter with configurable failure injection."""
    def __init__(self, exit_code: int = 0, stderr: str = ""):
        super().__init__()
        self._exit_code = exit_code
        self._stderr = stderr

    def execute(self, **kwargs) -> ExecutionResult:
        if self._exit_code != 0:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            return ExecutionResult(
                runner="simulation_adapter",
                workflow_id=kwargs.get("workflow_id", ""),
                token_id=kwargs.get("token_id", ""),
                artifact_sha256=kwargs.get("artifact_sha256", "sha256-default"),
                target_id=kwargs.get("target_resource_id", "localhost"),
                environment=kwargs.get("environment", "PROD"),
                exit_code=self._exit_code,
                stdout="Task started...\nFATAL ERROR encountered.",
                stderr=self._stderr or f"Execution failed with code {self._exit_code}",
                started_at=now,
                completed_at=now,
                duration_ms=10.0,
            )
        return super().execute(**kwargs)


class ConfigurableSimulationProbeRunner(SimulationProbeRunner):
    """Simulation probe runner with configurable probe failure injection."""
    def __init__(self, fail_probe_type: Optional[str] = None):
        super().__init__()
        self._fail_probe_type = fail_probe_type

    def run_probe(self, probe_type: str, target: str, probe_config: Dict[str, Any]) -> VerificationProbe:
        if self._fail_probe_type and probe_type == self._fail_probe_type:
            return VerificationProbe(
                probe_id=f"sim-fail-{probe_type}",
                target=target,
                probe_type=probe_type,
                passed=False,
                latency_ms=1.0,
                details={**probe_config, "simulation": True, "status": "failed", "error": f"Injected failure for {probe_type}"},
            )
        return super().run_probe(probe_type, target, probe_config)


class ConfigurableSimulationPolicyEngine(SimulationPolicyEngine):
    """Simulation policy engine with freeze window injection."""
    def __init__(self, simulate_freeze: bool = False):
        super().__init__()
        self._simulate_freeze = simulate_freeze

    def evaluate(self, ctx: WorkflowContext) -> PolicyDecision:
        import uuid
        if self._simulate_freeze:
            return PolicyDecision(
                decision="DENIED",
                decision_id=f"pol-freeze-{uuid.uuid4().hex[:8]}",
                reason="Changes blocked: Active change freeze window enforced.",
                in_maintenance_window=False,
            )
        return super().evaluate(ctx)


class AgentOSEvalRunner:
    """Executes the 50-scenario regression evaluation suite against AgentOSKernel."""

    @classmethod
    def execute_scenario(cls, scenario: EvalScenario) -> ScenarioExecutionResult:
        t0 = time.perf_counter()
        assertions_passed: List[str] = []
        assertions_failed: List[str] = []
        is_false_success = False
        unauth_action = False
        error_msg = None

        # Setup adapters and policy engine per scenario setup_kwargs
        exit_code = scenario.setup_kwargs.get("execution_exit_code", 0)
        stderr = scenario.setup_kwargs.get("execution_stderr", "")
        fail_probe = scenario.setup_kwargs.get("fail_probe_type")
        freeze = scenario.setup_kwargs.get("simulate_freeze_window", False)

        exec_adapter = ConfigurableSimulationExecutionAdapter(exit_code=exit_code, stderr=stderr)
        probe_runner = ConfigurableSimulationProbeRunner(fail_probe_type=fail_probe)
        policy_engine = ConfigurableSimulationPolicyEngine(simulate_freeze=freeze)

        if scenario.setup_kwargs.get("missing_resource"):
            ext_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=False)
        else:
            ext_repo = PostgresExternalResourceRepository(db_url=None, seed_defaults=True)

        kernel = AgentOSKernel(
            execution_adapter=exec_adapter,
            probe_runner=probe_runner,
            policy_engine=policy_engine,
            external_resource_repo=ext_repo,
        )

        try:
            # 1. Create Workflow
            ctx = kernel.create_workflow(
                original_request=scenario.request,
                requester_id=scenario.requester_id,
                environment=scenario.environment,
            )

            # 2. Step through state machine
            max_steps = 30
            step_count = 0

            while step_count < max_steps:
                step_count += 1
                curr = ctx.current_state

                # Check if in a terminal state
                if curr in (
                    WorkflowState.SUCCESS,
                    WorkflowState.POLICY_DENIED,
                    WorkflowState.SECURITY_REJECTED,
                    WorkflowState.VALIDATION_FAILED,
                    WorkflowState.EXECUTION_FAILED,
                    WorkflowState.VERIFY_FAILED,
                    WorkflowState.ROLLED_BACK,
                ):
                    # For rollback recovery tests, trigger rollback if we reached failure state
                    if scenario.group == ScenarioGroup.ROLLBACK_RECOVERY and scenario.setup_kwargs.get("trigger_rollback"):
                        if curr in (WorkflowState.EXECUTION_FAILED, WorkflowState.VERIFY_FAILED):
                            ctx = kernel.trigger_rollback(ctx.workflow_id)
                    break

                # Handle WAITING_FOR_INPUT (clarification gate)
                if curr == WorkflowState.WAITING_FOR_INPUT:
                    if scenario.group == ScenarioGroup.AMBIGUITY:
                        # Ambiguity test correctly stopped for input!
                        break
                    else:
                        # Supply missing parameters and continue
                        ctx = kernel.supply_input(ctx.workflow_id, {
                            "target_host": "db-cluster.internal",
                            "environment": "PROD",
                            "target_inventory": "db-cluster.internal",
                        })
                        ctx = kernel.step(ctx.workflow_id)
                        continue

                # Handle WAITING_FOR_APPROVAL (governance gate)
                if curr == WorkflowState.WAITING_FOR_APPROVAL:
                    if scenario.setup_kwargs.get("test_self_approval"):
                        # Requester attempts self-approval
                        try:
                            kernel.approve_workflow(
                                ctx.workflow_id,
                                approver_id=scenario.requester_id,
                                reason="Self-approval attempt",
                            )
                            # If it succeeded, that's an unauthorized action!
                            unauth_action = True
                        except PermissionError:
                            # Correctly blocked by Maker-Checker invariant
                            assertions_passed.append("maker_checker_blocked_self_approval")
                        break
                    else:
                        ctx = kernel.approve_workflow(
                            ctx.workflow_id,
                            approver_id=scenario.approver_id or "secops-bob@corp.internal",
                            reason="Evaluation automated sign-off",
                        )
                        continue

                # Handle WAITING_FOR_RESOURCE
                if curr == WorkflowState.WAITING_FOR_RESOURCE:
                    break

                # Injected invalid YAML for validation failure test
                if curr == WorkflowState.RESOLVING_RESOURCES and scenario.setup_kwargs.get("inject_invalid_yaml"):
                    ctx = kernel.repository.get_workflow(ctx.workflow_id)
                    ctx.generated_artifacts = [{
                        "files": [{"path": "playbook.yml", "content": "{invalid yaml: [unterminated"}],
                        "test_files": [],
                        "rollback_files": [],
                    }]
                    ctx.version += 1
                    kernel.repository.save_workflow(ctx)

                # Forged HMAC / tampered token test
                if curr == WorkflowState.EXECUTION_READY and scenario.setup_kwargs.get("tamper_token"):
                    ctx = kernel.repository.get_workflow(ctx.workflow_id)
                    if ctx.generated_artifacts:
                        ctx.generated_artifacts[0]["artifact_sha256"] = "forged_sha256_hash_tampered"
                        ctx.version += 1
                        kernel.repository.save_workflow(ctx)

                prev_state = ctx.current_state
                ctx = kernel.step(ctx.workflow_id)
                if ctx.current_state == prev_state:
                    break

            actual_terminal_state = ctx.current_state.value

            # Verify postconditions if reached SUCCESS
            probes = ctx.postcondition_verification.get("probes", [])
            postconditions_verified = bool(probes) and all(p.get("passed", False) for p in probes)

            if actual_terminal_state == "SUCCESS" and not postconditions_verified:
                is_false_success = True

            # Match terminal state expectation
            passed = (actual_terminal_state == scenario.expected_terminal_state) and not is_false_success and not unauth_action
            if passed:
                assertions_passed.append(f"terminal_state_matches_{scenario.expected_terminal_state}")
                if scenario.setup_kwargs.get("tamper_token"):
                    assertions_passed.append("tamper_detected")
            else:
                assertions_failed.append(f"terminal_state_mismatch: expected {scenario.expected_terminal_state}, got {actual_terminal_state}")

            event_history = kernel.repository.get_events(ctx.workflow_id)
            events_count = len(event_history)

        except Exception as exc:
            actual_terminal_state = "EXCEPTION"
            passed = False
            error_msg = str(exc)
            assertions_failed.append(f"unexpected_exception: {exc}")
            postconditions_verified = False
            events_count = 0

        duration_ms = (time.perf_counter() - t0) * 1000.0

        return ScenarioExecutionResult(
            scenario_id=scenario.id,
            group=scenario.group.value,
            name=scenario.name,
            passed=passed,
            expected_terminal_state=scenario.expected_terminal_state,
            actual_terminal_state=actual_terminal_state,
            postconditions_verified=postconditions_verified,
            is_false_success=is_false_success,
            unauthorized_action_detected=unauth_action,
            latency_ms=round(duration_ms, 2),
            events_count=events_count,
            error=error_msg,
            assertions_passed=assertions_passed,
            assertions_failed=assertions_failed,
        )

    @classmethod
    def run_all_50_scenarios(cls) -> EvalReport:
        scenarios = build_50_eval_scenarios()
        results: List[ScenarioExecutionResult] = []

        for scn in scenarios:
            res = cls.execute_scenario(scn)
            results.append(res)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        false_successes = sum(1 for r in results if r.is_false_success)
        unauth_actions = sum(1 for r in results if r.unauthorized_action_detected)

        latencies = sorted(r.latency_ms for r in results)
        p95_idx = int(0.95 * total) - 1
        p95_latency = latencies[max(0, p95_idx)]
        avg_latency = sum(latencies) / total if total > 0 else 0.0

        group_breakdown: Dict[str, Dict[str, Any]] = {}
        for r in results:
            if r.group not in group_breakdown:
                group_breakdown[r.group] = {"total": 0, "passed": 0, "failed": 0}
            group_breakdown[r.group]["total"] += 1
            if r.passed:
                group_breakdown[r.group]["passed"] += 1
            else:
                group_breakdown[r.group]["failed"] += 1

        for g_data in group_breakdown.values():
            g_data["pass_rate"] = round((g_data["passed"] / g_data["total"]) * 100.0, 1)

        verified_rate = round((passed / total) * 100.0, 1)
        false_success_rate = round((false_successes / total) * 100.0, 2)

        return EvalReport(
            total_scenarios=total,
            passed_scenarios=passed,
            failed_scenarios=failed,
            verified_completion_rate=verified_rate,
            false_success_rate=false_success_rate,
            unauthorized_actions_count=unauth_actions,
            p95_latency_ms=round(p95_latency, 2),
            avg_latency_ms=round(avg_latency, 2),
            cost_per_verified_success_usd=0.0,
            group_breakdown=group_breakdown,
            results=results,
        )
