"""
Project Vulcan: Unit and Invariant Tests for Stack Composer (REG-05)
Verifies:
1. Multi-module landing zone composition into immutable, curated CatalogItem.
2. 40-character Git SHA invariant enforcement.
3. Maker-Checker and risk tier policy assignment on composite stacks.
4. Schema validation and advisory default preservation (Rule 2 / D1 / CHAT-10).
5. BaseJobRunner execution clearance for curated composite stacks.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.domain.entities import (
    ApprovalDecision,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
    CurationStatus,
)
from app.domain.exceptions import ParameterValidationError, PolicyViolationError
from app.adapters.stack_composer import (
    CompositeSubModule,
    StackComposer,
    create_aws_banking_landing_zone_stack,
)
from app.adapters.simulation_adapter import SimulationExecutionEngine
from app.use_cases.runner import TerraformJobRunner
from app.ports.interfaces import IAuditLogger, ILockManager, ISecretProvider


class DummyLock(ILockManager):
    def acquire(self, key: str, ttl_ms: int = 30000):
        return True, "test-token", 1
    def release(self, key: str, token: str):
        return True


class DummyAudit(IAuditLogger):
    def __init__(self):
        self.records = []
    def record(self, job: ExecutionJob, event_type: str, details: dict, actor: Optional[str] = None):
        self.records.append((event_type, details))


class DummySecrets(ISecretProvider):
    def get_secret(self, key: str) -> str:
        return "super-secret"


def test_compose_stack_creates_curated_catalog_item():
    sub_modules = [
        CompositeSubModule(
            module_name="vpc",
            upstream_ref="v5.0.0",
            role="network",
            exposed_parameters=["cidr"],
        ),
        CompositeSubModule(
            module_name="eks",
            upstream_ref="v20.0.0",
            role="compute",
            exposed_parameters=["node_count"],
        ),
    ]
    schema = {
        "type": "object",
        "required": ["cidr", "node_count"],
        "properties": {
            "cidr": {"type": "string"},
            "node_count": {"type": "integer"},
        },
    }

    item = StackComposer.compose_stack(
        identifier="aws.test.landing_zone",
        name="Test AWS Landing Zone",
        description="Test composite architecture",
        sub_modules=sub_modules,
        input_schema=schema,
        internal_commit_sha="a" * 40,
        risk_tier=RiskTier.HIGH,
        suggested_defaults={"cidr": "10.0.0.0/16"},
    )

    assert item.curation_status == CurationStatus.CURATED
    assert item.can_execute() is True
    assert item.engine == ExecutionEngineType.TERRAFORM
    assert item.risk_tier == RiskTier.HIGH
    assert item.requires_maker_checker is True
    assert item.provenance["is_composite"] is True
    assert len(item.provenance["sub_modules"]) == 2
    assert item.provenance["suggested_defaults"]["cidr"] == "10.0.0.0/16"


def test_compose_stack_rejects_invalid_sha():
    sub_modules = []
    with pytest.raises(ParameterValidationError, match="must bind to a 40-character Git commit SHA"):
        StackComposer.compose_stack(
            identifier="aws.test.bad_sha",
            name="Bad SHA Stack",
            description="Should fail",
            sub_modules=sub_modules,
            input_schema={},
            internal_commit_sha="invalid-short-sha",
        )


def test_create_aws_banking_landing_zone_stack():
    item = create_aws_banking_landing_zone_stack()

    assert item.identifier == "aws.enterprise.landing_zone.vpc_eks_rds"
    assert item.curation_status == CurationStatus.CURATED
    assert item.can_execute() is True
    assert len(item.git_commit_sha) == 40
    assert item.risk_tier == RiskTier.HIGH
    assert item.requires_maker_checker is True
    assert item.requires_chg is True

    # Verify submodules
    roles = [m["role"] for m in item.provenance["sub_modules"]]
    assert "network" in roles
    assert "compute" in roles
    assert "database" in roles

    # Verify required parameters in schema
    req_fields = item.input_schema["required"]
    assert "vpc_cidr_block" in req_fields
    assert "aws_region" in req_fields
    assert "cluster_name" in req_fields
    assert "eks_node_count" in req_fields
    assert "db_instance_class" in req_fields
    assert "db_name" in req_fields
    assert "environment" in req_fields

    # Verify suggested defaults are present in provenance as advisory hints
    defaults = item.provenance["suggested_defaults"]
    assert defaults["aws_region"] == "us-east-1"
    assert defaults["eks_node_count"] == 3


def test_curated_landing_zone_executes_in_runner():
    item = create_aws_banking_landing_zone_stack()

    now = datetime.now(timezone.utc)
    job = ExecutionJob(
        job_id="job-lz-001",
        correlation_id="EXEC-LZ-001",
        catalog_item=item,
        requester_id="eng.alice",
        target_resource_id="aws-prod-landing-zone",
        parameters={
            "vpc_cidr_block": "10.200.0.0/16",
            "aws_region": "us-east-1",
            "cluster_name": "prod-core-cluster",
            "eks_node_count": 5,
            "db_instance_class": "db.r6g.large",
            "db_name": "retail_core_db",
            "environment": "prod",
        },
        servicenow_chg="CHG0099881",
    )
    job.request_approval(now)
    job.apply_approval_decision(
        ApprovalDecision(
            decision="APPROVE",
            approver_id="lead.bob",
            decided_at=now,
            reason="Landing zone review complete and authorized"
        ),
        evaluated_at=now,
    )
    assert job.status == JobStatus.QUEUED

    mock_lock = MagicMock()
    mock_audit = MagicMock()
    mock_secrets = MagicMock()
    mock_snow = MagicMock()
    mock_snow.is_within_maintenance_window.return_value = True

    runner = TerraformJobRunner(
        engine_port=SimulationExecutionEngine(),
        lock_manager=mock_lock,
        audit_logger=mock_audit,
        secret_provider=mock_secrets,
        snow_gateway=mock_snow,
    )

    result = runner.run(job)
    assert result.exit_code == 0
    assert result.status == "SUCCESS"
    mock_audit.record.assert_called()
