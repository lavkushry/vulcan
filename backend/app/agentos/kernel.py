"""
Project Vulcan: AgentOS Ultra Kernel (Section 5, 6, 7 & AGENT-01)
Author: Architectural Review Board & AgentOS Core Team

The central orchestration kernel for governed multi-agent infrastructure automation:
- Orchestrates multi-agent delegation via Supervisor
- Commits state transitions strictly through deterministic state machine
- Enforces optimistic concurrency and durable persistence
- Manages interactive pause/resume (WAITING_FOR_INPUT, WAITING_FOR_RESOURCE)
- Binds approved execution to cryptographic Capability Tokens
- Guarantees: Agent Intelligence -> Structured Proposal -> Deterministic Governance -> Constrained Execution -> Independent Verification
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.agentos.context import OptimisticLockError, StateTransitionError, WorkflowContext, WorkflowEvent, WorkflowState
from app.agentos.evidence import Evidence, EvidenceEngine, EvidenceType
from app.agentos.confidence import ConfidenceEngine
from app.agentos.schemas import AgentRole, ExecutionCapabilityToken
from app.agentos.gateway import ToolGateway
from app.agentos.repository import PostgresAgentWorkflowRepository
from app.agentos.agents.supervisor import SupervisorAgent
from app.agentos.agents.intent import IntentAgent
from app.agentos.agents.context import ContextAgent
from app.agentos.agents.discovery import DiscoveryAgent
from app.agentos.agents.risk import RiskAgent
from app.agentos.agents.planner import PlannerAgent
from app.agentos.agents.composer import ComposerAgent
from app.agentos.agents.builder import BuilderAgent
from app.agentos.agents.resource import ResourceAgent
from app.agentos.agents.validator import ValidatorAgent
from app.agentos.agents.test_agent import TestAgent
from app.agentos.agents.security import SecurityAgent
from app.agentos.agents.critic import CriticAgent
from app.agentos.agents.executor import ConstrainedExecutor
from app.agentos.agents.verifier import VerifierAgent, IVerificationProbeRunner
from app.agentos.agents.rollback import RollbackAgent
from app.agentos.agents.curator import CuratorAgent
from app.agentos.agents.eval import EvalAgent
from app.ports.repositories import IExternalResourceRepository

from app.agentos.policy_engine import IPolicyEngine, PolicyDecision, SimulationPolicyEngine
from app.agentos.adapters.execution_adapter import IAgentOSExecutionAdapter, SimulationExecutionAdapter
from app.agentos.adapters.foundry_adapter import IAgentRuntime, DeterministicAgentRuntime

logger = logging.getLogger("vulcan.agentos_kernel")


class AgentOSKernel:
    """
    Durable Multi-Agent Automation Operating System Kernel.
    Enforces deterministic state transitions, Maker-Checker separation,
    immutable capability tokens, and read-only desired-state verification.
    """

    def __init__(
        self,
        repository: Optional[PostgresAgentWorkflowRepository] = None,
        external_resource_repo: Optional[IExternalResourceRepository] = None,
        policy_engine: Optional[IPolicyEngine] = None,
        execution_adapter: Optional[IAgentOSExecutionAdapter] = None,
        agent_runtime: Optional[IAgentRuntime] = None,
        probe_runner: Optional[IVerificationProbeRunner] = None,
    ):
        is_prod = os.environ.get("AGENTOS_MODE", "").lower() == "production"

        if is_prod:
            if policy_engine is None or getattr(policy_engine, "is_simulation", False):
                raise RuntimeError("Production mode forbids SimulationPolicyEngine")
            if agent_runtime is None or getattr(agent_runtime, "is_simulation", False):
                raise RuntimeError("Production mode forbids DeterministicAgentRuntime")
            if execution_adapter is None or getattr(execution_adapter, "is_simulation", False):
                raise RuntimeError("Production mode forbids SimulationExecutionAdapter")
            if probe_runner is None or getattr(probe_runner, "is_simulation", False):
                raise RuntimeError("Production mode forbids SimulationProbeRunner")
            if not os.environ.get("VULCAN_CAPABILITY_HMAC_KEY"):
                raise RuntimeError("VULCAN_CAPABILITY_HMAC_KEY is required in production mode")

        self.repository = repository or PostgresAgentWorkflowRepository()
        self.external_resource_repo = external_resource_repo
        
        # Default imports for the engine
        from app.agentos.policy_engine import GovernancePolicyEngine
        from app.agentos.adapters.execution_adapter import AnsibleRunnerExecutionAdapter
        from app.agentos.adapters.foundry_adapter import FoundryAgentRuntime
        from app.agentos.agents.verifier import ProductionProbeRunner

        if is_prod:
            self.policy_engine = policy_engine or GovernancePolicyEngine()
            self.agent_runtime = agent_runtime or FoundryAgentRuntime()
            execution_adapter_default = AnsibleRunnerExecutionAdapter()
            probe_runner_default = ProductionProbeRunner()
        else:
            self.policy_engine = policy_engine or SimulationPolicyEngine()
            self.agent_runtime = agent_runtime or DeterministicAgentRuntime()
            execution_adapter_default = SimulationExecutionAdapter()
            from app.agentos.agents.verifier import SimulationProbeRunner
            probe_runner_default = SimulationProbeRunner()

        # Initialize Specialist Agents
        self.supervisor = SupervisorAgent()
        self.intent_agent = IntentAgent()
        self.context_agent = ContextAgent()
        self.discovery_agent = DiscoveryAgent()
        self.risk_agent = RiskAgent()
        self.planner_agent = PlannerAgent()
        self.composer_agent = ComposerAgent()
        self.builder_agent = BuilderAgent()
        self.resource_agent = ResourceAgent(resource_repo=self.external_resource_repo)
        self.validator_agent = ValidatorAgent()
        self.test_agent = TestAgent()
        self.security_agent = SecurityAgent()
        self.critic_agent = CriticAgent()
        self.executor = ConstrainedExecutor(adapter=execution_adapter or execution_adapter_default)
        self.verifier_agent = VerifierAgent(probe_runner=probe_runner or probe_runner_default)
        self.rollback_agent = RollbackAgent()
        self.curator_agent = CuratorAgent()
        self.eval_agent = EvalAgent()
        self.tool_gateway = ToolGateway.create_default_gateway()

    # -------------------------------------------------------------------------
    # WORKFLOW INITIALIZATION
    # -------------------------------------------------------------------------


    def create_workflow(
        self,
        original_request: str,
        requester_id: str = "operator@corp.internal",
        environment: str = "PROD",
        correlation_id: Optional[str] = None,
    ) -> WorkflowContext:
        """Initializes a canonical WorkflowContext in RECEIVED state."""
        wf_id = f"wf-{uuid.uuid4().hex[:12]}"
        corr_id = correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}"

        ctx = WorkflowContext(
            workflow_id=wf_id,
            correlation_id=corr_id,
            requester_id=requester_id,
            environment=environment.upper(),
            original_request=original_request,
            current_state=WorkflowState.RECEIVED,
            version=1,
        )

        event = WorkflowEvent(
            workflow_id=wf_id,
            correlation_id=corr_id,
            from_state=WorkflowState.RECEIVED,
            to_state=WorkflowState.RECEIVED,
            actor=requester_id,
            reason="Workflow received and initialized",
        )

        self.repository.save_workflow(ctx)
        self.repository.record_event(event)
        logger.info("Created AgentOS workflow [%s] for requester [%s]", wf_id, requester_id)
        return ctx

    # -------------------------------------------------------------------------
    # WORKFLOW STEP EXECUTION
    # -------------------------------------------------------------------------

    def step(self, workflow_id: str) -> WorkflowContext:
        """
        Advances the workflow by one stage.
        Queries Supervisor for delegation, invokes the designated specialist,
        validates the proposed transition deterministically, and saves state.
        """
        ctx = self.repository.get_workflow(workflow_id)
        if not ctx:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        # Terminal or pause states do not auto-advance
        if ctx.current_state in (
            WorkflowState.WAITING_FOR_INPUT,
            WorkflowState.WAITING_FOR_RESOURCE,
            WorkflowState.WAITING_FOR_APPROVAL,
            WorkflowState.MANUAL_INTERVENTION_REQUIRED,
            WorkflowState.POLICY_DENIED,
            WorkflowState.ROLLED_BACK,
        ):
            return ctx

        if ctx.current_state == WorkflowState.EVALUATING and ctx.eval_result:
            return ctx

        # 1. Supervisor Delegation
        sup_out = self.supervisor.execute(ctx)
        target_role = sup_out.delegated_agent

        # 2. Invoke Specialist Agent
        if target_role == AgentRole.INTENT:
            if ctx.current_state == WorkflowState.RECEIVED:
                ev_init = ctx.transition_to(
                    WorkflowState.UNDERSTANDING,
                    actor="supervisor",
                    agent_name="supervisor",
                    agent_version=self.supervisor.version,
                    reason="Request received; advancing to UNDERSTANDING.",
                )
                self.repository.record_event(ev_init)

            intent_out = self.intent_agent.execute(ctx)
            ctx.normalized_intent = intent_out.model_dump()
            ctx.desired_state = {"outcome": intent_out.desired_outcome, "domain": intent_out.automation_domain}
            ctx.assumptions = intent_out.assumptions
            ctx.unresolved_questions = intent_out.missing_parameters

            # Check for risk right after intent
            risk_out = self.risk_agent.execute(ctx)
            ctx.risk_classification = risk_out.model_dump()

            next_state = (
                WorkflowState.WAITING_FOR_INPUT
                if intent_out.requires_operator_input
                else WorkflowState.DISCOVERING
            )
            event = ctx.transition_to(
                next_state,
                actor="intent_agent",
                agent_name="intent",
                agent_version=self.intent_agent.version,
                reason=intent_out.rationale,
            )

        elif target_role == AgentRole.DISCOVERY:
            if ctx.current_state == WorkflowState.UNDERSTANDING:
                ev_disc = ctx.transition_to(
                    WorkflowState.DISCOVERING,
                    actor="supervisor",
                    agent_name="supervisor",
                    agent_version=self.supervisor.version,
                    reason="Intent clarified; advancing to DISCOVERING.",
                )
                self.repository.record_event(ev_disc)

            disc_out = self.discovery_agent.execute(ctx)
            ctx.discovered_assets = [c.model_dump() for c in disc_out.candidates]
            event = ctx.transition_to(
                WorkflowState.PLANNING,
                actor="discovery_agent",
                agent_name="discovery",
                agent_version=self.discovery_agent.version,
                reason=disc_out.rationale,
            )

        elif target_role == AgentRole.PLANNER:
            plan_out = self.planner_agent.execute(ctx)
            ctx.automation_plan = plan_out.model_dump()
            target_next = WorkflowState(plan_out.proposed_next_state)
            event = ctx.transition_to(
                target_next,
                actor="planner_agent",
                agent_name="planner",
                agent_version=self.planner_agent.version,
                reason=plan_out.rationale,
            )

        elif target_role == AgentRole.COMPOSER:
            comp_out = self.composer_agent.execute(ctx)
            ctx.automation_plan["dag_steps"] = [s.model_dump() for s in comp_out.dag_steps]
            ctx.automation_plan["execution_graph"] = comp_out.execution_graph
            ctx.automation_plan["rollback_dag"] = comp_out.rollback_dag

            # Builder compiles missing capabilities or role tasks
            build_out = self.builder_agent.execute(ctx)
            ctx.generated_artifacts = [build_out.model_dump()]

            event = ctx.transition_to(
                WorkflowState.RESOLVING_RESOURCES,
                actor="composer_agent",
                agent_name="composer",
                agent_version=self.composer_agent.version,
                reason=comp_out.rationale,
            )

        elif target_role == AgentRole.BUILDER:
            build_out = self.builder_agent.execute(ctx)
            ctx.generated_artifacts = [build_out.model_dump()]
            event = ctx.transition_to(
                WorkflowState.RESOLVING_RESOURCES,
                actor="builder_agent",
                agent_name="builder",
                agent_version=self.builder_agent.version,
                reason=build_out.rationale,
            )

        elif target_role == AgentRole.RESOURCE:
            res_out = self.resource_agent.execute(ctx)
            ctx.required_resources = [r.model_dump() for r in res_out.required_resources]
            ctx.resolved_resources = res_out.resolved_resources
            ctx.secret_references = res_out.secret_references

            target_next = (
                WorkflowState.VALIDATING
                if res_out.all_dependencies_satisfied
                else WorkflowState.WAITING_FOR_RESOURCE
            )
            event = ctx.transition_to(
                target_next,
                actor="resource_agent",
                agent_name="resource",
                agent_version=self.resource_agent.version,
                reason=res_out.rationale,
            )

        elif target_role == AgentRole.VALIDATOR:
            val_out = self.validator_agent.execute(ctx)
            ctx.validation_results = [c.model_dump() for c in val_out.checks]
            target_next = (
                WorkflowState.SECURITY_REVIEW
                if val_out.all_passed
                else WorkflowState.VALIDATION_FAILED
            )
            event = ctx.transition_to(
                target_next,
                actor="validator_agent",
                agent_name="validator",
                agent_version=self.validator_agent.version,
                reason=val_out.rationale,
            )

        elif target_role == AgentRole.SECURITY:
            sec_out = self.security_agent.execute(ctx)
            ctx.security_findings = [f.model_dump() for f in sec_out.findings]
            target_next = (
                WorkflowState.CRITIC_REVIEW
                if sec_out.verdict == "APPROVED"
                else WorkflowState.SECURITY_REJECTED
            )
            event = ctx.transition_to(
                target_next,
                actor="security_agent",
                agent_name="security",
                agent_version=self.security_agent.version,
                reason=sec_out.rationale,
            )

        elif target_role == AgentRole.TEST or ctx.current_state == WorkflowState.TESTING:
            test_out = self.test_agent.execute(ctx)
            ctx.test_results = [t.model_dump() for t in test_out.test_cases]
            target_next = (
                WorkflowState.CRITIC_REVIEW
                if test_out.all_passed
                else WorkflowState.TEST_FAILED
            )
            event = ctx.transition_to(
                target_next,
                actor="test_agent",
                agent_name="test",
                agent_version=self.test_agent.version,
                reason=test_out.rationale,
            )

        elif target_role == AgentRole.CRITIC:
            crit_out = self.critic_agent.execute(ctx)
            ctx.critic_findings = [d.model_dump() for d in crit_out.defects_found]
            target_next = (
                WorkflowState.POLICY_CHECK
                if not crit_out.blocks_workflow
                else WorkflowState.PLAN_REJECTED
            )
            event = ctx.transition_to(
                target_next,
                actor="critic_agent",
                agent_name="critic",
                agent_version=self.critic_agent.version,
                reason=crit_out.rationale,
            )

        elif ctx.current_state == WorkflowState.POLICY_CHECK:
            # Policy evaluation via pluggable engine
            decision = self.policy_engine.evaluate(ctx)
            ctx.policy_decision = {
                "decision": decision.decision,
                "decision_id": decision.decision_id,
                "reason": decision.reason,
                "change_ticket": decision.change_ticket,
                "in_maintenance_window": decision.in_maintenance_window,
                "is_simulation": self.policy_engine.is_simulation,
            }
            if decision.decision == "REQUIRES_APPROVAL":
                event = ctx.transition_to(
                    WorkflowState.WAITING_FOR_APPROVAL,
                    actor="policy_engine",
                    reason=decision.reason,
                )
            elif decision.decision == "APPROVED":
                event = ctx.transition_to(
                    WorkflowState.EXECUTION_READY,
                    actor="policy_engine",
                    reason=decision.reason,
                )
            else:  # DENIED
                event = ctx.transition_to(
                    WorkflowState.POLICY_DENIED,
                    actor="policy_engine",
                    reason=decision.reason,
                )

        elif target_role == AgentRole.EXECUTOR:
            # Requires capability token!
            artifact_sha = ctx.generated_artifacts[0].get("artifact_sha256") if ctx.generated_artifacts else "sha256-default"
            target_id = (
                ctx.normalized_intent.get("known_parameters", {}).get("target_host")
                or ctx.desired_state.get("target_host")
                or ctx.execution_plan.get("target_id")
                or "db-cluster.internal"
            )

            token_id = f"cap-{uuid.uuid4().hex[:12]}"
            token = ExecutionCapabilityToken(
                token_id=token_id,
                workflow_id=ctx.workflow_id,
                artifact_sha256=artifact_sha,
                parameter_hash=hashlib.sha256(json.dumps(ctx.desired_state, sort_keys=True).encode()).hexdigest(),
                target_resource_id=target_id,
                environment=ctx.environment,
                approval_id="appr-auto" if not ctx.approval_records else ctx.approval_records[-1].get("approver_id", "appr-sys"),
                policy_decision_id=ctx.policy_decision.get("decision_id", "pol-unknown"),
                allowed_action="EXECUTE",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            hmac_key = os.environ.get("VULCAN_CAPABILITY_HMAC_KEY", "")
            if hmac_key:
                token.hmac_signature = ExecutionCapabilityToken.compute_hmac(token, hmac_key)
            self.repository.save_capability_token(token)

            # Files dict for executor (includes all compiled package files)
            files = {}
            if ctx.generated_artifacts:
                art = ctx.generated_artifacts[0]
                all_file_entries = art.get("files", []) + art.get("test_files", []) + art.get("rollback_files", [])
                for f in all_file_entries:
                    files[f.get("path")] = f.get("content")

            # Transition to EXECUTING
            ctx.transition_to(WorkflowState.EXECUTING, actor="kernel", reason="Capability token issued; executing.")

            # Atomically consume capability token BEFORE execution
            consumed_token = self.repository.consume_capability_token(token.token_id)
            if not consumed_token:
                event = ctx.transition_to(
                    WorkflowState.EXECUTION_FAILED, 
                    actor="kernel", 
                    reason="Capability token consumption failed. Token already used or expired."
                )
                self.repository.save_workflow(ctx)
                self.repository.record_event(event)
                return ctx

            # Run Executor with the original token (is_used=False in memory)
            exec_res = self.executor.execute(
                token=token,
                artifact_files=files,
                target_resource_id=target_id,
                parameters=ctx.desired_state,
                environment=ctx.environment,
            )
            ctx.execution_result = exec_res.model_dump()
            
            # Update used_at timestamp from the executor result
            self.repository.save_capability_token(token)

            event = ctx.transition_to(
                WorkflowState.VERIFYING,
                actor="executor",
                reason=f"Runner completed with exit code {exec_res.exit_code}.",
            )

        elif target_role == AgentRole.VERIFIER:
            ver_out = self.verifier_agent.execute(ctx)
            ctx.postcondition_verification = ver_out.model_dump()
            target_next = (
                WorkflowState.SUCCESS
                if ver_out.all_passed
                else WorkflowState.VERIFY_FAILED
            )
            event = ctx.transition_to(
                target_next,
                actor="verifier_agent",
                agent_name="verifier",
                agent_version=self.verifier_agent.version,
                reason=ver_out.rationale,
            )

        elif target_role == AgentRole.CURATOR:
            cur_out = self.curator_agent.execute(ctx)
            ctx.curation_state = cur_out.model_dump()
            event = ctx.transition_to(
                WorkflowState.EVALUATING,
                actor="curator_agent",
                agent_name="curator",
                agent_version=self.curator_agent.version,
                reason=cur_out.rationale,
            )

        elif target_role == AgentRole.EVAL:
            eval_out = self.eval_agent.execute(ctx)
            ctx.eval_result = eval_out.model_dump()
            ctx.version += 1
            ctx.updated_at = datetime.now(timezone.utc)
            event = WorkflowEvent(
                workflow_id=ctx.workflow_id,
                correlation_id=ctx.correlation_id,
                from_state=ctx.current_state,
                to_state=ctx.current_state,
                actor="eval_agent",
                agent_name="eval",
                agent_version=self.eval_agent.version,
                reason="Recorded evaluation benchmark score.",
                timestamp=ctx.updated_at,
            )

        else:
            return ctx

        # Persist updated context and transition event
        self.repository.save_workflow(ctx)
        self.repository.record_event(event)
        return ctx

    # -------------------------------------------------------------------------
    # OPERATOR ACTIONS (RESUME, INPUT, APPROVAL, ROLLBACK)
    # -------------------------------------------------------------------------

    def supply_input(self, workflow_id: str, operator_input: Dict[str, Any]) -> WorkflowContext:
        """Supplies missing parameters for a workflow paused in WAITING_FOR_INPUT."""
        ctx = self.repository.get_workflow(workflow_id)
        if not ctx:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        if ctx.current_state != WorkflowState.WAITING_FOR_INPUT:
            raise StateTransitionError(
                from_state=ctx.current_state.value,
                to_state=WorkflowState.UNDERSTANDING.value,
                reason="Cannot supply operator input unless workflow is in WAITING_FOR_INPUT state.",
            )

        # Merge supplied input into normalized intent
        ctx.normalized_intent.setdefault("known_parameters", {}).update(operator_input)
        ctx.unresolved_questions = [q for q in ctx.unresolved_questions if q not in operator_input]
        ctx.normalized_intent["requires_operator_input"] = (len(ctx.unresolved_questions) > 0)

        event = ctx.transition_to(
            WorkflowState.UNDERSTANDING,
            actor="operator",
            reason=f"Operator supplied parameters: {list(operator_input.keys())}",
            payload=operator_input,
        )

        self.repository.save_workflow(ctx)
        self.repository.record_event(event)
        return ctx

    def resume_after_resource_config(self, workflow_id: str) -> WorkflowContext:
        """Resumes a workflow paused in WAITING_FOR_RESOURCE after operator configured dependencies."""
        ctx = self.repository.get_workflow(workflow_id)
        if not ctx:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        if ctx.current_state != WorkflowState.WAITING_FOR_RESOURCE:
            raise StateTransitionError(
                from_state=ctx.current_state.value,
                to_state=WorkflowState.RESOLVING_RESOURCES.value,
                reason="Can only resume from WAITING_FOR_RESOURCE state.",
            )

        event = ctx.transition_to(
            WorkflowState.RESOLVING_RESOURCES,
            actor="operator",
            reason="Operator configured required external resources; re-checking dependencies.",
        )

        self.repository.save_workflow(ctx)
        self.repository.record_event(event)
        return ctx

    def approve_workflow(
        self, workflow_id: str, approver_id: str, reason: str = "Approved for execution"
    ) -> WorkflowContext:
        """Enforces Maker-Checker separation of duties before issuing execution readiness."""
        ctx = self.repository.get_workflow(workflow_id)
        if not ctx:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        if ctx.current_state != WorkflowState.WAITING_FOR_APPROVAL:
            raise StateTransitionError(
                from_state=ctx.current_state.value,
                to_state=WorkflowState.EXECUTION_READY.value,
                reason="Workflow is not currently in WAITING_FOR_APPROVAL state.",
            )

        # Enforce Maker != Checker invariant (INV-AGENT-04)
        if approver_id == ctx.requester_id:
            raise PermissionError(
                f"Maker-Checker Violation: Approver '{approver_id}' cannot approve their own requested workflow!"
            )

        approval_record = {
            "approver_id": approver_id,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        ctx.approval_records.append(approval_record)

        event = ctx.transition_to(
            WorkflowState.EXECUTION_READY,
            actor=approver_id,
            reason=f"Human Maker-Checker sign-off by {approver_id}",
            payload=approval_record,
        )

        self.repository.save_workflow(ctx)
        self.repository.record_event(event)
        return ctx

    def trigger_rollback(self, workflow_id: str) -> WorkflowContext:
        """Executes pre-validated rollback playbook when execution or verification fails."""
        ctx = self.repository.get_workflow(workflow_id)
        if not ctx:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        event1 = ctx.transition_to(
            WorkflowState.ROLLING_BACK,
            actor="kernel",
            reason="Triggering rollback following failure",
        )
        self.repository.record_event(event1)

        # Execute Rollback Agent
        rb_out = self.rollback_agent.execute(ctx)
        ctx.rollback_state = rb_out.model_dump()

        event2 = ctx.transition_to(
            WorkflowState.ROLLED_BACK,
            actor="rollback_agent",
            reason=rb_out.rationale,
        )

        self.repository.save_workflow(ctx)
        self.repository.record_event(event2)
        return ctx
