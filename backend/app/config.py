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
        self.jobs = self._seed_jobs()

    def _build_catalog(self) -> List[CatalogItem]:
        from app.catalog_data import get_catalog_items
        return get_catalog_items()

    def _seed_jobs(self) -> dict:
        from app.catalog_data import get_sample_tasks
        from app.domain.entities import ExecutionJob, JobStatus
        cat_map = {item.identifier: item for item in self.catalog}
        samples = get_sample_tasks()
        jobs = {}
        for s in samples:
            cat_item = cat_map.get(s['identifier'])
            if not cat_item:
                continue
            params = dict(s.get('parameters', {}))
            for req in cat_item.input_schema.get('required', []):
                if req not in params:
                    props = cat_item.input_schema.get('properties', {}).get(req, {})
                    params[req] = props.get('default', 'test-val')
            job = ExecutionJob(
                job_id=s['id'],
                correlation_id=s['correlation_id'],
                catalog_item=cat_item,
                requester_id=s['requester_id'],
                target_resource_id=s['target_resource'],
                parameters=params,
                environment=s.get('environment', 'PROD')
            )
            job.status = JobStatus(s['status'])
            job.approver_id = s.get('approver_id')
            job.error_message = s.get('error_message')
            jobs[job.correlation_id] = job
        return jobs

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
