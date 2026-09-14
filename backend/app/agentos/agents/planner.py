"""
Project Vulcan: Planner Agent (Section 7 & AGENT-04)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Formulate automation strategy prioritizing existing trusted automation:
  Retrieve -> Compose -> Adapt -> Generate
- Generation is strictly the last resort
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, ExecutionMode, PlannerDecision, PlannerOutput, RejectedCandidate
from app.agentos.confidence import ConfidenceEngine


class PlannerAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.PLANNER,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Formulate execution strategy enforcing Retrieve -> Compose -> Adapt -> Generate precedence.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return PlannerOutput

    def _score_candidate(self, candidate: Dict[str, Any], ctx: WorkflowContext) -> Tuple[Optional[float], Optional[str]]:
        """
        Scores a candidate asset across 4 dimensions:
        1. Capability Match (0.35)
        2. Trust State & Security (0.25)
        3. Platform Version Compatibility (0.20)
        4. Rollback Compatibility (0.20)

        Returns (score, None) if candidate is viable, or (None, rejection_reason) if rejected.
        """
        identifier = candidate.get("identifier", "")
        trust_state = str(candidate.get("trust_state", "CANDIDATE")).upper()

        # 1. Hard rejection gates: Untrusted or Quarantined
        if trust_state in ("REJECTED", "QUARANTINED"):
            return None, f"Asset trust state is {trust_state}; blocked by security policy."

        # 2. Rollback compatibility
        is_curated = bool(candidate.get("is_curated") or trust_state == "CURATED")
        has_rollback = candidate.get("has_rollback")
        if has_rollback is None and is_curated:
            has_rollback = True

        is_prod = ctx.environment.upper() == "PROD"
        if has_rollback is False and is_prod:
            return None, "Candidate lacks rollback support required for PROD environment."
        if has_rollback is None and is_prod:
            return None, "Candidate lacks verified rollback support required for PROD environment."

        rollback_score = 1.0 if has_rollback is True else (0.5 if has_rollback is None else 0.0)

        # 3. Trust Score
        raw_trust = float(candidate.get("trust_score", 0.8 if is_curated else 0.5))
        trust_component = 1.0 if is_curated else min(1.0, max(0.0, raw_trust))

        # 4. Capability Match
        relevance = float(candidate.get("relevance_score", 0.7 if is_curated else 0.5))
        req_lower = ctx.original_request.lower()
        ident_lower = identifier.lower()
        name_lower = str(candidate.get("name", "")).lower()

        capability_score = relevance
        keywords = ["postgres", "postgresql", "redis", "mysql", "mongodb", "docker", "nginx", "jenkins", "gitlab", "ssl", "f5", "tablespace", "rhel", "patch", "vpc", "aws"]
        matches = [kw for kw in keywords if kw in req_lower and (kw in ident_lower or kw in name_lower)]
        if matches:
            capability_score = min(1.0, capability_score + 0.2)

        # 5. Platform Version Compatibility
        version_score = 0.8
        metadata = candidate.get("metadata", {})
        cand_version = str(candidate.get("version", "")).lower()
        req_versions = re.findall(r'\b\d+(?:\.\d+)?\b', req_lower)
        if req_versions:
            target_v = req_versions[0]
            if target_v in ident_lower or target_v in cand_version or target_v in str(metadata):
                version_score = 1.0
            elif any(f"version_{v}" in ident_lower or f"postgres_{v}" in ident_lower for v in ["12", "13", "14", "15", "16"] if v != target_v):
                return None, f"Incompatible platform version: candidate is for different major version than requested {target_v}."

        # 5b. OS Platform Compatibility
        requested_os = ctx.normalized_intent.get("known_parameters", {}).get("os_platform") if isinstance(ctx.normalized_intent, dict) else None
        if requested_os:
            from app.agentos.artifacts.resolver import ArtifactResolver
            supported_platforms = metadata.get("supported_platforms", [])
            if not supported_platforms:
                resolver = ArtifactResolver()
                try:
                    resolved = resolver.resolve_and_download(identifier, requested_os=requested_os)
                    supported_platforms = resolved.interface.supported_platforms
                except Exception:
                    pass
            if supported_platforms and not ArtifactResolver.is_os_compatible(requested_os, supported_platforms):
                return None, f"Incompatible OS platform: candidate does not support requested OS '{requested_os}'."

        # 6. Historical Success Evidence
        historical_failures = getattr(ctx, "context_retrieval", {}).get("historical_failures", []) if hasattr(ctx, "context_retrieval") and isinstance(ctx.context_retrieval, dict) else []
        if any(hf.get("identifier") == identifier for hf in historical_failures):
            return None, f"Asset '{identifier}' recorded in historical failure ledger; rejected until recertified."

        total_score = (
            0.35 * capability_score
            + 0.25 * trust_component
            + 0.20 * version_score
            + 0.20 * rollback_score
        )
        if is_curated:
            total_score = min(1.0, total_score + 0.1)

        return round(total_score, 3), None

    def execute(self, ctx: WorkflowContext, **kwargs) -> PlannerOutput:
        discovered = ctx.discovered_assets or []
        rejected_candidates: List[RejectedCandidate] = []
        ranked_candidates: List[Dict[str, Any]] = []

        for candidate in discovered:
            score, rejection_reason = self._score_candidate(candidate, ctx)
            ident = candidate.get("identifier", "unknown")
            if score is None:
                rejected_candidates.append(
                    RejectedCandidate(
                        identifier=ident,
                        reason=rejection_reason or "Failed scoring criteria",
                        score=0.0,
                        trust_state=candidate.get("trust_state"),
                    )
                )
            else:
                cand_entry = dict(candidate)
                cand_entry["composite_score"] = score
                ranked_candidates.append(cand_entry)

        # Sort ranked candidates by score descending
        ranked_candidates.sort(key=lambda c: c["composite_score"], reverse=True)

        if ranked_candidates:
            top = ranked_candidates[0]
            selected = [top.get("identifier")]
            top_score = top["composite_score"]
            is_curated = bool(top.get("is_curated") or top.get("trust_state") == "CURATED")

            for alt in ranked_candidates[1:]:
                rejected_candidates.append(
                    RejectedCandidate(
                        identifier=alt.get("identifier", ""),
                        reason=f"Ranked lower than top candidate '{selected[0]}' (score {alt['composite_score']:.2f} vs {top_score:.2f})",
                        score=alt["composite_score"],
                        trust_state=alt.get("trust_state"),
                    )
                )

            if is_curated and top_score >= 0.75:
                decision = PlannerDecision.COMPOSE
                missing = []
                strategy = f"Compose workflow leveraging trusted curated asset '{selected[0]}'."
                next_state = WorkflowState.COMPOSING.value
            else:
                decision = PlannerDecision.ADAPT
                missing = ["enterprise_hardening", "rollback_playbook"]
                strategy = f"Adapt candidate '{selected[0]}' by injecting enterprise hardening and rollback."
                next_state = WorkflowState.GENERATING.value

            second_score = ranked_candidates[1]["composite_score"] if len(ranked_candidates) > 1 else (top_score - 0.2 if is_curated else 0.0)
            margin = max(0.0, top_score - second_score)

            assessment = ConfidenceEngine.calculate_confidence(
                model_confidence=0.88 if is_curated else 0.70,
                retrieval_score=top_score,
                top_candidate_margin=margin,
                has_catalog_exact_match=is_curated,
                cross_agent_agreement=1.0 if is_curated else 0.75,
                historical_accuracy=0.96 if is_curated else 0.80,
                deterministic_validation_passed=True,
                evidence_coverage=0.92 if is_curated else 0.60,
                environment=ctx.environment,
            )
            confidence = assessment.calibrated_score
        else:
            selected = []
            decision = PlannerDecision.GENERATE
            missing = ["entire_automation_stack"]
            strategy = "Generate complete automation package from desired state specification."
            next_state = WorkflowState.GENERATING.value

            assessment = ConfidenceEngine.calculate_confidence(
                model_confidence=0.50,
                retrieval_score=0.10,
                top_candidate_margin=0.0,
                has_catalog_exact_match=False,
                cross_agent_agreement=0.50,
                historical_accuracy=0.50,
                deterministic_validation_passed=True,
                evidence_coverage=0.20,
                environment=ctx.environment,
            )
            confidence = min(0.68, assessment.calibrated_score)

        engine = "ansible"
        if "terraform" in ctx.original_request.lower():
            engine = "terraform"

        return PlannerOutput(
            workflow_id=ctx.workflow_id,
            decision=decision,
            selected_assets=selected,
            missing_capabilities=missing,
            execution_strategy=strategy,
            target_engine=engine,
            proposed_next_state=next_state,
            rejected_candidates=rejected_candidates,
            candidate_rankings=[{"identifier": c["identifier"], "score": c["composite_score"]} for c in ranked_candidates],
            confidence=confidence,
            execution_mode=ExecutionMode.SIMULATED,
            rationale=f"Strategy '{decision.value}' selected. Ranked {len(ranked_candidates)} candidates, rejected {len(rejected_candidates)}.",
        )
