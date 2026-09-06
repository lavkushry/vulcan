"""
Project Vulcan: FastAPI Server Assembly
Author: Alex Xu & Uncle Bob
Configures lifespan, CORS middleware, WebSocket loop binding, and route registry.
"""
import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.routes import router, container
from app.api.curation_routes import curation_router
from app.api.websockets import ws_hub

SERVER_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set the running event loop on the WebSocket hub for thread-safe worker broadcasts
    loop = asyncio.get_running_loop()
    ws_hub.set_event_loop(loop)
    if hasattr(container, "redis_nodes") and container.redis_nodes:
        ws_hub.set_redis_client(container.redis_nodes[0])
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Project Vulcan: Enterprise Automation Control Plane",
        description="High-reliability banking automation platform OS (PNC Bank Standard)",
        version="1.0.0",
        lifespan=lifespan
    )

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

    # Standardized Consistent Error Envelope (BKND-18)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get("x-vulcan-correlation-id", f"ERR-{uuid.uuid4().hex[:8]}")
        error_code = f"ERR_{exc.status_code}"
        msg = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
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
    def liveness_probe():
        """Kubernetes / Compose container liveness probe."""
        return {
            "status": "ALIVE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": round(time.time() - SERVER_START_TIME, 2)
        }

    # Readiness Probe (INFRA-17)
    @app.get("/ready", tags=["Observability"])
    def readiness_probe():
        """Kubernetes / Compose service readiness probe verifying subsystem health."""
        catalog_ok = len(container.catalog) > 0
        audit_ok = container.audit_logger.verify_chain()
        is_ready = catalog_ok and audit_ok
        status_code = 200 if is_ready else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "READY" if is_ready else "NOT_READY",
                "checks": {
                    "catalog_loaded": catalog_ok,
                    "audit_chain_valid": audit_ok,
                    "lock_manager_active": True
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    # Prometheus Metrics Exporter (INFRA-16)
    @app.get("/metrics", response_class=PlainTextResponse, tags=["Observability"])
    def prometheus_metrics():
        """Prometheus metrics endpoint scrapable by Prometheus / OpenTelemetry."""
        uptime = time.time() - SERVER_START_TIME
        catalog_size = len(container.catalog)
        jobs_count = len(container.jobs)
        running_jobs = sum(1 for j in container.jobs.values() if j.status.value == "RUNNING")
        queued_jobs = sum(1 for j in container.jobs.values() if j.status.value == "QUEUED")
        pending_jobs = sum(1 for j in container.jobs.values() if j.status.value == "PENDING_APPROVAL")
        success_jobs = sum(1 for j in container.jobs.values() if j.status.value == "SUCCESS")
        failed_jobs = sum(1 for j in container.jobs.values() if j.status.value == "FAILED")

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
        ]
        return "\n".join(lines) + "\n"

    app.include_router(router)
    app.include_router(curation_router, prefix="/api/v1")
    return app


app = create_app()
