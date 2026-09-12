"""
Project Vulcan: AgentOS Ultra Calibrated Confidence Engine (Section 10)
Author: Architectural Review Board & AgentOS Core Team

Fuses multi-signal scoring:
1. Raw model self-confidence
2. Retrieval score & top candidate margin
3. Catalog exact-match evidence
4. Cross-agent agreement
5. Historical agent accuracy
6. Deterministic validation outcomes
7. Evidence coverage score
"""
from __future__ import annotations

from dataclasses import dataclass, field
import enum
from typing import Any, Dict, List, Optional


class ConfidenceTier(str, enum.Enum):
    HIGH = "HIGH"          # Continue automatically
    MEDIUM = "MEDIUM"      # Trigger secondary verification / critic inspection
    LOW = "LOW"            # Halt in WAITING_FOR_INPUT


@dataclass
class ConfidenceAssessment:
    calibrated_score: float  # 0.0 to 1.0
    tier: ConfidenceTier
    component_scores: Dict[str, float]
    rationale: str
    requires_clarification: bool = False
    requires_secondary_verification: bool = False


class ConfidenceEngine:
    """
    Calibrates decision confidence using multi-factor Bayesian-weighted fusion.
    Prevents model hallucination overconfidence from triggering unverified automation.
    """

    DEFAULT_HIGH_THRESHOLD = 0.85
    DEFAULT_MEDIUM_THRESHOLD = 0.65
    PROD_HIGH_THRESHOLD = 0.88
    PROD_MEDIUM_THRESHOLD = 0.70

    @classmethod
    def calculate_confidence(
        cls,
        model_confidence: float = 0.80,
        retrieval_score: float = 0.80,
        top_candidate_margin: float = 0.20,
        has_catalog_exact_match: bool = False,
        cross_agent_agreement: float = 1.0,
        historical_accuracy: float = 0.95,
        deterministic_validation_passed: bool = True,
        evidence_coverage: float = 0.85,
        environment: str = "PROD",
        high_threshold: Optional[float] = None,
        medium_threshold: Optional[float] = None,
    ) -> ConfidenceAssessment:
        """Computes calibrated confidence score and assigns progression tier."""
        # Clamp inputs
        m_conf = max(0.0, min(1.0, float(model_confidence)))
        r_score = max(0.0, min(1.0, float(retrieval_score)))
        margin = max(0.0, min(1.0, float(top_candidate_margin)))
        exact_bonus = 1.0 if has_catalog_exact_match else 0.0
        agreement = max(0.0, min(1.0, float(cross_agent_agreement)))
        hist_acc = max(0.0, min(1.0, float(historical_accuracy)))
        det_val = 1.0 if deterministic_validation_passed else 0.0
        e_cov = max(0.0, min(1.0, float(evidence_coverage)))

        # Weighted composition:
        # Deterministic checks & exact matches have heavy weight
        weights = {
            "model_confidence": 0.10,
            "retrieval_score": 0.15,
            "top_candidate_margin": 0.10,
            "catalog_exact_match": 0.15,
            "cross_agent_agreement": 0.15,
            "historical_accuracy": 0.10,
            "deterministic_validation": 0.15,
            "evidence_coverage": 0.10,
        }

        calibrated = (
            m_conf * weights["model_confidence"]
            + r_score * weights["retrieval_score"]
            + margin * weights["top_candidate_margin"]
            + exact_bonus * weights["catalog_exact_match"]
            + agreement * weights["cross_agent_agreement"]
            + hist_acc * weights["historical_accuracy"]
            + det_val * weights["deterministic_validation"]
            + e_cov * weights["evidence_coverage"]
        )
        calibrated = round(max(0.0, min(1.0, calibrated)), 4)

        is_prod = (environment.upper() == "PROD")
        high_t = high_threshold or (cls.PROD_HIGH_THRESHOLD if is_prod else cls.DEFAULT_HIGH_THRESHOLD)
        med_t = medium_threshold or (cls.PROD_MEDIUM_THRESHOLD if is_prod else cls.DEFAULT_MEDIUM_THRESHOLD)

        if not deterministic_validation_passed:
            tier = ConfidenceTier.LOW
            rationale = "Deterministic validation failed; forced to LOW confidence."
        elif calibrated >= high_t:
            tier = ConfidenceTier.HIGH
            rationale = f"Calibrated score {calibrated:.2f} >= high threshold {high_t:.2f}."
        elif calibrated >= med_t:
            tier = ConfidenceTier.MEDIUM
            rationale = f"Calibrated score {calibrated:.2f} in medium range [{med_t:.2f}, {high_t:.2f})."
        else:
            tier = ConfidenceTier.LOW
            rationale = f"Calibrated score {calibrated:.2f} < medium threshold {med_t:.2f}."

        return ConfidenceAssessment(
            calibrated_score=calibrated,
            tier=tier,
            component_scores={
                "model_confidence": m_conf,
                "retrieval_score": r_score,
                "top_candidate_margin": margin,
                "catalog_exact_match": exact_bonus,
                "cross_agent_agreement": agreement,
                "historical_accuracy": hist_acc,
                "deterministic_validation": det_val,
                "evidence_coverage": e_cov,
            },
            rationale=rationale,
            requires_clarification=(tier == ConfidenceTier.LOW),
            requires_secondary_verification=(tier == ConfidenceTier.MEDIUM),
        )
