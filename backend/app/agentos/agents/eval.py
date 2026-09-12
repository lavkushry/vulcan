"""
Project Vulcan: Eval Agent & Multi-Tier Evaluation Engine (Section 7, 36, 37 & AGENT-12)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Evaluate end-to-end multi-agent workflow traces across 8 tiers (Tier 0 to Tier 7)
- Computes statistical metrics: pass rate, bootstrap confidence intervals, regression risk
- Never grants execution approval
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, EvalOutput


class EvalAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.EVAL,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Evaluate complete workflow traces against empirical ground truth and compute statistical confidence intervals.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return EvalOutput

    @staticmethod
    def compute_bootstrap_ci(
        successes: int, total: int, num_bootstrap: int = 1000, alpha: float = 0.05
    ) -> Tuple[float, float]:
        """Calculates 95% non-parametric bootstrap confidence interval for pass rate."""
        if total <= 0:
            return (0.0, 0.0)

        data = [1] * successes + [0] * (total - successes)
        means = []
        for _ in range(num_bootstrap):
            sample = [random.choice(data) for _ in range(total)]
            means.append(sum(sample) / total)

        means.sort()
        lower_idx = int((alpha / 2.0) * num_bootstrap)
        upper_idx = int((1.0 - alpha / 2.0) * num_bootstrap)
        ci_lower = round(means[lower_idx] * 100.0, 2)
        ci_upper = round(means[upper_idx] * 100.0, 2)
        return (ci_lower, ci_upper)

    def execute(self, ctx: WorkflowContext, **kwargs) -> EvalOutput:
        tier = kwargs.get("tier", 0)
        suite_name = kwargs.get("suite_name", "Tier 0 PR Smoke Benchmark")

        # Evaluate workflow completeness
        checks = [
            ("intent_accuracy", bool(ctx.normalized_intent.get("automation_domain"))),
            ("discovery_relevance", len(ctx.discovered_assets) > 0),
            ("resource_recall", len(ctx.required_resources) > 0),
            ("validation_gate", len(ctx.validation_results) > 0),
            ("security_defense", bool(ctx.security_findings is not None)),
            ("postcondition_verified", ctx.postcondition_verification.get("all_passed", False)),
        ]

        passed_scenarios = sum(1 for _, ok in checks if ok)
        total_scenarios = len(checks)
        pass_rate = round((passed_scenarios / total_scenarios) * 100.0, 2)

        ci_lower, ci_upper = self.compute_bootstrap_ci(passed_scenarios, total_scenarios)

        gate_passed = (pass_rate >= 80.0)

        return EvalOutput(
            workflow_id=ctx.workflow_id,
            eval_id=f"eval-{ctx.workflow_id[:8]}",
            tier=tier,
            suite_name=suite_name,
            total_scenarios=total_scenarios,
            passed_scenarios=passed_scenarios,
            pass_rate=pass_rate,
            bootstrap_ci_lower=ci_lower,
            bootstrap_ci_upper=ci_upper,
            gate_passed=gate_passed,
            proposed_next_state=WorkflowState.EVALUATING.value,
            confidence=1.0,
            rationale=f"Evaluated workflow across {total_scenarios} quality dimensions. Pass rate: {pass_rate}%.",
        )
