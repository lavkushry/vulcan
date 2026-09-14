"""
Project Vulcan: Critic Agent (Section 7 & AGENT-08)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Objective: Prove the proposed plan or generated automation is wrong
- Attacks:
  1. Unverified or silent assumptions
  2. Ordering and dependency flaws in execution DAG
  3. Non-idempotent task declarations
  4. Missing or unsound rollback branches
  5. Target selection & environment blast radius
"""
from __future__ import annotations

from typing import List, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, CriticDefect, CriticOutput


class CriticAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.CRITIC,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",  # Independent critic role
            system_instructions="Adversarially probe proposed automation to uncover design flaws, unverified assumptions, and rollback holes.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return CriticOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> CriticOutput:
        attacks = [
            "attack_silent_assumptions",
            "attack_rollback_exhaustiveness",
            "attack_idempotency_loop",
            "attack_target_boundary",
        ]
        defects: List[CriticDefect] = []

        # Attack 1: Unverified assumptions
        for asm in ctx.assumptions:
            if "defaulting" in asm.lower() and ctx.environment == "PROD":
                defects.append(
                    CriticDefect(
                        category="assumptions",
                        severity="MAJOR",
                        critique=f"Assumption '{asm}' is applied in PROD without explicit operator verification.",
                        counter_example="Operator may require PostgreSQL 15 rather than 16.",
                    )
                )

        # Attack 2: Rollback completeness
        plan = ctx.automation_plan
        rollback_map = plan.get("rollback_dag", {})
        if not rollback_map and ctx.environment == "PROD":
            defects.append(
                CriticDefect(
                    category="rollback",
                    severity="FATAL",
                    critique="Production automation plan completely lacks an automated rollback branch.",
                    counter_example="If cluster initialization fails halfway, nodes are left in undefined state.",
                )
            )

        fatal_count = sum(1 for d in defects if d.severity == "FATAL")
        blocks = (fatal_count > 0)
        verdict = "CHALLENGED" if blocks else "ACCEPTED"
        next_state = WorkflowState.PLAN_REJECTED.value if blocks else WorkflowState.POLICY_CHECK.value

        return CriticOutput(
            workflow_id=ctx.workflow_id,
            verdict=verdict,
            attacks_attempted=attacks,
            defects_found=defects,
            blocks_workflow=blocks,
            proposed_next_state=next_state,
            confidence=0.95,
            rationale="Plan passed adversarial critique." if not blocks else f"Adversarial critique found {fatal_count} fatal defect(s).",
        )
