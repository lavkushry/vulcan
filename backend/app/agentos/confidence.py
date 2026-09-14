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


from datetime import datetime, timezone
from pydantic import BaseModel, Field


class CalibrationRecord(BaseModel):
    """
    Tracks predicted confidence vs actual execution outcome for future threshold calibration.
    """
    workflow_id: str
    predicted_confidence: float = Field(ge=0.0, le=1.0)
    predicted_tier: ConfidenceTier
    actual_outcome: str  # e.g., "SUCCESS", "FAILED", "VERIFY_FAILED"
    actual_success: bool
    unknown_signals: List[str] = Field(default_factory=list)
    component_scores: Dict[str, float] = Field(default_factory=dict)
    environment: str = "PROD"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConfidenceAssessment:
    calibrated_score: float  # 0.0 to 1.0
    tier: ConfidenceTier
    component_scores: Dict[str, float]
    rationale: str
    requires_clarification: bool = False
    requires_secondary_verification: bool = False
    unknown_signals: List[str] = field(default_factory=list)
    max_achievable_score: float = 1.0


class ConfidenceEngine:
    """
    Calibrates decision confidence using multi-factor Bayesian-weighted fusion.
    Treats missing evidence as unknown (None), reducing maximum achievable score.
    Prevents model hallucination overconfidence from triggering unverified automation.
    Failed authorization, verification, or deterministic checks force ConfidenceTier.LOW.
    """

    DEFAULT_HIGH_THRESHOLD = 0.85
    DEFAULT_MEDIUM_THRESHOLD = 0.65
    PROD_HIGH_THRESHOLD = 0.88
    PROD_MEDIUM_THRESHOLD = 0.70

    @classmethod
    def calculate_confidence(
        cls,
        model_confidence: Optional[float] = None,
        retrieval_score: Optional[float] = None,
        top_candidate_margin: Optional[float] = None,
        has_catalog_exact_match: Optional[bool] = None,
        cross_agent_agreement: Optional[float] = None,
        historical_accuracy: Optional[float] = None,
        deterministic_validation_passed: Optional[bool] = None,
        evidence_coverage: Optional[float] = None,
        authorization_passed: Optional[bool] = None,
        verification_passed: Optional[bool] = None,
        environment: str = "PROD",
        high_threshold: Optional[float] = None,
        medium_threshold: Optional[float] = None,
    ) -> ConfidenceAssessment:
        """
        Computes calibrated confidence score and assigns progression tier.
        Missing signals (None) are excluded from positive contribution and reduce max achievable score.
        """
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

        raw_signals = {
            "model_confidence": model_confidence,
            "retrieval_score": retrieval_score,
            "top_candidate_margin": top_candidate_margin,
            "catalog_exact_match": (1.0 if has_catalog_exact_match else 0.0) if has_catalog_exact_match is not None else None,
            "cross_agent_agreement": cross_agent_agreement,
            "historical_accuracy": historical_accuracy,
            "deterministic_validation": (1.0 if deterministic_validation_passed else 0.0) if deterministic_validation_passed is not None else None,
            "evidence_coverage": evidence_coverage,
        }

        unknown_signals: List[str] = []
        component_scores: Dict[str, float] = {}
        weighted_sum = 0.0
        known_weight_sum = 0.0

        for name, val in raw_signals.items():
            if val is None:
                unknown_signals.append(name)
            else:
                clamped = max(0.0, min(1.0, float(val)))
                component_scores[name] = clamped
                weighted_sum += clamped * weights[name]
                known_weight_sum += weights[name]

        max_achievable = round(known_weight_sum, 4)
        calibrated = round(max(0.0, min(max_achievable, weighted_sum)), 4)

        # Invariant: Failed authorization, verification, or deterministic validation MUST force LOW tier
        forced_low = False
        forced_reason = ""
        if authorization_passed is False:
            forced_low = True
            forced_reason = "Authorization failed; forced to LOW confidence."
        elif verification_passed is False:
            forced_low = True
            forced_reason = "Verification failed; forced to LOW confidence."
        elif deterministic_validation_passed is False:
            forced_low = True
            forced_reason = "Deterministic validation failed; forced to LOW confidence."

        is_prod = (environment.upper() == "PROD")
        high_t = high_threshold or (cls.PROD_HIGH_THRESHOLD if is_prod else cls.DEFAULT_HIGH_THRESHOLD)
        med_t = medium_threshold or (cls.PROD_MEDIUM_THRESHOLD if is_prod else cls.DEFAULT_MEDIUM_THRESHOLD)

        if forced_low:
            tier = ConfidenceTier.LOW
            rationale = forced_reason
        elif calibrated >= high_t:
            tier = ConfidenceTier.HIGH
            rationale = f"Calibrated score {calibrated:.2f} >= high threshold {high_t:.2f} (max achievable {max_achievable:.2f})."
        elif calibrated >= med_t:
            tier = ConfidenceTier.MEDIUM
            rationale = f"Calibrated score {calibrated:.2f} in medium range [{med_t:.2f}, {high_t:.2f}) (max achievable {max_achievable:.2f})."
        else:
            tier = ConfidenceTier.LOW
            rationale = f"Calibrated score {calibrated:.2f} < medium threshold {med_t:.2f} (unknown signals: {len(unknown_signals)})."

        return ConfidenceAssessment(
            calibrated_score=calibrated,
            tier=tier,
            component_scores=component_scores,
            rationale=rationale,
            requires_clarification=(tier == ConfidenceTier.LOW),
            requires_secondary_verification=(tier == ConfidenceTier.MEDIUM),
            unknown_signals=unknown_signals,
            max_achievable_score=max_achievable,
        )
