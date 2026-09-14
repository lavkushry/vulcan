"""
Project Vulcan: Builder Agent (Section 7 & AGENT-05)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Generate missing automation capabilities strictly specification-first:
  Desired State Specification -> Resource Contract -> Automation Specification -> Execution Graph -> Implementation -> Tests -> Rollback -> Documentation
- Uses AutomationCompiler to guarantee reproducible, versioned immutable artifacts
"""
from __future__ import annotations

from typing import Type
from app.agentos.agents.base import BaseAgent
from app.agentos.compiler import AutomationCompiler
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, BuilderOutput
from app.agentos.specification import (
    AutomationSpecification,
    PostconditionProbeDef,
    ResourceContract,
    ResourceDependency,
)


class BuilderAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.BUILDER,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Compile declarative specifications into immutable, hardened Ansible/Terraform artifacts.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return BuilderOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> BuilderOutput:
        engine = ctx.automation_plan.get("target_engine", "ansible")
        goal = ctx.original_request

        # 1. Resource Contract
        contract = ResourceContract(
            dependencies={
                "target_inventory": ResourceDependency(
                    resource_type="inventory", provider="local", required=True, description="RHEL 9 cluster nodes"
                ),
                "cyberark_pam": ResourceDependency(
                    resource_type="credentials", provider="cyberark", required=True, description="Root SSH key / CCP"
                ),
                "servicenow_chg": ResourceDependency(
                    resource_type="itsm", provider="servicenow", required=True, description="Change Ticket verification"
                ),
                "datadog_apm": ResourceDependency(
                    resource_type="monitoring", provider="datadog", required=False, description="Host & DB metrics"
                ),
                "s3_backup": ResourceDependency(
                    resource_type="storage", provider="s3", required=True, description="Immutable WAL/basebackup storage"
                ),
            }
        )

        # 2. Desired State Postconditions
        probes = [
            PostconditionProbeDef(
                probe_id="probe-pg-port",
                target="db-cluster.internal",
                probe_type="port_open",
                expected_value=5432,
                independent_channel=True,
            ),
            PostconditionProbeDef(
                probe_id="probe-pg-service",
                target="db-cluster.internal",
                probe_type="service_active",
                expected_value="active",
                independent_channel=True,
            ),
            PostconditionProbeDef(
                probe_id="probe-storage-500gb",
                target="db-cluster.internal",
                probe_type="disk_capacity",
                expected_value="500GB",
                independent_channel=True,
            ),
        ]

        # 3. Intermediate AutomationSpecification
        spec = AutomationSpecification(
            spec_id=f"spec-{ctx.workflow_id[:12]}",
            goal=goal,
            engine=engine,
            supported_platforms=["rhel9", "rockylinux9"],
            desired_state=ctx.desired_state or {"version": 16, "storage": "500GB", "nodes": 3},
            input_schema={"type": "object", "properties": {"cluster_size": {"type": "integer", "default": 3}}},
            output_schema={"type": "object", "properties": {"cluster_endpoint": {"type": "string"}}},
            dependencies=["ansible.builtin", "community.postgresql"],
            resource_contract=contract,
            execution_dag=ctx.automation_plan.get("execution_graph", []),
            risk_level=ctx.risk_classification.get("risk_tier", "HIGH"),
            postconditions=probes,
            idempotency_requirements=["ansible_check_mode_clean", "zero_changed_on_second_run"],
            rollback_requirements={"strategy": "stop_service_and_restore_backup", "artifact": "rollback.yml"},
        )

        # 4. Compile via AutomationCompiler
        compiled = AutomationCompiler.compile(spec)

        return BuilderOutput(
            workflow_id=ctx.workflow_id,
            engine=engine,
            artifact_id=compiled.artifact_id,
            artifact_sha256=compiled.artifact_sha256,
            spec_hash=compiled.spec_hash,
            files=compiled.files,
            test_files=compiled.test_files,
            rollback_files=compiled.rollback_files,
            postconditions=compiled.postconditions,
            proposed_next_state=WorkflowState.RESOLVING_RESOURCES.value,
            confidence=0.99,
            rationale=f"Compiled specification-first into immutable package [{compiled.artifact_sha256[:12]}].",
        )
