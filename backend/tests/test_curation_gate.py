"""
Project Vulcan: Curation Gate & Steel-Cage Invariant Tests (REG-01 / REG-02 / REG-03 / INV-1)
Validates:
1. Public registry crawlers tag modules as CANDIDATE (can_execute = False).
2. BaseJobRunner strictly blocks execution of CANDIDATE items with PolicyViolationError
   and logs an immutable EXEC_BLOCKED audit record (INV-1).
3. POST /api/v1/jobs rejects candidate execution attempts with HTTP 403 Forbidden.
4. License Gate detects and flags non-permissive licenses (BUSL-1.1) and prevents approval.
5. Internal Git PR drafting produces valid vendoring manifests and compliance checklists.
6. Approval Gate promotes CANDIDATE to CURATED only after binding to internal Git + 40-char SHA.
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.domain.entities import (
    CatalogItem,
    CurationStatus,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
)
from app.domain.exceptions import ParameterValidationError, PolicyViolationError
from app.adapters.registry_crawler import (
    CurationCandidateStore,
    CurationGateService,
    RegistryCrawlerAgent,
)
from app.adapters.simulation_adapter import SimulationExecutionEngine
from app.use_cases.runner import TerraformJobRunner
from app.api.server import create_app
from app.api.routes import container


@pytest.fixture
def temp_candidate_store(tmp_path):
    store_file = tmp_path / "test_candidates.json"
    return CurationCandidateStore(store_file)


@pytest.fixture
def candidate_item():
    return CatalogItem(
        id="cand-tf-vpc-001",
        identifier="candidate.terraform.terraform-aws-modules.vpc-aws",
        name="[Candidate] Terraform AWS VPC",
        engine=ExecutionEngineType.TERRAFORM,
        git_repo="https://github.com/terraform-aws-modules/terraform-aws-vpc",
        git_commit_sha="11223344556677889900aabbccddeeff00112233",
        playbook_or_module_path="modules/vpc",
        risk_tier=RiskTier.MEDIUM,
        requires_maker_checker=True,
        requires_chg=False,
        input_schema={
            "type": "object",
            "required": ["vpc_name"],
            "properties": {
                "vpc_name": {"type": "string"},
                "cidr": {"type": "string", "default": "10.0.0.0/16"}
            }
        },
        category="network",
        description="Public candidate module from registry.terraform.io",
        tags=["aws", "vpc", "candidate"],
        curation_status=CurationStatus.CANDIDATE,
        provenance={
            "source_registry": "terraform_registry",
            "upstream_url": "https://registry.terraform.io/modules/terraform-aws-modules/vpc/aws",
            "version": "6.7.2",
            "license": "MPL-2.0",
            "license_compliant": True
        }
    )


class TestCurationInvariants:
    """Tests INV-1 enforcement at Domain and Runner layers."""

    def test_candidate_cannot_execute(self, candidate_item):
        assert candidate_item.curation_status == CurationStatus.CANDIDATE
        assert candidate_item.can_execute() is False

    def test_runner_blocks_candidate_execution_inv1(self, candidate_item):
        """INV-1: Attempting to run a CANDIDATE catalog item raises PolicyViolationError and audits EXEC_BLOCKED."""
        mock_audit = MagicMock()
        mock_locks = MagicMock()
        mock_secrets = MagicMock()

        runner = TerraformJobRunner(
            engine_port=SimulationExecutionEngine(),
            lock_manager=mock_locks,
            audit_logger=mock_audit,
            secret_provider=mock_secrets
        )

        job = ExecutionJob(
            job_id="job-test-cand-01",
            correlation_id="EXEC-CAND-01",
            catalog_item=candidate_item,
            requester_id="eng.alice",
            target_resource_id="aws-vpc-01",
            parameters={"vpc_name": "corp-vpc"}
        )
        job.transition_to(JobStatus.PARSED)

        with pytest.raises(PolicyViolationError) as exc_info:
            runner.run(job)

        assert "Execution of uncurated candidate code is strictly prohibited by INV-1" in str(exc_info.value)
        # Verify EXEC_BLOCKED was committed to audit ledger
        mock_audit.record.assert_called_once()
        call_args = mock_audit.record.call_args[0]
        assert call_args[1] == "EXEC_BLOCKED"
        assert call_args[2]["reason"] == "UNCURATED_CANDIDATE_EXECUTION_FORBIDDEN"


class TestCurationGateWorkflow:
    """Tests candidate store, PR drafting, license gating, and human promotion."""

    def test_license_gate_flags_and_blocks_busl(self, temp_candidate_store):
        crawler = RegistryCrawlerAgent(temp_candidate_store)
        service = CurationGateService(temp_candidate_store)

        busl_mod = {
            "namespace": "hashicorp",
            "name": "consul",
            "provider": "aws",
            "version": "1.0.0",
            "license": "BUSL-1.1"
        }
        cand = crawler.transform_terraform_candidate(busl_mod)
        assert cand.provenance["license"] == "BUSL-1.1"
        assert cand.provenance["license_compliant"] is False

        temp_candidate_store.add(cand)

        # Attempting to approve a BUSL candidate must fail with PolicyViolationError
        with pytest.raises(PolicyViolationError) as exc_info:
            service.approve_candidate(
                identifier=cand.identifier,
                approver_id="lead.curator",
                internal_git_repo="git@github.internal.bank.com:automation/consul.git",
                internal_commit_sha="a" * 40
            )
        assert "violates enterprise policy" in str(exc_info.value)

    def test_draft_registration_pr(self, temp_candidate_store, candidate_item):
        service = CurationGateService(temp_candidate_store)
        temp_candidate_store.add(candidate_item)

        pr = service.draft_registration_pr(candidate_item.identifier)

        assert pr["candidate_identifier"] == candidate_item.identifier
        assert len(pr["tarball_checksum_sha256"]) == 64
        assert "tfsec/Checkov" in pr["compliance_checklist"][0]

        updated = temp_candidate_store.get(candidate_item.identifier)
        assert updated.curation_status == CurationStatus.DRAFTED_PR

    def test_approve_candidate_enforces_internal_git_sha(self, temp_candidate_store, candidate_item):
        service = CurationGateService(temp_candidate_store)
        temp_candidate_store.add(candidate_item)

        # 1. Invalid SHA must fail
        with pytest.raises(ParameterValidationError):
            service.approve_candidate(
                identifier=candidate_item.identifier,
                approver_id="lead.curator",
                internal_git_repo="git@github.internal.bank.com:automation/vpc.git",
                internal_commit_sha="short-sha"
            )

        # 2. Valid internal Git repo + 40-char SHA succeeds
        internal_sha = "aabbccddeeff00112233445566778899aabbccdd"
        internal_repo = "git@github.internal.bank.com:automation/terraform-aws-vpc.git"
        curated = service.approve_candidate(
            identifier=candidate_item.identifier,
            approver_id="lead.curator",
            internal_git_repo=internal_repo,
            internal_commit_sha=internal_sha
        )

        assert curated.curation_status == CurationStatus.CURATED
        assert curated.can_execute() is True
        assert curated.git_repo == internal_repo
        assert curated.git_commit_sha == internal_sha
        assert not curated.identifier.startswith("candidate.")


class TestCurationRestApi:
    """Tests Curation Gateway REST API endpoints and job submission blocking."""

    @pytest.fixture
    def client(self):
        app = create_app()
        return TestClient(app)

    def test_job_submission_blocks_candidate_with_403(self, client, candidate_item):
        # Temporarily inject candidate into active catalog
        container.catalog.append(candidate_item)

        payload = {
            "identifier": candidate_item.identifier,
            "requester_id": "eng.alice",
            "parameters": {"vpc_name": "corp-vpc"}
        }

        res = client.post("/api/v1/jobs", json=payload)
        assert res.status_code == 403
        assert "Execution of uncurated candidate code is strictly forbidden by INV-1" in res.json()["detail"]

        # Clean up
        container.catalog = [c for c in container.catalog if c.identifier != candidate_item.identifier]

    def test_curation_api_candidate_lifecycle(self, client, candidate_item):
        from app.api.curation_routes import candidate_store
        candidate_store.add(candidate_item)

        # 1. List candidates
        list_res = client.get("/api/v1/curation/candidates?source=terraform_registry")
        assert list_res.status_code == 200
        items = list_res.json()
        assert any(i["identifier"] == candidate_item.identifier for i in items)

        # 2. Draft PR
        draft_res = client.post(f"/api/v1/curation/candidates/{candidate_item.identifier}/draft-pr", json={})
        assert draft_res.status_code == 200
        assert "tarball_checksum_sha256" in draft_res.json()

        # 3. Approve candidate
        approve_payload = {
            "approver_id": "lead.curator",
            "internal_git_repo": "git@github.internal.bank.com:automation/vpc.git",
            "internal_commit_sha": "1234567890abcdef1234567890abcdef12345678"
        }
        appr_res = client.post(f"/api/v1/curation/candidates/{candidate_item.identifier}/approve", json=approve_payload)
        assert appr_res.status_code == 200
        assert appr_res.json()["status"] == "APPROVED"
