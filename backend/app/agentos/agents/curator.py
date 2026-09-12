"""
Project Vulcan: Curator Agent (Section 7, 31 & AGENT-11)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Self-improving catalog promotion lifecycle:
  GENERATED -> CANDIDATE -> VERIFIED -> CURATED
- Cannot unilaterally promote to CURATED without historical verification evidence
- Submits structured promotion proposals for verified automation assets
"""
from __future__ import annotations

from typing import Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, CuratorOutput


class CuratorAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.CURATOR,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Evaluate successful workflow executions and propose validated automation for catalog curation.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return CuratorOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> CuratorOutput:
        # Check prerequisite gates: execution success + verifier postconditions pass
        exec_ok = (ctx.execution_result.get("exit_code") == 0)
        verify_ok = ctx.postcondition_verification.get("all_passed", False)

        if exec_ok and verify_ok:
            ident = f"curated.{ctx.normalized_intent.get('automation_domain', 'infra')}.{ctx.workflow_id[:8]}"
            return CuratorOutput(
                workflow_id=ctx.workflow_id,
                proposed_promotion=True,
                item_identifier=ident,
                promotion_tier="CANDIDATE",  # Promotes to CANDIDATE first (human review required for CURATED)
                provenance={
                    "origin_workflow_id": ctx.workflow_id,
                    "artifact_sha256": ctx.execution_result.get("artifact_sha256"),
                    "verified_environment": ctx.environment,
                    "postconditions_passed": len(ctx.postcondition_verification.get("probes", [])),
                },
                rationale="Execution succeeded and 100% of desired-state postconditions verified; eligible for catalog admission.",
                proposed_next_state=WorkflowState.EVALUATING.value,
                confidence=1.0,
            )

        return CuratorOutput(
            workflow_id=ctx.workflow_id,
            proposed_promotion=False,
            item_identifier="",
            promotion_tier="REJECTED",
            provenance={},
            rationale="Workflow did not meet strict promotion threshold; postcondition or execution failed.",
            proposed_next_state=WorkflowState.EVALUATING.value,
            confidence=1.0,
        )
