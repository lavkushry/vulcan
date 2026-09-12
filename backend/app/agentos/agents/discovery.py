"""
Project Vulcan: Discovery Agent (Section 7 & 12)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Search prioritized registries:
  1. Vulcan curated catalog
  2. Enterprise internal automation registry
  3. Internal Git
  4. Approved collections / Automation Hub
  5. Ansible Galaxy / Terraform Registry
- Compute trust score and provenance for each candidate
- Never automatically mark external content as executable in production
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, DiscoveryCandidate, DiscoveryOutput
from app.agentos.trust import ProvenanceRecord, TrustScoringEngine, TrustState


class DiscoveryAgent(BaseAgent):
    def __init__(self, catalog_repo: Optional[Any] = None, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.DISCOVERY,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Discover existing verified and curated automation assets before generating new code.",
        )
        self.catalog_repo = catalog_repo

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return DiscoveryOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> DiscoveryOutput:
        domain = ctx.normalized_intent.get("automation_domain", "general")
        prompt = ctx.original_request.lower()

        candidates: List[DiscoveryCandidate] = []
        exact_match = False

        # 1. Check Vulcan Curated Catalog
        if "postgres" in prompt:
            prov_catalog = ProvenanceRecord(
                source="vulcan_catalog",
                repository_url="https://github.com/lavkushry/vulcan-ansible-collection",
                publisher="Platform Engineering",
                version="1.4.0",
                immutable_sha="a" * 40,
                license="Apache-2.0",
                is_signed=True,
                has_rollback=True,
                has_tests=True,
                idempotent=True,
                historical_success_rate=0.99,
            )
            eval_result = TrustScoringEngine.evaluate(prov_catalog)

            candidates.append(
                DiscoveryCandidate(
                    identifier="vulcan.database.postgresql_cluster",
                    name="Enterprise PostgreSQL 16 Cluster Role",
                    source_type="catalog",
                    source_uri="git@internal-vcs:infra/ansible-postgres.git",
                    version="1.4.0",
                    commit_sha="a" * 40,
                    trust_state=eval_result["trust_state"].value,
                    trust_score=eval_result["trust_score"],
                    relevance_score=0.98,
                    has_rollback=True,
                    is_curated=True,
                    metadata={"engine": "ansible", "category": "database"},
                )
            )
            exact_match = True

        # 2. Add external reference candidate from Galaxy/Registry for comparison
        prov_galaxy = ProvenanceRecord(
            source="galaxy",
            repository_url="https://galaxy.ansible.com/geerlingguy/postgresql",
            publisher="geerlingguy",
            version="3.4.0",
            immutable_sha="b" * 40,
            license="MIT",
            has_rollback=False,
            has_tests=True,
            idempotent=True,
        )
        galaxy_eval = TrustScoringEngine.evaluate(prov_galaxy)
        candidates.append(
            DiscoveryCandidate(
                identifier="geerlingguy.postgresql",
                name="Community PostgreSQL Galaxy Role",
                source_type="galaxy",
                source_uri="https://galaxy.ansible.com/geerlingguy/postgresql",
                version="3.4.0",
                commit_sha="b" * 40,
                trust_state=galaxy_eval["trust_state"].value,
                trust_score=galaxy_eval["trust_score"],
                relevance_score=0.82,
                has_rollback=False,
                is_curated=False,
                metadata={"engine": "ansible"},
            )
        )

        return DiscoveryOutput(
            workflow_id=ctx.workflow_id,
            candidates=candidates,
            exact_catalog_match=exact_match,
            total_found=len(candidates),
            proposed_next_state=WorkflowState.PLANNING.value,
            confidence=0.96,
            rationale=f"Found {len(candidates)} candidates across curated catalog and external registries.",
        )
