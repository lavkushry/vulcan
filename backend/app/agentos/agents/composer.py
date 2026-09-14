"""
Project Vulcan: Composer Agent (Section 7 & AGENT-04)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Combine trusted roles and modules into an acyclic execution graph (DAG)
- Bind parameters, inputs, and outputs across pipeline steps
- Map failure branches to automated rollback actions
"""
from __future__ import annotations

from typing import Dict, List, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, ComposerOutput, ExecutionStep


class ComposerAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.COMPOSER,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Assemble trusted components into an ordered, failure-resilient execution DAG.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return ComposerOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> ComposerOutput:
        selected_assets = ctx.automation_plan.get("selected_assets", [])
        primary_asset = selected_assets[0] if selected_assets else "generic.automation"
        known_params = ctx.normalized_intent.get("known_parameters", {}) if isinstance(ctx.normalized_intent, dict) else {}
        prompt_lower = ctx.original_request.lower()

        software = known_params.get("software")
        if not software:
            if "postgres" in primary_asset.lower() or "postgres" in prompt_lower:
                software = "postgresql"
            elif "redis" in primary_asset.lower() or "redis" in prompt_lower:
                software = "redis"
            elif "docker" in primary_asset.lower() or "docker" in prompt_lower:
                software = "docker"
            elif "nginx" in primary_asset.lower() or "nginx" in prompt_lower:
                software = "nginx"
            else:
                software = "general"

        steps: List[ExecutionStep] = []
        dag: Dict[str, List[str]] = {}
        rollback_dag: Dict[str, str] = {}

        # 1. Step 1: Preflight
        os_platform = known_params.get("os_platform", "rhel9")
        min_disk = 500 if software == "postgresql" else 10
        step1 = ExecutionStep(
            step_id="step-1",
            name=f"1. Validate Environment & Prerequisites ({os_platform})",
            action_identifier="core-preflight-check",
            engine="ansible",
            parameters={"platform": os_platform, "min_disk_gb": min_disk},
            depends_on=[],
            rollback_step_id=None,
            postconditions=["disk_space_ok", "os_supported"],
        )
        steps.append(step1)
        dag["step-1"] = []

        # 2. Step 2: Primary Workload Step
        if software == "postgresql":
            step2_name = f"2. Provision & Configure Primary PostgreSQL {known_params.get('db_version', 16)} Cluster"
            step2_params = {
                "nodes": known_params.get("node_count", 3),
                "port": known_params.get("port", 5432),
                "storage_gb": 500,
            }
            step2_post = ["port_5432_reachable", "service_postgresql_active"]
        elif software == "redis":
            redis_port = known_params.get("port", 6379)
            step2_name = f"2. Deploy and Configure In-Memory Redis Cache (port {redis_port})"
            step2_params = {
                "port": redis_port,
                "maxmemory_mb": known_params.get("maxmemory_mb", 256),
                "bind_address": known_params.get("bind_address", "0.0.0.0"),
            }
            step2_post = [f"port_{redis_port}_reachable", "service_redis_active"]
        elif software == "docker":
            step2_name = "2. Provision Docker CE Engine & Container Runtime"
            step2_params = {"target_user": known_params.get("target_user", "vulcan")}
            step2_post = ["docker_daemon_active"]
        elif software == "nginx":
            nginx_port = known_params.get("port", 80)
            step2_name = f"2. Deploy and Harden Nginx Web Server (port {nginx_port})"
            step2_params = {"port": nginx_port}
            step2_post = [f"port_{nginx_port}_reachable", "service_nginx_active"]
        else:
            step2_name = f"2. Execute Automation for {primary_asset}"
            step2_params = dict(known_params)
            step2_post = ["execution_verified"]

        step2 = ExecutionStep(
            step_id="step-2",
            name=step2_name,
            action_identifier=primary_asset,
            engine="ansible",
            parameters=step2_params,
            depends_on=["step-1"],
            rollback_step_id="step-rollback",
            postconditions=step2_post,
        )
        steps.append(step2)
        dag["step-2"] = ["step-1"]
        rollback_dag["step-2"] = "step-rollback"

        # 3. Optional Step: Datadog Monitoring (ONLY if explicitly requested)
        if known_params.get("monitoring") == "datadog" or "datadog" in prompt_lower:
            s_idx = len(steps) + 1
            s_id = f"step-{s_idx}"
            step_dd = ExecutionStep(
                step_id=s_id,
                name=f"{s_idx}. Attach Datadog APM & Host Telemetry",
                action_identifier="datadog-agent-install",
                engine="ansible",
                parameters={"integrations": [software]},
                depends_on=["step-2"],
                rollback_step_id="step-rollback",
                postconditions=["datadog_metrics_flowing"],
            )
            steps.append(step_dd)
            dag[s_id] = ["step-2"]
            rollback_dag[s_id] = "step-rollback"

        # 4. Optional Step: S3 Backup (ONLY if explicitly requested)
        if known_params.get("backup") == "s3" or "s3" in prompt_lower:
            s_idx = len(steps) + 1
            s_id = f"step-{s_idx}"
            step_s3 = ExecutionStep(
                step_id=s_id,
                name=f"{s_idx}. Configure S3 Automated Backup Target ({software})",
                action_identifier=f"s3-{software}-backup-config",
                engine="ansible",
                parameters={"bucket_policy": "encrypted"},
                depends_on=["step-2"],
                rollback_step_id="step-rollback",
                postconditions=["s3_backup_job_verified"],
            )
            steps.append(step_s3)
            dag[s_id] = ["step-2"]
            rollback_dag[s_id] = "step-rollback"

        return ComposerOutput(
            workflow_id=ctx.workflow_id,
            dag_steps=steps,
            execution_graph=dag,
            rollback_dag=rollback_dag,
            proposed_next_state=WorkflowState.RESOLVING_RESOURCES.value,
            confidence=0.98,
            rationale=f"Composed {len(steps)}-stage execution DAG for '{primary_asset}' ({software}).",
        )
