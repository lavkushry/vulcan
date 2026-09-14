"""
Project Vulcan: Evaluation Platform Scenarios and Reporting Models
"""
from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScenarioGroup(str, enum.Enum):
    SUPPORTED_PARAPHRASE = "supported_tasks_and_paraphrases"
    AMBIGUITY = "missing_information_and_ambiguity"
    SECURITY_PERMISSIONS = "permissions_and_malicious_instructions"
    TOOL_FAILURES = "tool_failures_and_timeouts"
    ROLLBACK_RECOVERY = "rollback_and_restart_recovery"


class EvalScenario(BaseModel):
    id: str
    group: ScenarioGroup
    name: str
    description: str
    request: str
    requester_id: str = "operator-alice@corp.internal"
    environment: str = "PROD"
    approver_id: Optional[str] = "secops-bob@corp.internal"
    expected_terminal_state: str
    assertions: List[str] = Field(default_factory=list)
    setup_kwargs: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScenarioExecutionResult(BaseModel):
    scenario_id: str
    group: str
    name: str
    passed: bool
    expected_terminal_state: str
    actual_terminal_state: str
    postconditions_verified: bool
    is_false_success: bool
    unauthorized_action_detected: bool
    latency_ms: float
    events_count: int
    error: Optional[str] = None
    assertions_passed: List[str] = Field(default_factory=list)
    assertions_failed: List[str] = Field(default_factory=list)


class EvalReport(BaseModel):
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    verified_completion_rate: float
    false_success_rate: float
    unauthorized_actions_count: int
    p95_latency_ms: float
    avg_latency_ms: float
    cost_per_verified_success_usd: float
    group_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    results: List[ScenarioExecutionResult] = Field(default_factory=list)
    evaluation_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
