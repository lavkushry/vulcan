"""
Project Vulcan: Configuration & Dependency Injection Container
Wires ports to adapters with progressive infrastructure detection.
"""
import logging
import os
from typing import List, Optional

from app.adapters.crypto_audit_adapter import MerkleAuditLogger
from app.adapters.cyberark_adapter import CyberArkPAMProvider
from app.adapters.fake_chat_adapter import DeterministicFakeChatProvider
from app.adapters.redlock_adapter import RedlockManager
from app.adapters.s3_multipart_adapter import S3MultipartGateway
from app.adapters.servicenow_adapter import ServiceNowGateway
from app.adapters.simulation_adapter import SimulationExecutionEngine
from app.adapters.sqlite_repositories import (
    SQLiteAuditLedgerRepository,
    SQLiteCatalogRepository,
    SQLiteJobRepository,
)
from app.domain.entities import CatalogItem, ExecutionEngineType, RiskTier
from app.use_cases.diagnose_failure import FailureDiagnosticEngine
from app.use_cases.resolve_intent import IntentResolver
from app.use_cases.runner import AnsibleJobRunner

logger = logging.getLogger("vulcan.config")


class AppContainer:
    """
    Dependency Injection Container assembling Ports and Adapters.
    Supports progressive infrastructure detection:
    - SQLite for durable persistence (zero-dependency, survives restarts)
    - Redis for distributed locking and WebSocket pub/sub (when available)
    - In-memory fallbacks when infrastructure is unavailable
    """

    def __init__(self):
        # 0. Configuration
        self.database_url = os.getenv("DATABASE_URL", "data/vulcan.db")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.simulation_mode = os.getenv("SIMULATION_MODE", "true").lower() == "true"

        # 1. Infrastructure Adapters
        redis_nodes = self._detect_redis()
        self.lock_manager = RedlockManager(redis_nodes=redis_nodes)
        if redis_nodes:
            from app.api.websockets import ws_hub
            ws_hub.set_redis_client(redis_nodes[0])
        self.audit_logger = MerkleAuditLogger(persistence_file="data/audit_ledger.jsonl")
        self.secret_provider = CyberArkPAMProvider(mock_mode=True)
        self.snow_gateway = ServiceNowGateway(mock_mode=True)
        self.storage_gateway = S3MultipartGateway(
            bucket_name=os.getenv("S3_BUCKET_NAME", "vulcan-artifacts"),
            mock_mode=True
        )
        self.execution_engine = SimulationExecutionEngine(delay_per_step=0.02)

        # 2. AI Chat Model Provider
        self.chat_provider = DeterministicFakeChatProvider()

        # 3. Seed Catalog (in-memory materialization)
        self.catalog = self._build_catalog()

        # 4. Durable Persistence Repositories (SQLite)
        self.job_repo = SQLiteJobRepository(db_path=self.database_url, catalog=self.catalog)
        self.audit_repo = SQLiteAuditLedgerRepository(db_path=self.database_url)
        self.catalog_repo = SQLiteCatalogRepository(db_path=self.database_url)

        # 5. Seed catalog into SQLite if empty
        seeded = self.catalog_repo.seed_if_empty(self.catalog)
        if seeded > 0:
            logger.info(f"Seeded {seeded} catalog items into SQLite.")

        # 6. Seed sample jobs into SQLite if empty
        self._seed_jobs_to_db()

        # 7. In-memory job cache for backward compatibility during transition
        # Routes that still reference container.jobs will work
        self.jobs = self._load_jobs_from_db()

        # 8. AI & Domain Use Cases
        self.intent_resolver = IntentResolver(catalog=self.catalog, chat_model_provider=self.chat_provider)
        self.diagnostic_engine = FailureDiagnosticEngine()

    def _detect_redis(self) -> list:
        """Attempt to connect to Redis. Returns node list or empty list."""
        try:
            import redis
            r = redis.Redis.from_url(self.redis_url, socket_timeout=1)
            r.ping()
            logger.info(f"Redis detected at {self.redis_url}")
            return [r]
        except Exception:
            logger.info("Redis not available — using in-memory lock fallback.")
            return []

    def _build_catalog(self) -> List[CatalogItem]:
        from app.catalog_data import get_catalog_items
        return get_catalog_items()

    def _seed_jobs_to_db(self) -> None:
        """Seed sample jobs into SQLite if the jobs table is empty."""
        existing = self.job_repo.list_jobs(limit=1)
        if existing:
            logger.info(f"Job repository already has data — skipping seed.")
            return

        from app.catalog_data import get_sample_tasks
        from app.domain.entities import ExecutionJob, JobStatus
        cat_map = {item.identifier: item for item in self.catalog}
        samples = get_sample_tasks()
        count = 0
        for s in samples:
            cat_item = cat_map.get(s['identifier'])
            if not cat_item:
                continue
            params = dict(s.get('parameters', {}))
            for req in cat_item.input_schema.get('required', []):
                if req not in params:
                    props = cat_item.input_schema.get('properties', {}).get(req, {})
                    params[req] = props.get('default', 'test-val')
            chg = s.get('servicenow_chg')
            if cat_item.requires_chg and not chg:
                chg = f"CHG-{s['id'].replace('task-', '')}"
            job = ExecutionJob(
                job_id=s['id'],
                correlation_id=s['correlation_id'],
                catalog_item=cat_item,
                requester_id=s['requester_id'],
                target_resource_id=s['target_resource'],
                parameters=params,
                servicenow_chg=chg,
                environment=s.get('environment', 'PROD')
            )
            job.status = JobStatus(s['status'])
            job.approver_id = s.get('approver_id')
            job.error_message = s.get('error_message')
            self.job_repo.save(job)
            count += 1
        logger.info(f"Seeded {count} sample jobs into SQLite.")

    def _load_jobs_from_db(self) -> dict:
        """Load all jobs from SQLite into in-memory dict for backward compatibility."""
        jobs = {}
        for job in self.job_repo.list_jobs(limit=500):
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
