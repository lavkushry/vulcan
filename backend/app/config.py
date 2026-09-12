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
from app.adapters.ansible_runner_adapter import AnsibleRunnerExecutionEngine
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
from app.adapters.redis_chat_repository import RedisChatSessionRepository

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
        raw_db_url = os.getenv("DATABASE_URL", "")
        postgres_url = os.getenv("POSTGRES_URL") or (raw_db_url if (raw_db_url.startswith("postgresql://") or raw_db_url.startswith("postgres://")) else None)
        persistence_backend = os.getenv("VULCAN_PERSISTENCE_BACKEND", "postgres" if postgres_url else "sqlite").lower()

        if persistence_backend in ("postgres", "postgresql") and postgres_url:
            self.database_url = postgres_url
            self.persistence_backend = "postgres"
        else:
            self.database_url = raw_db_url if (raw_db_url and not raw_db_url.startswith("postgres")) else "data/vulcan.db"
            self.persistence_backend = "sqlite"

        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.simulation_mode = os.getenv("SIMULATION_MODE", "true").lower() == "true"

        # 1. Infrastructure Adapters
        redis_nodes = self._detect_redis()
        self.redis_nodes = redis_nodes
        self.lock_manager = RedlockManager(redis_nodes=redis_nodes)
        pam_url = os.getenv("CYBERARK_CCP_URL")
        pam_mock = os.getenv("CYBERARK_MOCK_MODE", "true" if not pam_url else "false").lower() in ("1", "true", "yes")
        self.secret_provider = CyberArkPAMProvider(
            pam_url=pam_url,
            app_id=os.getenv("CYBERARK_APP_ID", "VULCAN_CONTROL_PLANE"),
            safe=os.getenv("CYBERARK_SAFE", "PNC_AUTOMATION_KEYS"),
            cert_path=os.getenv("CYBERARK_CERT_PATH"),
            key_path=os.getenv("CYBERARK_KEY_PATH"),
            ca_bundle=os.getenv("CYBERARK_CA_BUNDLE"),
            mock_mode=pam_mock
        )
        snow_instance = os.getenv("SERVICENOW_INSTANCE_URL")
        snow_user = os.getenv("SERVICENOW_USERNAME")
        snow_pass = os.getenv("SERVICENOW_PASSWORD")
        snow_token = os.getenv("SERVICENOW_AUTH_TOKEN")
        snow_mock = os.getenv("SERVICENOW_MOCK_MODE", "true").lower() in ("1", "true", "yes") or not snow_instance
        self.snow_gateway = ServiceNowGateway(
            instance_url=snow_instance,
            username=snow_user,
            password=snow_pass,
            auth_token=snow_token,
            mock_mode=snow_mock
        )
        s3_endpoint = os.getenv("S3_ENDPOINT_URL")
        s3_access = os.getenv("S3_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID")
        s3_secret = os.getenv("S3_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
        s3_public_endpoint = os.getenv("S3_PUBLIC_ENDPOINT_URL") or s3_endpoint
        s3_bucket = os.getenv("S3_BUCKET_NAME", "vulcan-artifacts")

        self.storage_gateway = S3MultipartGateway(
            bucket_name=s3_bucket,
            endpoint_url=s3_endpoint,
            public_endpoint_url=s3_public_endpoint,
            aws_access_key_id=s3_access,
            aws_secret_access_key=s3_secret,
            mock_mode=(not s3_endpoint and not s3_access)
        )
        if not self.simulation_mode:
            self.execution_engine = AnsibleRunnerExecutionEngine()
            logger.info("Initialized real AnsibleRunnerExecutionEngine for production execution.")
        else:
            self.execution_engine = SimulationExecutionEngine(delay_per_step=0.02)
            logger.info("Initialized SimulationExecutionEngine.")

        # 2. AI Chat Model & Embedding Providers
        from app.adapters.chat_providers import get_chat_provider
        self.chat_provider = get_chat_provider()
        from app.adapters.embedding_providers import get_embedding_provider
        self.embedding_provider = get_embedding_provider()

        # 3. Seed Catalog (in-memory materialization)
        self.catalog = self._build_catalog()

        # 4. Durable Persistence Repositories & Audit Ledger (Milestone B)
        if self.persistence_backend == "postgres":
            try:
                from app.adapters.postgres_catalog_repository import PostgresCatalogRepository
                from app.adapters.postgres_job_repository import PostgresJobRepository
                from app.adapters.postgres_audit_adapter import PostgresAuditAdapter

                self.catalog_repo = PostgresCatalogRepository(
                    db_url=self.database_url,
                    embedding_provider=self.embedding_provider,
                )
                self.job_repo = PostgresJobRepository(
                    db_url=self.database_url,
                    catalog_repo=self.catalog_repo,
                    catalog=self.catalog
                )
                pg_audit = PostgresAuditAdapter(db_url=self.database_url)
                self.audit_repo = pg_audit
                self.audit_logger = pg_audit
                logger.info("Initialized PostgreSQL 16 durable persistence for Catalog, Jobs, and Merkle Audit Ledger.")

                # Sync curated catalog items if missing
                if self.catalog_repo.count(curation_status="CURATED") < len(self.catalog):
                    for item in self.catalog:
                        self.catalog_repo.save(item)
                    logger.info("Seeded %d catalog items into PostgreSQL pgvector.", len(self.catalog))
            except Exception as e:
                logger.critical("FATAL: Failed to initialize PostgreSQL persistence (%s). Refusing silent fallback to file ledger.", e)
                raise RuntimeError(
                    f"PostgreSQL persistence failed to initialize: {e}. Refusing silent degradation to file-based ledger."
                ) from e
        else:
            self.job_repo = SQLiteJobRepository(db_path=self.database_url, catalog=self.catalog)
            self.audit_repo = SQLiteAuditLedgerRepository(db_path=self.database_url)
            self.audit_logger = MerkleAuditLogger(persistence_file="data/audit_ledger.jsonl")
            self.catalog_repo = SQLiteCatalogRepository(db_path=self.database_url)
            seeded = self.catalog_repo.seed_if_empty(self.catalog)
            if seeded > 0:
                logger.info(f"Seeded {seeded} catalog items into SQLite.")

        # 5. Distributed Approval Sweeper with Redlock Leader Election
        from app.core.approval_sweeper import ApprovalSweeper
        self.approval_sweeper = ApprovalSweeper(
            job_repo=self.job_repo,
            audit_logger=self.audit_logger,
            lock_manager=self.lock_manager,
            interval_seconds=float(os.getenv("VULCAN_SWEEPER_INTERVAL", "5.0")),
            timeout_seconds=int(os.getenv("VULCAN_APPROVAL_TIMEOUT", "900"))
        )

        # 6. Seed sample jobs into database if empty
        self._seed_jobs_to_db()

        # 7. In-memory job cache for backward compatibility during transition
        self.jobs = self._load_jobs_from_db()

        # 8. AI & Domain Use Cases
        active_catalog_repo = self.catalog_repo if self.persistence_backend == "postgres" else None
        self.intent_resolver = IntentResolver(
            catalog=self.catalog,
            chat_model_provider=self.chat_provider,
            catalog_repo=active_catalog_repo,
            embedding_provider=self.embedding_provider,
            servicenow_gateway=self.snow_gateway,
        )
        self.diagnostic_engine = FailureDiagnosticEngine()
        redis_client = self.redis_nodes[0] if self.redis_nodes else None
        self.chat_session_repo = RedisChatSessionRepository(
            redis_client=redis_client,
            db_url=self.database_url if self.persistence_backend == "postgres" else None,
            ttl_seconds=int(os.getenv("VULCAN_CHAT_SESSION_TTL", "7200"))
        )

        # 9. Decoupled Job Queue & Worker Fleet (BKND-18)
        from app.adapters.redis_queue_adapter import RedisJobQueue, InMemoryJobQueue
        from app.workers.execution_worker import ExecutionWorkerFleet
        from app.api.websockets import ws_hub

        if redis_client:
            try:
                self.job_queue = RedisJobQueue(redis_client=redis_client)
                logger.info("Initialized RedisJobQueue (stream: vulcan:jobs:dispatch)")
            except Exception as e:
                logger.warning("Could not initialize RedisJobQueue: %s. Falling back to InMemoryJobQueue.", e)
                self.job_queue = InMemoryJobQueue()
        else:
            self.job_queue = InMemoryJobQueue()
            logger.info("Initialized InMemoryJobQueue.")

        self.embedded_worker = os.getenv("VULCAN_EMBEDDED_WORKER", "true").lower() in ("1", "true", "yes")
        worker_concurrency = int(os.getenv("VULCAN_WORKER_CONCURRENCY", "10" if self.embedded_worker else "75"))
        self.worker_fleet = ExecutionWorkerFleet(
            job_queue=self.job_queue,
            container=self,
            ws_hub=ws_hub,
            concurrency=worker_concurrency,
            fleet_name="vulcan-fleet"
        )
        if self.embedded_worker:
            self.worker_fleet.start()
            logger.info("Started embedded ExecutionWorkerFleet with concurrency=%d", worker_concurrency)

    def _detect_redis(self) -> list:
        """Attempt to connect to Redis. Returns node list or empty list."""
        try:
            import redis
            r = redis.Redis.from_url(self.redis_url, socket_timeout=5, socket_connect_timeout=2)
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

    def create_runner(self, log_event_stream=None, status_event_stream=None) -> AnsibleJobRunner:
        return AnsibleJobRunner(
            engine_port=self.execution_engine,
            lock_manager=self.lock_manager,
            audit_logger=self.audit_logger,
            secret_provider=self.secret_provider,
            snow_gateway=self.snow_gateway,
            storage_gateway=self.storage_gateway,
            log_event_stream=log_event_stream,
            status_event_stream=status_event_stream
        )


container = AppContainer()
