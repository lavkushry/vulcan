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
        known_params = ctx.normalized_intent.get("known_parameters", {}) if isinstance(ctx.normalized_intent, dict) else {}
        software = known_params.get("software", "")
        if not software:
            if "postgres" in goal.lower():
                software = "postgresql"
            elif "redis" in goal.lower():
                software = "redis"
            elif "docker" in goal.lower():
                software = "docker"
            elif "nginx" in goal.lower():
                software = "nginx"
            else:
                software = "general"

        target_host = known_params.get("target_host", "db-cluster.internal" if software == "postgresql" else "sandbox")
        os_platform = known_params.get("os_platform", "rhel9" if software == "postgresql" else "ubuntu22")
        port = known_params.get("port", 5432 if software == "postgresql" else (6379 if software == "redis" else 80))

        # 1. Resource Contract (tailored to requested automation)
        deps = {
            "target_inventory": ResourceDependency(
                resource_type="inventory", provider="local", required=True, description=f"{os_platform} cluster nodes"
            )
        }
        if ctx.environment.upper() == "PROD" or known_params.get("secrets") == "cyberark":
            deps["cyberark_pam"] = ResourceDependency(
                resource_type="credentials", provider="cyberark", required=True, description="Root SSH key / CCP"
            )
        if ctx.environment.upper() == "PROD" or known_params.get("itsm") == "servicenow":
            deps["servicenow_chg"] = ResourceDependency(
                resource_type="itsm", provider="servicenow", required=True, description="Change Ticket verification"
            )
        if known_params.get("monitoring") == "datadog" or "datadog" in goal.lower():
            deps["datadog_apm"] = ResourceDependency(
                resource_type="monitoring", provider="datadog", required=False, description="Host & DB metrics"
            )
        if known_params.get("backup") == "s3" or "s3" in goal.lower():
            deps["s3_backup"] = ResourceDependency(
                resource_type="storage", provider="s3", required=True, description="Immutable WAL/backup storage"
            )

        contract = ResourceContract(dependencies=deps)

        # 2. Desired State Postconditions (tailored to software)
        probes = []
        if software == "postgresql":
            probes = [
                PostconditionProbeDef(
                    probe_id="probe-pg-port",
                    target=target_host,
                    probe_type="port_open",
                    expected_value=port,
                    independent_channel=True,
                ),
                PostconditionProbeDef(
                    probe_id="probe-pg-service",
                    target=target_host,
                    probe_type="service_active",
                    expected_value="active",
                    independent_channel=True,
                ),
                PostconditionProbeDef(
                    probe_id="probe-storage-500gb",
                    target=target_host,
                    probe_type="disk_capacity",
                    expected_value="500GB",
                    independent_channel=True,
                ),
            ]
        elif software == "redis":
            probes = [
                PostconditionProbeDef(
                    probe_id=f"probe-redis-port-{port}",
                    target=target_host,
                    probe_type="port_open",
                    expected_value=port,
                    independent_channel=True,
                ),
                PostconditionProbeDef(
                    probe_id="probe-redis-service",
                    target=target_host,
                    probe_type="service_active",
                    expected_value="active",
                    independent_channel=True,
                ),
            ]
        elif software == "docker":
            probes = [
                PostconditionProbeDef(
                    probe_id="probe-docker-service",
                    target=target_host,
                    probe_type="service_active",
                    expected_value="active",
                    independent_channel=True,
                ),
            ]
        elif software == "nginx":
            probes = [
                PostconditionProbeDef(
                    probe_id=f"probe-nginx-port-{port}",
                    target=target_host,
                    probe_type="port_open",
                    expected_value=port,
                    independent_channel=True,
                ),
                PostconditionProbeDef(
                    probe_id="probe-nginx-service",
                    target=target_host,
                    probe_type="service_active",
                    expected_value="active",
                    independent_channel=True,
                ),
            ]
        else:
            probes = [
                PostconditionProbeDef(
                    probe_id="probe-generic-service",
                    target=target_host,
                    probe_type="service_active",
                    expected_value="active",
                    independent_channel=True,
                ),
            ]

        # 3. Desired State & Specification
        desired_state = ctx.desired_state or {}
        if not desired_state:
            if software == "postgresql":
                desired_state = {"software": "postgresql", "version": known_params.get("db_version", 16), "storage": "500GB", "nodes": known_params.get("node_count", 3), "port": port}
            elif software == "redis":
                desired_state = {"software": "redis", "port": port, "maxmemory_mb": known_params.get("maxmemory_mb", 256), "bind_address": known_params.get("bind_address", "0.0.0.0")}
            elif software == "docker":
                desired_state = {"software": "docker", "target_user": known_params.get("target_user", "vulcan")}
            elif software == "nginx":
                desired_state = {"software": "nginx", "port": port}
            else:
                desired_state = {"software": software, "params": known_params}

        ansible_deps = ["ansible.builtin"]
        if software == "postgresql":
            ansible_deps.append("community.postgresql")
        elif software == "redis":
            ansible_deps.append("community.general")

        spec = AutomationSpecification(
            spec_id=f"spec-{ctx.workflow_id[:12]}",
            goal=goal,
            engine=engine,
            supported_platforms=[os_platform, "rockylinux9" if "rhel" in os_platform else "ubuntu22"],
            desired_state=desired_state,
            input_schema={"type": "object", "properties": {k: {"type": "string"} for k in known_params}},
            output_schema={"type": "object", "properties": {"cluster_endpoint": {"type": "string"}}},
            dependencies=ansible_deps,
            resource_contract=contract,
            execution_dag=ctx.automation_plan.get("execution_graph", []),
            risk_level=ctx.risk_classification.get("risk_tier", "HIGH" if software == "postgresql" else "MEDIUM"),
            postconditions=probes,
            idempotency_requirements=["ansible_check_mode_clean", "zero_changed_on_second_run"],
            rollback_requirements={"strategy": f"stop_{software}_service_and_restore", "artifact": "rollback.yml"},
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
