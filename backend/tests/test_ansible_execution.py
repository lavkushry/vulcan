"""
Project Vulcan: Automated Tests for Real Ansible Execution & Sandbox Catalog
Validates AnsibleRunnerExecutionEngine, role catalog registration,
parameter schemas, and AI intent resolution for GitHub roles.
"""
import os
import pytest
from app.adapters.ansible_runner_adapter import AnsibleRunnerExecutionEngine
from app.catalog_data import get_catalog_items, find_matching_playbook
from app.domain.entities import CatalogItem, ExecutionEngineType, ExecutionJob, JobStatus, RiskTier


class TestAnsibleCatalogRegistration:
    """Tests verifying all 9 real Ansible GitHub playbooks are properly registered."""

    def test_real_playbooks_registered(self):
        items = get_catalog_items()
        item_map = {item.identifier: item for item in items}

        real_identifiers = [
            "os-sandbox-ping",
            "db-postgres-provision",
            "ci-jenkins-deploy",
            "git-gitlab-stage",
            "k8s-node-provision",
            "web-nginx-deploy",
            "cache-redis-deploy",
            "sec-system-hardening",
            "sec-create-operator",
        ]

        for ident in real_identifiers:
            assert ident in item_map, f"Missing real playbook: {ident}"
            item = item_map[ident]
            assert item.engine == ExecutionEngineType.ANSIBLE
            assert item.playbook_or_module_path.startswith("ansible/playbooks/")
            assert "type" in item.input_schema
            assert item.input_schema["type"] == "object"
            assert "properties" in item.input_schema
            assert len(item.input_schema["properties"]) > 0

    def test_postgres_schema_validation(self):
        items = get_catalog_items()
        item_map = {item.identifier: item for item in items}
        pg = item_map["db-postgres-provision"]
        assert pg.risk_tier == RiskTier.HIGH
        assert pg.requires_maker_checker is True
        assert "postgres_user" in pg.input_schema["properties"]
        assert "postgres_db_name" in pg.input_schema["properties"]
        assert "postgres_port" in pg.input_schema["properties"]

    def test_sandbox_ping_schema(self):
        items = get_catalog_items()
        item_map = {item.identifier: item for item in items}
        ping = item_map["os-sandbox-ping"]
        assert ping.risk_tier == RiskTier.LOW
        assert ping.requires_maker_checker is False
        assert "target_host" in ping.input_schema["properties"]


class TestAnsibleIntentResolution:
    """Tests verifying natural language routing to real playbooks."""

    def test_ping_intent(self):
        res = find_matching_playbook("ping sandbox and check facts")
        assert res["matched"] is True
        assert res["identifier"] == "os-sandbox-ping"

    def test_postgres_intent(self):
        res = find_matching_playbook("provision postgresql database with app_user")
        assert res["matched"] is True
        assert res["identifier"] == "db-postgres-provision"

    def test_jenkins_intent(self):
        res = find_matching_playbook("setup jenkins ci automation server on port 8080")
        assert res["matched"] is True
        assert res["identifier"] == "ci-jenkins-deploy"

    def test_nginx_intent(self):
        res = find_matching_playbook("deploy nginx reverse proxy web server")
        assert res["matched"] is True
        assert res["identifier"] == "web-nginx-deploy"

    def test_hardening_intent(self):
        res = find_matching_playbook("apply ssh security hardening and audit policy")
        assert res["matched"] is True
        assert res["identifier"] == "sec-system-hardening"


class TestAnsibleRunnerExecutionEngine:
    """Tests verifying AnsibleRunnerExecutionEngine path resolution and execution flow."""

    def test_engine_initialization(self):
        engine = AnsibleRunnerExecutionEngine(private_data_dir="/tmp/vulcan-ansible-test")
        assert engine.private_data_dir == "/tmp/vulcan-ansible-test"
        assert os.path.exists("/tmp/vulcan-ansible-test")

    def test_playbook_path_resolution(self):
        engine = AnsibleRunnerExecutionEngine()
        resolved = engine._resolve_playbook_path("ansible/playbooks/ping_check.yml")
        assert resolved is not None
        assert resolved.endswith("ping_check.yml")
        assert os.path.isfile(resolved)

    def test_inventory_path_resolution(self):
        engine = AnsibleRunnerExecutionEngine()
        inventory = engine._resolve_inventory_path()
        assert inventory is not None
        assert inventory.endswith("hosts")
        assert os.path.isfile(inventory)

    def test_ansible_cfg_resolution(self):
        engine = AnsibleRunnerExecutionEngine()
        cfg = engine._resolve_ansible_cfg()
        assert cfg is not None
        assert cfg.endswith("ansible.cfg")
        assert os.path.isfile(cfg)

    def test_fallback_when_playbook_missing(self):
        engine = AnsibleRunnerExecutionEngine()
        dummy_item = CatalogItem(
            id="cat-dummy-999",
            identifier="dummy-missing",
            name="Dummy Missing Playbook",
            engine=ExecutionEngineType.ANSIBLE,
            git_repo="git@github.com:dummy/repo.git",
            git_commit_sha="0000000000000000000000000000000000000000",
            playbook_or_module_path="non_existent_playbook_999.yml",
            risk_tier=RiskTier.LOW,
            requires_maker_checker=False,
            requires_chg=False,
            input_schema={},
            category="os_patching",
            description="Dummy item for fallback test"
        )

        job = ExecutionJob(
            job_id="test-job-999",
            correlation_id="EXEC-TEST-999",
            catalog_item=dummy_item,
            requester_id="eng.alice",
            target_resource_id="sandbox",
            parameters={}
        )

        logs = []
        res = engine.execute(job, event_callback=logs.append, secrets={})
        assert res.status == "SUCCESS"
        assert res.exit_code == 0
