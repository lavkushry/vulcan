"""
Project Vulcan: AgentOS Ultra Evidence Engine (Section 9)
Author: Architectural Review Board & AgentOS Core Team

Enforces:
1. Every material agent conclusion must be supported by verifiable Evidence.
2. Decisions lacking sufficient evidence fail closed.
3. Cryptographic fingerprints ensure evidence immutability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class EvidenceType(str, enum.Enum):
    CATALOG_ARTIFACT = "catalog_artifact"
    CATALOG_SHA = "catalog_sha"
    REGISTRY_URL = "registry_url"
    MODULE_VERSION = "module_version"
    DOCUMENTATION_REF = "documentation_reference"
    CMDB_RECORD = "cmdb_record"
    SERVICENOW_TICKET = "servicenow_ticket"
    POLICY_RESULT = "policy_result"
    TEST_RESULT = "test_result"
    SANDBOX_RESULT = "sandbox_result"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    MODEL_CONFIDENCE = "model_confidence"
    DETERMINISTIC_MATCHER = "deterministic_matcher_result"
    POSTCONDITION_RESULT = "postcondition_result"
    HISTORICAL_EXECUTION = "historical_execution"


@dataclass(frozen=True)
class Evidence:
    """Immutable evidence unit supporting an agent proposition or decision."""
    evidence_id: str
    evidence_type: EvidenceType
    source_uri: str
    summary: str
    confidence_weight: float = 1.0  # 0.0 to 1.0
    fingerprint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.fingerprint:
            raw = f"{self.evidence_type.value}:{self.source_uri}:{json.dumps(self.metadata, sort_keys=True, default=str)}"
            fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "fingerprint", fp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value if isinstance(self.evidence_type, EvidenceType) else str(self.evidence_type),
            "source_uri": self.source_uri,
            "summary": self.summary,
            "confidence_weight": self.confidence_weight,
            "fingerprint": self.fingerprint,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Evidence:
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif not ts:
            ts = datetime.now(timezone.utc)
        return cls(
            evidence_id=data["evidence_id"],
            evidence_type=EvidenceType(data["evidence_type"]),
            source_uri=data["source_uri"],
            summary=data["summary"],
            confidence_weight=float(data.get("confidence_weight", 1.0)),
            fingerprint=data.get("fingerprint", ""),
            metadata=data.get("metadata", {}),
            timestamp=ts,
        )


class EvidenceEngine:
    """
    Evaluates evidence sufficiency across pipeline stages.
    Enforces that high-risk conclusions fail closed if ungrounded.
    """

    @classmethod
    def evaluate_coverage(
        cls,
        evidence_list: List[Evidence],
        required_types: Optional[List[EvidenceType]] = None,
        min_weight: float = 0.70,
    ) -> Dict[str, Any]:
        """Calculates evidence completeness and weight score."""
        if not evidence_list:
            return {
                "adequate": False,
                "coverage_score": 0.0,
                "missing_types": [t.value for t in (required_types or [])],
                "reason": "Zero evidence items provided.",
            }

        present_types = {e.evidence_type for e in evidence_list}
        missing = []
        if required_types:
            for rt in required_types:
                if rt not in present_types:
                    missing.append(rt.value)

        total_weight = sum(min(max(e.confidence_weight, 0.0), 1.0) for e in evidence_list)
        avg_weight = total_weight / len(evidence_list)
        adequate = (len(missing) == 0) and (avg_weight >= min_weight)

        return {
            "adequate": adequate,
            "coverage_score": round(avg_weight, 4),
            "evidence_count": len(evidence_list),
            "missing_types": missing,
            "reason": "Evidence satisfies sufficiency threshold" if adequate else f"Missing required evidence types: {missing}" if missing else f"Average weight {avg_weight:.2f} below threshold {min_weight:.2f}",
        }
