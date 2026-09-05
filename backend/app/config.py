"""
Project Vulcan: Configuration & Dependency Injection Container
"""
import os
from typing import List, Optional

from app.adapters.crypto_audit_adapter import MerkleAuditLogger
from app.adapters.cyberark_adapter import CyberArkPAMProvider
from app.adapters.redlock_adapter import RedlockManager
from app.adapters.s3_multipart_adapter import S3MultipartGateway
from app.adapters.servicenow_adapter import ServiceNowGateway
from app.adapters.simulation_adapter import SimulationExecutionEngine
from app.domain.entities import CatalogItem, ExecutionEngineType, RiskTier
from app.use_cases.diagnose_failure import FailureDiagnosticEngine
from app.use_cases.resolve_intent import IntentResolver
from app.use_cases.runner import AnsibleJobRunner


class AppContainer:
    """
    Dependency Injection Container assembling Ports and Adapters.
    """

    def __init__(self):
        # 1. Infrastructure Adapters
        self.lock_manager = RedlockManager(redis_nodes=[])
        self.audit_logger = MerkleAuditLogger(persistence_file="data/audit_ledger.jsonl")
        self.secret_provider = CyberArkPAMProvider(mock_mode=True)
        self.snow_gateway = ServiceNowGateway(mock_mode=True)
        self.storage_gateway = S3MultipartGateway(bucket_name="pnc-vulcan-artifacts", mock_mode=True)
        self.execution_engine = SimulationExecutionEngine(delay_per_step=0.02)

        # 2. Seed Catalog
        self.catalog = self._build_catalog()

        # 3. AI & Domain Use Cases
        self.intent_resolver = IntentResolver(catalog=self.catalog)
        self.diagnostic_engine = FailureDiagnosticEngine()

        # 4. In-Memory Job Store for Active Control Plane
        self.jobs = {}

    def _build_catalog(self) -> List[CatalogItem]:
        return [
            CatalogItem(
                id="cat-f5-renew",
                identifier="net-f5-cert-renew",
                name="F5 BIG-IP SSL Certificate Renewal",
                engine=ExecutionEngineType.ANSIBLE,
                git_repo="git@github.com:pnc/net-playbooks.git",
                git_commit_sha="a1b2c3d4e5f67890123456789abcdef012345678",
                playbook_or_module_path="catalog/net-f5-cert-renew/playbook.yml",
                risk_tier=RiskTier.HIGH,
                requires_maker_checker=True,
                requires_chg=True,
                input_schema={
                    "type": "object",
                    "required": ["hostname", "vip_ip", "cert_valid_days"],
                    "properties": {
                        "hostname": {"type": "string", "pattern": r"^[a-z0-9-]+(\.pnc\.com)?$"},
                        "vip_ip": {"type": "string", "pattern": r"^\d{1,3}(\.\d{1,3}){3}$"},
                        "cert_valid_days": {"type": "integer", "minimum": 30, "maximum": 365}
                    }
                }
            ),
            CatalogItem(
                id="cat-db-expand",
                identifier="db-expand-tablespace",
                name="Database Tablespace Disk Expansion",
                engine=ExecutionEngineType.ANSIBLE,
                git_repo="git@github.com:pnc/db-playbooks.git",
                git_commit_sha="b2c3d4e5f67890123456789abcdef01234567890",
                playbook_or_module_path="catalog/db-expand-tablespace/playbook.yml",
                risk_tier=RiskTier.HIGH,
                requires_maker_checker=True,
                requires_chg=True,
                input_schema={
                    "type": "object",
                    "required": ["tablespace_name", "expand_gb"],
                    "properties": {
                        "tablespace_name": {"type": "string"},
                        "expand_gb": {"type": "integer", "minimum": 10, "maximum": 500}
                    }
                }
            ),
            CatalogItem(
                id="cat-vpc-peer",
                identifier="cloud-vpc-peering",
                name="Cross-Account AWS VPC Peering Connection",
                engine=ExecutionEngineType.TERRAFORM,
                git_repo="git@github.com:pnc/cloud-terraform.git",
                git_commit_sha="c3d4e5f67890123456789abcdef0123456789012",
                playbook_or_module_path="catalog/cloud-vpc-peering/main.tf",
                risk_tier=RiskTier.MEDIUM,
                requires_maker_checker=True,
                requires_chg=True,
                input_schema={
                    "type": "object",
                    "required": ["peer_vpc_id", "peer_cidr"],
                    "properties": {
                        "peer_vpc_id": {"type": "string", "pattern": r"^vpc-[0-9a-fA-F]+$"},
                        "peer_cidr": {"type": "string", "pattern": r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$"}
                    }
                }
            ),
            CatalogItem(
                id="cat-os-patch",
                identifier="os-kernel-patch",
                name="Enterprise Linux Kernel Patching (10GB ISO)",
                engine=ExecutionEngineType.ANSIBLE,
                git_repo="git@github.com:pnc/os-playbooks.git",
                git_commit_sha="d4e5f67890123456789abcdef012345678901234",
                playbook_or_module_path="catalog/os-kernel-patch/playbook.yml",
                risk_tier=RiskTier.HIGH,
                requires_maker_checker=True,
                requires_chg=True,
                input_schema={
                    "type": "object",
                    "required": ["target_host"],
                    "properties": {
                        "target_host": {"type": "string"}
                    }
                }
            )
        ]

    def create_runner(self, log_event_stream=None) -> AnsibleJobRunner:
        return AnsibleJobRunner(
            engine_port=self.execution_engine,
            lock_manager=self.lock_manager,
            audit_logger=self.audit_logger,
            secret_provider=self.secret_provider,
            snow_gateway=self.snow_gateway,
            storage_gateway=self.storage_gateway,
            log_event_stream=log_event_stream
        )


container = AppContainer()
