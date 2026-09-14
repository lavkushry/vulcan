"""
Project Vulcan: AutomationSpecification & ResourceContract (Section 13 & 19)
Author: Architectural Review Board & AgentOS Core Team

Intermediate Representation (IR) decoupling natural language intent
from concrete infrastructure implementations (Ansible / Terraform / OpenTofu).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional


@dataclass
class ResourceDependency:
    """Explicit dependency declaration within a ResourceContract."""
    resource_type: str  # "inventory", "credentials", "itsm", "monitoring", "storage", "cloud"
    provider: str       # "cyberark", "servicenow", "datadog", "s3", "azure", "aws", "gcp"
    required: bool = True
    description: str = ""
    config_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "provider": self.provider,
            "required": self.required,
            "description": self.description,
            "config_schema": self.config_schema,
        }


@dataclass
class ResourceContract:
    """Binds all external resource dependencies required before execution."""
    dependencies: Dict[str, ResourceDependency] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in self.dependencies.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ResourceContract:
        deps = {}
        for k, v in data.items():
            deps[k] = ResourceDependency(
                resource_type=v.get("resource_type", "generic"),
                provider=v.get("provider", "generic"),
                required=v.get("required", True),
                description=v.get("description", ""),
                config_schema=v.get("config_schema", {}),
            )
        return cls(dependencies=deps)


@dataclass
class PostconditionProbeDef:
    """Read-only verification probe testing desired state independently of execution exit code."""
    probe_id: str
    target: str
    probe_type: str  # "port_open", "http_200", "service_active", "db_query", "telemetry_present"
    expected_value: Any
    retries: int = 3
    timeout_sec: float = 5.0
    independent_channel: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "target": self.target,
            "probe_type": self.probe_type,
            "expected_value": self.expected_value,
            "retries": self.retries,
            "timeout_sec": self.timeout_sec,
            "independent_channel": self.independent_channel,
        }


@dataclass
class AutomationSpecification:
    """
    Intermediate Representation (IR) specification for Governed Infrastructure Automation.
    Guarantees reproducibility, versioning, and compilation to target engines.
    """
    spec_id: str
    goal: str
    engine: str  # "ansible" or "terraform"
    supported_platforms: List[str]
    desired_state: Dict[str, Any]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    dependencies: List[str]
    resource_contract: ResourceContract
    execution_dag: List[Dict[str, Any]]
    risk_level: str = "MEDIUM"
    policy_requirements: List[str] = field(default_factory=list)
    idempotency_requirements: List[str] = field(default_factory=list)
    rollback_requirements: Dict[str, Any] = field(default_factory=dict)
    postconditions: List[PostconditionProbeDef] = field(default_factory=list)
    failure_handling: Dict[str, Any] = field(default_factory=dict)
    observability_requirements: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def compute_hash(self) -> str:
        """Deterministic canonical hash of specification."""
        payload = {
            "goal": self.goal,
            "engine": self.engine,
            "supported_platforms": sorted(self.supported_platforms),
            "desired_state": self.desired_state,
            "input_schema": self.input_schema,
            "dependencies": sorted(self.dependencies),
            "resource_contract": self.resource_contract.to_dict(),
            "execution_dag": self.execution_dag,
            "risk_level": self.risk_level,
            "rollback_requirements": self.rollback_requirements,
            "postconditions": [p.to_dict() for p in self.postconditions],
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "goal": self.goal,
            "engine": self.engine,
            "supported_platforms": self.supported_platforms,
            "desired_state": self.desired_state,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "dependencies": self.dependencies,
            "resource_contract": self.resource_contract.to_dict(),
            "execution_dag": self.execution_dag,
            "risk_level": self.risk_level,
            "policy_requirements": self.policy_requirements,
            "idempotency_requirements": self.idempotency_requirements,
            "rollback_requirements": self.rollback_requirements,
            "postconditions": [p.to_dict() for p in self.postconditions],
            "failure_handling": self.failure_handling,
            "observability_requirements": self.observability_requirements,
            "spec_hash": self.compute_hash(),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AutomationSpecification:
        contract_data = data.get("resource_contract", {})
        res_contract = ResourceContract.from_dict(contract_data) if isinstance(contract_data, dict) else ResourceContract()
        probes = [
            PostconditionProbeDef(
                probe_id=p.get("probe_id", f"p-{i}"),
                target=p.get("target", "localhost"),
                probe_type=p.get("probe_type", "port_open"),
                expected_value=p.get("expected_value", True),
                retries=p.get("retries", 3),
                timeout_sec=p.get("timeout_sec", 5.0),
                independent_channel=p.get("independent_channel", True),
            )
            for i, p in enumerate(data.get("postconditions", []))
        ]
        return cls(
            spec_id=data["spec_id"],
            goal=data["goal"],
            engine=data.get("engine", "ansible"),
            supported_platforms=data.get("supported_platforms", ["rhel9"]),
            desired_state=data.get("desired_state", {}),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            dependencies=data.get("dependencies", []),
            resource_contract=res_contract,
            execution_dag=data.get("execution_dag", []),
            risk_level=data.get("risk_level", "MEDIUM"),
            policy_requirements=data.get("policy_requirements", []),
            idempotency_requirements=data.get("idempotency_requirements", []),
            rollback_requirements=data.get("rollback_requirements", {}),
            postconditions=probes,
            failure_handling=data.get("failure_handling", {}),
            observability_requirements=data.get("observability_requirements", {}),
        )
