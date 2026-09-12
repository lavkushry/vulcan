"""
Project Vulcan: FastAPI Server Assembly
Author: Alex Xu & Uncle Bob
Configures lifespan, CORS middleware, WebSocket loop binding, and route registry.
"""
import asyncio
import collections
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.auth import APIKeyMiddleware, load_token_map
from app.api.routes import router, container
from app.api.curation_routes import curation_router
from app.api.chat_routes import chat_router
from app.api.websockets import ws_hub
from app.adapters.structured_logger import setup_structured_logging

logger = logging.getLogger("vulcan.server")

SERVER_START_TIME = time.time()

# RED Telemetry Tracking (INFRA-22 Rate, Errors, Duration)
_REQUEST_COUNTS = collections.defaultdict(int)
_REQUEST_DURATION_SUM = collections.defaultdict(float)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set the running event loop on the WebSocket hub for thread-safe worker broadcasts
    loop = asyncio.get_running_loop()
    ws_hub.set_event_loop(loop)
    if hasattr(container, "redis_nodes") and container.redis_nodes:
        ws_hub.set_redis_client(container.redis_nodes[0])

    # Start distributed approval sweeper with Redlock leader election (Milestone B)
    if hasattr(container, "approval_sweeper") and container.approval_sweeper:
        container.approval_sweeper.event_publisher = ws_hub.publish
        container.approval_sweeper.start(loop)

    yield

    # Clean shutdown
    if hasattr(container, "approval_sweeper") and container.approval_sweeper:
        await container.approval_sweeper.stop()
    ws_hub.stop()


def create_app() -> FastAPI:
    # INFRA-24: Activate structured JSON logging before any other initialization
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    use_json = os.getenv("LOG_FORMAT", "json").lower() != "text"
    setup_structured_logging(level=log_level, use_json=use_json)
    logger.info("Structured logging initialized", extra={"log_format": "json" if use_json else "text", "log_level": log_level_name})

    app = FastAPI(
        title="Project Vulcan: Enterprise Automation Control Plane",
        description="High-reliability banking automation platform OS (PNC Bank Standard)",
        version="1.0.0",
        lifespan=lifespan
    )

    # API Token Authentication Middleware (Step-1 Hardening)
    token_map = load_token_map()
    auth_disabled = os.getenv("VULCAN_AUTH_DISABLED", "0").lower() in ("1", "true", "yes")
    app.add_middleware(APIKeyMiddleware, token_map=token_map, allow_disabled=auth_disabled)

    # Allow cross-origin requests from Jordan Walke's Next.js 15 Obsidian Glass frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Universal Correlation ID Middleware (INFRA-25 / BKND-19)
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        corr_id = (
            request.headers.get("x-vulcan-correlation-id")
            or request.headers.get("x-correlation-id")
            or f"VULC-{uuid.uuid4().hex[:8].upper()}"
        )
        request.state.correlation_id = corr_id
        response = await call_next(request)
        response.headers["X-Vulcan-Correlation-Id"] = corr_id
        return response

    # INFRA-24: Structured Request Logging Middleware
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_sec = time.perf_counter() - start
        duration_ms = round(duration_sec * 1000, 2)
        corr_id = getattr(request.state, "correlation_id", "-")

        # Label cardinality protection: use route template instead of raw path (e.g. /jobs/{id})
        path = request.url.path
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            endpoint_template = route.path
        else:
            # Fallback regex template normalization for dynamic parameters
            endpoint_template = re.sub(r'/(EXEC-[A-Za-z0-9_-]+|[0-9a-fA-F-]{36}|\d+)', '/{id}', path)

        if not (endpoint_template.startswith("/api/") or endpoint_template in ("/healthz", "/health", "/ready", "/metrics")):
            endpoint_group = "other"
        else:
            endpoint_group = endpoint_template

        _REQUEST_COUNTS[(request.method, str(response.status_code), endpoint_group)] += 1
        _REQUEST_DURATION_SUM[(request.method, endpoint_group)] += duration_sec

        # Skip noisy health/ready probes at INFO level; log at DEBUG
        log_fn = logger.debug if path in ("/healthz", "/health", "/ready") else logger.info
        log_fn(
            "%s %s %s %.1fms",
            request.method, path, response.status_code, duration_ms,
            extra={
                "correlation_id": corr_id,
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )
        return response

    # Standardized Consistent Error Envelope (BKND-18)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get("x-vulcan-correlation-id", f"ERR-{uuid.uuid4().hex[:8]}")
        error_code = f"ERR_{exc.status_code}"
        msg = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error_code": error_code,
                "message": msg,
                "detail": msg,  # backward compatibility for standard clients
                "correlation_id": correlation_id,
                "details": getattr(exc, "details", {}) or {"status_code": exc.status_code}
            }
        )

    # Liveness Probe (INFRA-17)
    @app.get("/healthz", tags=["Observability"])
    @app.get("/health", tags=["Observability"])
    def liveness_probe():
        """Kubernetes / Compose container liveness probe."""
        return {
            "status": "ALIVE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": round(time.time() - SERVER_START_TIME, 2)
        }

    # Readiness Probe (INFRA-17, Operational Backup Freshness Guarantee)
    @app.get("/ready", tags=["Observability"])
    def readiness_probe():
        """Kubernetes / Compose service readiness probe verifying subsystem health & backup freshness."""
        catalog_ok = len(container.catalog) > 0
        audit_ok = container.audit_logger.verify_chain()

        # Operational Backup Freshness Guarantee (Nightly cron SLA: newest snapshot < 26 hours old)
        backup_fresh = True
        backup_age_hours = None
        latest_backup_key = None
        if hasattr(container, "storage_gateway") and container.storage_gateway and not container.storage_gateway.mock_mode:
            try:
                s3 = container.storage_gateway.s3_client
                if s3:
                    bucket = container.storage_gateway.bucket_name
                    res = s3.list_objects_v2(Bucket=bucket, Prefix="backups/")
                    contents = [c for c in res.get("Contents", []) if c["Key"].endswith(".dump")]
                    if contents:
                        newest = max(contents, key=lambda x: x["LastModified"])
                        age_sec = (datetime.now(timezone.utc) - newest["LastModified"]).total_seconds()
                        backup_age_hours = round(age_sec / 3600.0, 2)
                        latest_backup_key = newest["Key"]
                        backup_fresh = backup_age_hours <= 26.0
                    else:
                        backup_fresh = False
            except Exception as e:
                logger.warning("Backup freshness check in /ready failed: %s", e)
                backup_fresh = False

        is_ready = catalog_ok and audit_ok and backup_fresh
        status_code = 200 if is_ready else 503
        provider_name = getattr(container.embedding_provider, "provider_name", "unknown")
        ai_quota_exhausted = bool(
            getattr(getattr(container, "embedding_provider", None), "quota_exhausted", False) or
            getattr(getattr(container, "chat_provider", None), "quota_exhausted", False)
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "READY" if is_ready else "NOT_READY",
                "checks": {
                    "catalog_loaded": catalog_ok,
                    "audit_chain_valid": audit_ok,
                    "backup_fresh": backup_fresh,
                    "backup_age_hours": backup_age_hours,
                    "latest_backup": latest_backup_key,
                    "lock_manager_active": True,
                    "embedding_provider_name": provider_name,
                    "ai_quota_exhausted": ai_quota_exhausted,
                    "ai_status": "QUOTA_EXHAUSTED" if ai_quota_exhausted else "OPERATIONAL"
                },
                "embedding_provider_name": provider_name,
                "ai_quota_exhausted": ai_quota_exhausted,
                "ai_status": "QUOTA_EXHAUSTED" if ai_quota_exhausted else "OPERATIONAL",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    # Prometheus Metrics Exporter (INFRA-22)
    @app.get("/metrics", response_class=PlainTextResponse, tags=["Observability"])
    def prometheus_metrics():
        """Prometheus metrics endpoint scrapable by Prometheus / OpenTelemetry."""
        catalog_size = len(container.catalog)
        if hasattr(container, "job_repo") and container.job_repo:
            if hasattr(container.job_repo, "get_status_counts"):
                counts = container.job_repo.get_status_counts()
                running_jobs = counts.get("RUNNING", 0)
                queued_jobs = counts.get("QUEUED", 0)
                pending_jobs = counts.get("PENDING_APPROVAL", 0)
                success_jobs = counts.get("SUCCESS", 0)
                failed_jobs = counts.get("FAILED", 0)
                jobs_count = counts.get("ALL", sum(v for k, v in counts.items() if k != "ALL"))
            else:
                jobs = container.job_repo.list_jobs(limit=5000)
                jobs_count = len(jobs)
                running_jobs = sum(1 for j in jobs if j.status.value == "RUNNING")
                queued_jobs = sum(1 for j in jobs if j.status.value == "QUEUED")
                pending_jobs = sum(1 for j in jobs if j.status.value == "PENDING_APPROVAL")
                success_jobs = sum(1 for j in jobs if j.status.value == "SUCCESS")
                failed_jobs = sum(1 for j in jobs if j.status.value == "FAILED")
        else:
            jobs_count = len(container.jobs)
            running_jobs = sum(1 for j in container.jobs.values() if j.status.value == "RUNNING")
            queued_jobs = sum(1 for j in container.jobs.values() if j.status.value == "QUEUED")
            pending_jobs = sum(1 for j in container.jobs.values() if j.status.value == "PENDING_APPROVAL")
            success_jobs = sum(1 for j in container.jobs.values() if j.status.value == "SUCCESS")
            failed_jobs = sum(1 for j in container.jobs.values() if j.status.value == "FAILED")

        uptime = time.time() - SERVER_START_TIME
        lines = [
            "# HELP vulcan_uptime_seconds System process uptime in seconds.",
            "# TYPE vulcan_uptime_seconds gauge",
            f"vulcan_uptime_seconds {uptime:.2f}",
            "# HELP vulcan_catalog_items_total Total playbooks registered in the catalog.",
            "# TYPE vulcan_catalog_items_total gauge",
            f"vulcan_catalog_items_total {catalog_size}",
            "# HELP vulcan_jobs_total Total execution jobs in the control plane by status.",
            "# TYPE vulcan_jobs_total gauge",
            f'vulcan_jobs_total{{status="RUNNING"}} {running_jobs}',
            f'vulcan_jobs_total{{status="QUEUED"}} {queued_jobs}',
            f'vulcan_jobs_total{{status="PENDING_APPROVAL"}} {pending_jobs}',
            f'vulcan_jobs_total{{status="SUCCESS"}} {success_jobs}',
            f'vulcan_jobs_total{{status="FAILED"}} {failed_jobs}',
            f'vulcan_jobs_total{{status="ALL"}} {jobs_count}',
            "",
            "# HELP vulcan_http_requests_total Total incoming HTTP requests handled by the control plane (RED Rate/Errors).",
            "# TYPE vulcan_http_requests_total counter",
        ]
        if _REQUEST_COUNTS:
            for (m, sc, ep), count in sorted(_REQUEST_COUNTS.items()):
                lines.append(f'vulcan_http_requests_total{{method="{m}",status="{sc}",endpoint="{ep}"}} {count}')
        else:
            lines.append('vulcan_http_requests_total{method="GET",status="200",endpoint="/metrics"} 0')

        lines.extend([
            "",
            "# HELP vulcan_http_request_duration_seconds_sum Total request latency sum in seconds (RED Duration).",
            "# TYPE vulcan_http_request_duration_seconds_sum counter",
        ])
        if _REQUEST_DURATION_SUM:
            for (m, ep), dur in sorted(_REQUEST_DURATION_SUM.items()):
                lines.append(f'vulcan_http_request_duration_seconds_sum{{method="{m}",endpoint="{ep}"}} {dur:.4f}')
        else:
            lines.append('vulcan_http_request_duration_seconds_sum{method="GET",endpoint="/metrics"} 0.0000')

        return "\n".join(lines) + "\n"

    app.include_router(router)
    app.include_router(curation_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    return app


app = create_app()
