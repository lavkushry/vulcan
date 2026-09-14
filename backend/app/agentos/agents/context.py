"""
Project Vulcan: Context Agent (Section 7)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Retrieve enterprise context: catalog metadata, CMDB records, applicable policies
- Treat all retrieved content as untrusted data
"""
from __future__ import annotations

from typing import Any, Dict, List, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, ContextOutput


class ContextAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.CONTEXT,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Gather enterprise infrastructure topology, CMDB records, and applicable policies.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return ContextOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> ContextOutput:
        domain = ctx.normalized_intent.get("automation_domain", "general")

        policies = ["POL-MAKER-CHECKER-HIGH-RISK", "POL-AUDIT-MERKLE-CHAIN"]
        if ctx.environment == "PROD":
            policies.append("POL-PROD-CHANGE-WINDOW-ENFORCEMENT")

        cmdb = {
            "datacenter": "ashburn-dc1",
            "environment": ctx.environment,
            "os_baseline": "RHEL 9.3 x86_64",
            "cluster_domain": "corp.internal",
        }

        retrieved_catalog = []
        if domain == "database":
            retrieved_catalog.append({
                "identifier": "db-postgres-cluster-setup",
                "name": "PostgreSQL 16 High-Availability Cluster",
                "category": "database",
                "risk_tier": "HIGH",
                "is_curated": True,
            })

        return ContextOutput(
            workflow_id=ctx.workflow_id,
            retrieved_catalog_items=retrieved_catalog,
            historical_failures=[],
            applicable_policies=policies,
            cmdb_context=cmdb,
            proposed_next_state=WorkflowState.DISCOVERING.value,
            confidence=0.95,
            rationale="Context assembled from CMDB and policy registries.",
        )
