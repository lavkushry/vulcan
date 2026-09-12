"""
Project Vulcan: AgentOS Ultra Versioned Pydantic Schemas (Section 8)
Author: Architectural Review Board & AgentOS Core Team

Enforces:
1. Every agent communicates through versioned, validated Pydantic schemas.
2. Zero free-form model responses directly control state transitions.
3. Raw LLM responses are captured separately for diagnostics and audit.
"""
from __future__ import annotations

from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SchemaVersion(str, enum.Enum):
    V1_0 = "1.0"


class AgentRole(str, enum.Enum):
    SUPERVISOR = "supervisor"
    INTENT = "intent"
    CONTEXT = "context"
    DISCOVERY = "discovery"
    RISK = "risk"
    PLANNER = "planner"
    COMPOSER = "composer"
    BUILDER = "builder"
    RESOURCE = "resource"
    VALIDATOR = "validator"
    SECURITY = "security"
    CRITIC = "critic"
    TEST = "test"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    ROLLBACK = "rollback"
    CURATOR = "curator"
    EVAL = "eval"


class BaseAgentOutput(BaseModel):
    """Base envelope required for every structured agent proposal."""
    schema_version: SchemaVersion = SchemaVersion.V1_0
    agent: AgentRole
    workflow_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    proposed_next_state: str
    rationale: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# 1. Supervisor Output
class SupervisorOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.SUPERVISOR
    delegated_agent: AgentRole
    objective: str
    stop_and_wait_for_input: bool = False
    stop_and_wait_for_resource: bool = False


# 2. Intent Output
class IntentOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.INTENT
    desired_outcome: str
    automation_domain: str  # e.g., "database", "os_patching", "network", "cloud"
    known_parameters: Dict[str, Any] = Field(default_factory=dict)
    missing_parameters: List[str] = Field(default_factory=list)
    ambiguity_classification: str = "UNAMBIGUOUS"  # "UNAMBIGUOUS", "PARTIAL", "HIGHLY_AMBIGUOUS"
    requires_operator_input: bool = False
    clarification_prompt: Optional[str] = None


# 3. Context Output
class ContextOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.CONTEXT
    retrieved_catalog_items: List[Dict[str, Any]] = Field(default_factory=list)
    historical_failures: List[Dict[str, Any]] = Field(default_factory=list)
    applicable_policies: List[str] = Field(default_factory=list)
    cmdb_context: Dict[str, Any] = Field(default_factory=dict)


# 4. Discovery Output
class DiscoveryCandidate(BaseModel):
    identifier: str
    name: str
    source_type: str  # "catalog", "internal_git", "galaxy", "terraform_registry"
    source_uri: str
    version: str = "1.0.0"
    commit_sha: Optional[str] = None
    trust_state: str = "CANDIDATE"  # "CANDIDATE", "VERIFIED", "CURATED", "QUARANTINED", "REJECTED"
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    privilege_level: str = "standard"
    has_rollback: bool = True
    is_curated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiscoveryOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.DISCOVERY
    candidates: List[DiscoveryCandidate] = Field(default_factory=list)
    exact_catalog_match: bool = False
    total_found: int = 0


# 5. Risk Output
class RiskOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.RISK
    risk_tier: str = "MEDIUM"  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    destructive_potential: bool = False
    iam_impact: bool = False
    data_impact: bool = False
    network_impact: bool = False
    database_impact: bool = False
    blast_radius: str = "single_host"
    reversibility: str = "fully_reversible"
    requires_maker_checker: bool = True
    requires_change_ticket: bool = True


# 6. Planner Output
class PlannerDecision(str, enum.Enum):
    REUSE = "REUSE"
    COMPOSE = "COMPOSE"
    ADAPT = "ADAPT"
    GENERATE = "GENERATE"


class PlannerOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.PLANNER
    decision: PlannerDecision = PlannerDecision.COMPOSE
    selected_assets: List[str] = Field(default_factory=list)
    missing_capabilities: List[str] = Field(default_factory=list)
    execution_strategy: str = ""
    target_engine: str = "ansible"


# 7. Composer Output
class ExecutionStep(BaseModel):
    step_id: str
    name: str
    action_identifier: str
    engine: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    rollback_step_id: Optional[str] = None
    postconditions: List[str] = Field(default_factory=list)


class ComposerOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.COMPOSER
    dag_steps: List[ExecutionStep] = Field(default_factory=list)
    execution_graph: Dict[str, List[str]] = Field(default_factory=dict)
    rollback_dag: Dict[str, str] = Field(default_factory=dict)


# 8. Builder Output
class ArtifactFile(BaseModel):
    path: str
    content: str
    executable: bool = False


class BuilderOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.BUILDER
    engine: str = "ansible"
    artifact_id: str
    artifact_sha256: str
    spec_hash: str
    files: List[ArtifactFile] = Field(default_factory=list)
    test_files: List[ArtifactFile] = Field(default_factory=list)
    rollback_files: List[ArtifactFile] = Field(default_factory=list)
    postconditions: List[Dict[str, Any]] = Field(default_factory=list)


# 9. Resource Output
class RequiredResource(BaseModel):
    resource_type: str
    provider: str
    required: bool = True
    description: str = ""
    is_available: bool = False
    external_resource_id: Optional[str] = None
    secret_ref: Optional[str] = None


class ResourceOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.RESOURCE
    required_resources: List[RequiredResource] = Field(default_factory=list)
    missing_resources: List[str] = Field(default_factory=list)
    resolved_resources: Dict[str, Any] = Field(default_factory=dict)
    secret_references: List[str] = Field(default_factory=list)
    all_dependencies_satisfied: bool = True


# 10. Validator Output
class ValidationCheckStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValidationCheck(BaseModel):
    check_name: str
    status: ValidationCheckStatus
    details: str = ""
    evidence_ref: Optional[str] = None


class ValidatorOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.VALIDATOR
    all_passed: bool = False
    checks: List[ValidationCheck] = Field(default_factory=list)
    syntax_valid: bool = False
    lint_passed: bool = False
    idempotency_verified: bool = False
    sandbox_passed: bool = False


# 11. Security Output
class SecurityFinding(BaseModel):
    rule_id: str
    severity: str  # "INFO", "WARNING", "CRITICAL", "BLOCKER"
    title: str
    description: str
    file_path: Optional[str] = None
    line: Optional[int] = None


class SecurityOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.SECURITY
    verdict: str = "APPROVED"  # "APPROVED", "REJECTED"
    findings: List[SecurityFinding] = Field(default_factory=list)
    prompt_injection_detected: bool = False
    unauthorized_escalation_detected: bool = False
    secret_leak_detected: bool = False


# 11b. Test Output (Section 7: Test Agent)
class TestCaseResult(BaseModel):
    test_id: str
    name: str
    passed: bool
    details: str = ""
    duration_ms: float = 0.0


class TestOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.TEST
    all_passed: bool = False
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    test_cases: List[TestCaseResult] = Field(default_factory=list)


# 12. Critic Output
class CriticDefect(BaseModel):
    category: str  # "assumptions", "idempotency", "rollback", "target_selection", "ordering"
    severity: str  # "MINOR", "MAJOR", "FATAL"
    critique: str
    counter_example: str


class CriticOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.CRITIC
    verdict: str = "ACCEPTED"  # "ACCEPTED", "CHALLENGED"
    attacks_attempted: List[str] = Field(default_factory=list)
    defects_found: List[CriticDefect] = Field(default_factory=list)
    blocks_workflow: bool = False


# 13. Execution Capability Token
class ExecutionCapabilityToken(BaseModel):
    token_id: str
    workflow_id: str
    artifact_sha256: str
    parameter_hash: str
    target_resource_id: str
    environment: str = "PROD"
    approval_id: str
    policy_decision_id: str
    allowed_action: str = "EXECUTE"
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    is_used: bool = False
    used_at: Optional[datetime] = None


# 14. Verifier Output
class VerificationProbe(BaseModel):
    probe_id: str
    target: str
    probe_type: str  # e.g., "http_health", "port_check", "service_status", "db_query"
    passed: bool
    latency_ms: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)


class VerifierOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.VERIFIER
    all_passed: bool = False
    probes: List[VerificationProbe] = Field(default_factory=list)
    actual_state_matches_desired: bool = False


# 15. Rollback Output
class RollbackOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.ROLLBACK
    status: str = "SUCCESS"  # "SUCCESS", "FAILED"
    target: str
    rollback_artifact_sha: str
    stdout: str = ""
    exit_code: int = 0


# 16. Curator Output
class CuratorOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.CURATOR
    proposed_promotion: bool = False
    item_identifier: str
    promotion_tier: str = "CANDIDATE"  # "CANDIDATE", "VERIFIED", "CURATED"
    provenance: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


# 17. Eval Output
class EvalOutput(BaseAgentOutput):
    agent: AgentRole = AgentRole.EVAL
    eval_id: str
    tier: int = 0
    suite_name: str
    total_scenarios: int = 0
    passed_scenarios: int = 0
    pass_rate: float = 0.0
    bootstrap_ci_lower: Optional[float] = None
    bootstrap_ci_upper: Optional[float] = None
    gate_passed: bool = True
