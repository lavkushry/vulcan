"""
Project Vulcan: Planner Agent (Section 7 & AGENT-04)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Formulate automation strategy prioritizing existing trusted automation:
  Retrieve -> Compose -> Adapt -> Generate
- Generation is strictly the last resort
"""
from __future__ import annotations

from typing import Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, PlannerDecision, PlannerOutput


class PlannerAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.PLANNER,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Formulate execution strategy enforcing Retrieve -> Compose -> Adapt -> Generate precedence.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return PlannerOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> PlannerOutput:
        discovered = ctx.discovered_assets
        curated_candidates = [
            c for c in discovered
            if c.get("is_curated") or c.get("trust_state") == "CURATED"
        ]

        if curated_candidates:
            # Prefer composing or reusing curated assets
            selected = [curated_candidates[0].get("identifier", "vulcan.database.postgresql_cluster")]
            decision = PlannerDecision.COMPOSE
            missing = []
            strategy = f"Compose workflow leveraging trusted curated asset '{selected[0]}'."
            next_state = WorkflowState.COMPOSING.value
        elif discovered:
            # Adapt verified candidates
            selected = [discovered[0].get("identifier", "community.automation")]
            decision = PlannerDecision.ADAPT
            missing = ["enterprise_hardening", "rollback_playbook"]
            strategy = f"Adapt candidate '{selected[0]}' by injecting enterprise hardening and rollback."
            next_state = WorkflowState.GENERATING.value
        else:
            # Fallback: Generate specification-first
            selected = []
            decision = PlannerDecision.GENERATE
            missing = ["entire_automation_stack"]
            strategy = "Generate complete automation package from desired state specification."
            next_state = WorkflowState.GENERATING.value

        engine = "ansible"
        if "terraform" in ctx.original_request.lower():
            engine = "terraform"

        return PlannerOutput(
            workflow_id=ctx.workflow_id,
            decision=decision,
            selected_assets=selected,
            missing_capabilities=missing,
            execution_strategy=strategy,
            target_engine=engine,
            proposed_next_state=next_state,
            confidence=0.97,
            rationale=f"Strategy '{decision.value}' selected following reuse precedence rules.",
        )
