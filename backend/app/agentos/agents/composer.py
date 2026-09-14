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
        steps = [
            ExecutionStep(
                step_id="step-1",
                name="1. Validate Environment & Prerequisites",
                action_identifier="core-preflight-check",
                engine="ansible",
                parameters={"platform": "rhel9", "min_disk_gb": 500},
                depends_on=[],
                rollback_step_id=None,
                postconditions=["disk_space_ok", "os_supported"],
            ),
            ExecutionStep(
                step_id="step-2",
                name="2. Provision & Configure Primary PostgreSQL 16 Cluster",
                action_identifier="vulcan.database.postgresql_cluster",
                engine="ansible",
                parameters={"nodes": 3, "port": 5432, "storage_gb": 500},
                depends_on=["step-1"],
                rollback_step_id="step-rollback",
                postconditions=["port_5432_reachable", "service_postgresql_active"],
            ),
            ExecutionStep(
                step_id="step-3",
                name="3. Attach Datadog APM & Host Telemetry",
                action_identifier="datadog-agent-install",
                engine="ansible",
                parameters={"integrations": ["postgres"]},
                depends_on=["step-2"],
                rollback_step_id="step-rollback",
                postconditions=["datadog_metrics_flowing"],
            ),
            ExecutionStep(
                step_id="step-4",
                name="4. Configure S3 Automated Backup Target",
                action_identifier="s3-pg-backup-config",
                engine="ansible",
                parameters={"bucket_policy": "encrypted"},
                depends_on=["step-2"],
                rollback_step_id="step-rollback",
                postconditions=["s3_backup_job_verified"],
            ),
        ]

        dag = {
            "step-1": [],
            "step-2": ["step-1"],
            "step-3": ["step-2"],
            "step-4": ["step-2"],
        }
        rollback_dag = {
            "step-2": "step-rollback",
            "step-3": "step-rollback",
            "step-4": "step-rollback",
        }

        return ComposerOutput(
            workflow_id=ctx.workflow_id,
            dag_steps=steps,
            execution_graph=dag,
            rollback_dag=rollback_dag,
            proposed_next_state=WorkflowState.RESOLVING_RESOURCES.value,
            confidence=0.98,
            rationale=f"Composed 4-stage execution DAG with explicit rollback mapping.",
        )
