"""
Project Vulcan: Risk Agent (Section 7 & 26)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Deterministic operational risk classification
- Blast radius and reversibility analysis
- Maker-checker and change ticket requirement enforcement
- Rule-based authority: deterministic rules strictly override model opinion
"""
from __future__ import annotations

from typing import Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, RiskOutput


class RiskAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.RISK,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Evaluate operational blast radius, data impact, and governance gating requirements.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return RiskOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> RiskOutput:
        req = ctx.original_request.lower()
        domain = ctx.normalized_intent.get("automation_domain", "general")
        env = ctx.environment.upper()

        # Deterministic Rules (Section 7)
        is_database = (domain == "database" or "database" in req or "postgres" in req or "sql" in req)
        is_destructive = any(w in req for w in ("drop", "delete", "destroy", "reformat", "truncate", "wipe"))
        is_iam = any(w in req for w in ("iam", "role", "policy", "sudo", "privilege", "cyberark", "vault"))
        is_network = any(w in req for w in ("f5", "vip", "route", "firewall", "iptables", "dns"))

        # Risk Tier derivation
        if is_destructive or (is_database and env == "PROD"):
            risk_tier = "HIGH" if not is_destructive else "CRITICAL"
            blast_radius = "multi_host_cluster" if is_database else "datacenter"
            requires_mc = True
            requires_chg = True
        elif env == "PROD" or is_iam or is_network:
            risk_tier = "HIGH"
            blast_radius = "service_wide"
            requires_mc = True
            requires_chg = True
        elif is_database:
            risk_tier = "MEDIUM"
            blast_radius = "isolated_database"
            requires_mc = False
            requires_chg = False
        else:
            risk_tier = "LOW"
            blast_radius = "single_host"
            requires_mc = False
            requires_chg = False

        return RiskOutput(
            workflow_id=ctx.workflow_id,
            risk_tier=risk_tier,
            destructive_potential=is_destructive,
            iam_impact=is_iam,
            data_impact=is_database,
            network_impact=is_network,
            database_impact=is_database,
            blast_radius=blast_radius,
            reversibility="automated_rollback" if not is_destructive else "irreversible_data_loss",
            requires_maker_checker=requires_mc,
            requires_change_ticket=requires_chg,
            proposed_next_state=WorkflowState.PLANNING.value,
            confidence=1.0,
            rationale=f"Assigned {risk_tier} based on environment={env}, database={is_database}, destructive={is_destructive}.",
        )
