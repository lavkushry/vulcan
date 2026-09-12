"""
Project Vulcan: Supervisor Agent (Section 7)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Determine which specialist should act next based on current state and context
- Never directly execute infrastructure
- Never generate production shell commands
- Never bypass deterministic state-machine rules
Output structured delegation only.
"""
from __future__ import annotations

from typing import Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, SupervisorOutput


class SupervisorAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.SUPERVISOR,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Direct the workflow progression to the appropriate specialist agent.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return SupervisorOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> SupervisorOutput:
        state = ctx.current_state

        if state == WorkflowState.RECEIVED:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.INTENT,
                objective="Normalize operator intent and extract explicit requirements.",
                proposed_next_state=WorkflowState.UNDERSTANDING.value,
                confidence=1.0,
                rationale="New request received; delegating to Intent Agent.",
            )

        elif state == WorkflowState.UNDERSTANDING:
            if ctx.unresolved_questions or (ctx.normalized_intent.get("requires_operator_input")):
                return SupervisorOutput(
                    workflow_id=ctx.workflow_id,
                    delegated_agent=AgentRole.SUPERVISOR,
                    objective="Awaiting critical operator input for missing parameters.",
                    proposed_next_state=WorkflowState.WAITING_FOR_INPUT.value,
                    stop_and_wait_for_input=True,
                    confidence=1.0,
                    rationale="Unresolved critical assumptions detected; halting in WAITING_FOR_INPUT.",
                )
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.DISCOVERY,
                objective="Search curated catalog and registries for matching automation.",
                proposed_next_state=WorkflowState.DISCOVERING.value,
                confidence=1.0,
                rationale="Intent is clear; proceed to asset discovery.",
            )

        elif state == WorkflowState.DISCOVERING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.DISCOVERY,
                objective="Search curated catalog and registries for matching automation.",
                proposed_next_state=WorkflowState.PLANNING.value,
                confidence=1.0,
                rationale="Perform discovery across registries.",
            )

        elif state == WorkflowState.PLANNING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.PLANNER,
                objective="Formulate reuse-first execution strategy.",
                proposed_next_state=WorkflowState.COMPOSING.value,
                confidence=1.0,
                rationale="Formulate execution strategy (Retrieve -> Compose -> Adapt -> Generate).",
            )

        elif state == WorkflowState.COMPOSING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.COMPOSER,
                objective="Assemble execution DAG and compile automation artifacts.",
                proposed_next_state=WorkflowState.RESOLVING_RESOURCES.value,
                confidence=1.0,
                rationale="Compose execution graph and artifacts.",
            )

        elif state == WorkflowState.GENERATING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.BUILDER,
                objective="Generate missing automation capabilities specification-first.",
                proposed_next_state=WorkflowState.RESOLVING_RESOURCES.value,
                confidence=1.0,
                rationale="Generate missing automation capabilities.",
            )

        elif state == WorkflowState.RESOLVING_RESOURCES:
            missing = ctx.required_resources
            missing_unresolved = [r for r in missing if not r.get("is_available", False) and r.get("required", True)]
            if missing_unresolved:
                return SupervisorOutput(
                    workflow_id=ctx.workflow_id,
                    delegated_agent=AgentRole.RESOURCE,
                    objective=f"Waiting for {len(missing_unresolved)} external resources.",
                    proposed_next_state=WorkflowState.WAITING_FOR_RESOURCE.value,
                    stop_and_wait_for_resource=True,
                    confidence=1.0,
                    rationale="Required external resources not configured; halting in WAITING_FOR_RESOURCE.",
                )
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.RESOURCE,
                objective="Resolve external dependencies and secret references.",
                proposed_next_state=WorkflowState.VALIDATING.value,
                confidence=1.0,
                rationale="Resolve external resources against registry.",
            )

        elif state == WorkflowState.VALIDATING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.VALIDATOR,
                objective="Execute preflight syntax, lint, sandbox, and secret checks.",
                proposed_next_state=WorkflowState.SECURITY_REVIEW.value,
                confidence=1.0,
                rationale="Validation factory preflight execution.",
            )

        elif state == WorkflowState.SECURITY_REVIEW:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.SECURITY,
                objective="Scan for vulnerabilities, privilege escalation, and injection.",
                proposed_next_state=WorkflowState.CRITIC_REVIEW.value,
                confidence=1.0,
                rationale="Validation passed; delegating to Security Agent.",
            )

        elif state == WorkflowState.TESTING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.TEST,
                objective="Execute isolated sandbox and functional invariant tests.",
                proposed_next_state=WorkflowState.CRITIC_REVIEW.value,
                confidence=1.0,
                rationale="Run sandbox test suite before critic review.",
            )

        elif state == WorkflowState.CRITIC_REVIEW:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.CRITIC,
                objective="Attempt to prove proposed automation defective.",
                proposed_next_state=WorkflowState.POLICY_CHECK.value,
                confidence=1.0,
                rationale="Security approved; delegating to Critic Agent.",
            )

        elif state == WorkflowState.POLICY_CHECK:
            risk = ctx.risk_classification.get("risk_tier", "MEDIUM")
            if risk in ("HIGH", "CRITICAL") or ctx.environment == "PROD":
                return SupervisorOutput(
                    workflow_id=ctx.workflow_id,
                    delegated_agent=AgentRole.SUPERVISOR,
                    objective="Awaiting human maker-checker sign-off.",
                    proposed_next_state=WorkflowState.WAITING_FOR_APPROVAL.value,
                    confidence=1.0,
                    rationale="High/Prod risk requires maker-checker approval.",
                )
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.SUPERVISOR,
                objective="Execution authorization granted.",
                proposed_next_state=WorkflowState.EXECUTION_READY.value,
                confidence=1.0,
                rationale="Low risk automated policy check passed.",
            )

        elif state == WorkflowState.WAITING_FOR_APPROVAL:
            if ctx.approval_records:
                return SupervisorOutput(
                    workflow_id=ctx.workflow_id,
                    delegated_agent=AgentRole.SUPERVISOR,
                    objective="Approval verified; issue capability token.",
                    proposed_next_state=WorkflowState.EXECUTION_READY.value,
                    confidence=1.0,
                    rationale="Maker-checker approval recorded.",
                )
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.SUPERVISOR,
                objective="Still waiting for approval.",
                proposed_next_state=WorkflowState.WAITING_FOR_APPROVAL.value,
                confidence=1.0,
                rationale="No approval recorded yet.",
            )

        elif state == WorkflowState.EXECUTION_READY:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.EXECUTOR,
                objective="Execute approved immutable package under capability token.",
                proposed_next_state=WorkflowState.EXECUTING.value,
                confidence=1.0,
                rationale="Capability token issued; delegating to Executor.",
            )

        elif state == WorkflowState.EXECUTING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.VERIFIER,
                objective="Verify desired state independently using read-only probes.",
                proposed_next_state=WorkflowState.VERIFYING.value,
                confidence=1.0,
                rationale="Execution finished; delegating to Verifier.",
            )

        elif state == WorkflowState.VERIFYING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.VERIFIER,
                objective="Verify desired state independently using read-only probes.",
                proposed_next_state=WorkflowState.SUCCESS.value,
                confidence=1.0,
                rationale="Execution completed; verify postconditions.",
            )

        elif state == WorkflowState.SUCCESS:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.CURATOR,
                objective="Evaluate successful automation for catalog promotion.",
                proposed_next_state=WorkflowState.EVALUATING.value,
                confidence=1.0,
                rationale="Workflow succeeded; evaluate for catalog curation.",
            )

        elif state == WorkflowState.CURATING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.EVAL,
                objective="Run trace evaluation and record benchmark metrics.",
                proposed_next_state=WorkflowState.EVALUATING.value,
                confidence=1.0,
                rationale="Curation stage complete; advance to evaluation.",
            )

        elif state == WorkflowState.EVALUATING:
            return SupervisorOutput(
                workflow_id=ctx.workflow_id,
                delegated_agent=AgentRole.EVAL,
                objective="Run trace evaluation and record benchmark metrics.",
                proposed_next_state=WorkflowState.EVALUATING.value,
                confidence=1.0,
                rationale="Curation complete; evaluate benchmark scoring.",
            )

        return SupervisorOutput(
            workflow_id=ctx.workflow_id,
            delegated_agent=AgentRole.SUPERVISOR,
            objective="Workflow terminal or manual intervention required.",
            proposed_next_state=ctx.current_state.value,
            confidence=1.0,
            rationale="No further automated steps.",
        )
