"""
Project Vulcan: External Resources REST API & Enterprise RBAC Controller (M5 / R5 / R6)
Author: Alex Xu & Uncle Bob
Implements:
1. RESTful CRUD endpoints for external resource management.
2. Enterprise RBAC: Platform Admin mutations; Operator/Auditor read-only inspection.
3. Zero-Raw-Secrets reference masking for non-admin callers.
4. Real-time connection probes, dynamic deployment discovery, and sync triggers.
5. Telemetry & Merkle audit logging integration.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.adapters.providers.provider_registry import ProviderRegistry
from app.domain.external_resource_entities import (
    AuthMode,
    ExternalResource,
    ExternalResourceHealth,
    HealthStatus,
    ResourceCategory,
    ResourceEnvironment,
)
from app.domain.roles_and_policies import UserRole

logger = logging.getLogger("vulcan.api.external_resources")

router = APIRouter(prefix="/external-resources", tags=["External Resources"])

USER_ROLE_MAP: Dict[str, UserRole] = {
    "admin.dave": UserRole.PLATFORM_ADMIN,
    "system.admin": UserRole.PLATFORM_ADMIN,
    "local.dev": UserRole.PLATFORM_ADMIN,
    "sec.carol": UserRole.SECURITY_ADMIN,
    "lead.bob": UserRole.APPROVING_LEAD,
    "eng.alice": UserRole.OPERATOR,
    "audit.emma": UserRole.AUDITOR,
}


def _get_user_and_role(request: Request) -> tuple[str, UserRole]:
    """Resolves authenticated username and RBAC role."""
    user_id = getattr(request.state, "user_id", None) or getattr(request.state, "user", None) or "anonymous"
    role = USER_ROLE_MAP.get(user_id, UserRole.OPERATOR)
    if user_id in ("system.admin", "admin.dave", "local.dev"):
        role = UserRole.PLATFORM_ADMIN
    return user_id, role


def _require_platform_admin(request: Request) -> str:
    """Enforces that the caller holds PLATFORM_ADMIN role for mutations (R6)."""
    user_id, role = _get_user_and_role(request)
    if role != UserRole.PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Insufficient permissions. User '{user_id}' with role '{role.value}' cannot mutate external resources. Platform Admin role required."
        )
    return user_id


def _get_repo(request: Request):
    """Retrieves repository from app container or singleton fallback."""
    container = getattr(request.app.state, "container", None)
    if container and hasattr(container, "external_resource_repo"):
        return container.external_resource_repo
    from app.adapters.postgres_external_resource_repository import PostgresExternalResourceRepository
    return PostgresExternalResourceRepository()


# -----------------------------------------------------------------------------
# PYDANTIC SCHEMAS
# -----------------------------------------------------------------------------

class CreateExternalResourcePayload(BaseModel):
    resource_id: str = Field(..., description="Unique alphanumeric identifier (e.g. res-foundry-prod-01)")
    provider: Optional[str] = Field("generic", description="Provider connector key (e.g. microsoft_foundry, github)")
    category: Optional[str] = Field("AI & Models", description="Functional category")
    display_name: Optional[str] = Field(None, description="Human-readable title")
    environment: Optional[str] = Field("PROD", description="Deployment tier (PROD, STAGE, DEV)")
    endpoint: Optional[str] = Field("", description="Remote service base URL")
    auth_mode: Optional[str] = Field("API_KEY", description="Authentication strategy")
    enabled: Optional[bool] = Field(True, description="Active status")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Provider configuration")
    secret_refs: Optional[Dict[str, str]] = Field(default_factory=dict, description="Vault pointer references")


class UpdateExternalResourcePayload(BaseModel):
    display_name: Optional[str] = None
    category: Optional[str] = None
    environment: Optional[str] = None
    endpoint: Optional[str] = None
    auth_mode: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    secret_refs: Optional[Dict[str, str]] = None


# -----------------------------------------------------------------------------
# REST ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("", summary="List all registered external resources")
def list_external_resources(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    environment: Optional[str] = Query(None, description="Filter by environment (PROD, STAGE, DEV)"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled state"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Lists external resources. Non-admins receive masked secret references (********)."""
    user_id, role = _get_user_and_role(request)
    is_admin = (role == UserRole.PLATFORM_ADMIN)

    repo = _get_repo(request)
    items = repo.list_all(
        category=category,
        environment=environment,
        enabled=enabled,
        limit=limit,
        offset=offset,
    )
    return [item.to_dict(mask_secrets=not is_admin, is_admin=is_admin) for item in items]


@router.get("/providers", summary="List available external resource connector types")
def list_available_providers():
    """Returns metadata for all 16 registered enterprise connectors."""
    return ProviderRegistry.list_providers()


@router.get("/{resource_id}", summary="Get single external resource details")
def get_external_resource(request: Request, resource_id: str):
    """Retrieves an external resource by ID."""
    user_id, role = _get_user_and_role(request)
    is_admin = (role == UserRole.PLATFORM_ADMIN)

    repo = _get_repo(request)
    item = repo.get_by_id(resource_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )
    return item.to_dict(mask_secrets=not is_admin, is_admin=is_admin)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a new external resource")
def create_external_resource(request: Request, payload: CreateExternalResourcePayload):
    """Creates a new external resource. Restricted to Platform Admins."""
    user_id = _require_platform_admin(request)
    repo = _get_repo(request)

    existing = repo.get_by_id(payload.resource_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"External resource '{payload.resource_id}' already exists."
        )

    try:
        resource = ExternalResource(
            resource_id=payload.resource_id,
            provider=payload.provider,
            category=payload.category or "AI & Models",
            display_name=payload.display_name or payload.resource_id,
            environment=payload.environment or "PROD",
            endpoint=payload.endpoint or "",
            auth_mode=payload.auth_mode or "API_KEY",
            enabled=payload.enabled if payload.enabled is not None else True,
            config=payload.config or {},
            secret_refs=payload.secret_refs or {},
            created_by=user_id,
            updated_by=user_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {e}"
        )

    saved = repo.save(resource, actor=user_id, reason="Created via REST API")
    return saved.to_dict(mask_secrets=False, is_admin=True)


@router.put("/{resource_id}", summary="Update an external resource")
def update_external_resource(request: Request, resource_id: str, payload: UpdateExternalResourcePayload):
    """Updates configuration or metadata. Restricted to Platform Admins."""
    user_id = _require_platform_admin(request)
    repo = _get_repo(request)

    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )

    if payload.display_name is not None:
        res.display_name = payload.display_name
    if payload.category is not None:
        res.category = ResourceCategory.from_string(payload.category)
    if payload.environment is not None:
        res.environment = ResourceEnvironment.from_string(payload.environment)
    if payload.endpoint is not None:
        res.endpoint = payload.endpoint
    if payload.auth_mode is not None:
        res.auth_mode = AuthMode.from_string(payload.auth_mode)
    if payload.enabled is not None:
        res.enabled = payload.enabled

    if payload.config is not None or payload.secret_refs is not None:
        new_config = dict(res.config) if payload.config is None else payload.config
        new_secrets = dict(res.secret_refs) if payload.secret_refs is None else payload.secret_refs
        try:
            res.update_configuration(config=new_config, secret_refs=new_secrets, actor=user_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Update validation failed: {e}"
            )

    saved = repo.save(res, actor=user_id, reason="Updated via REST API")
    return saved.to_dict(mask_secrets=False, is_admin=True)


@router.delete("/{resource_id}", summary="Delete an external resource")
def delete_external_resource(request: Request, resource_id: str):
    """Deletes an external resource. Restricted to Platform Admins."""
    user_id = _require_platform_admin(request)
    repo = _get_repo(request)

    existing = repo.get_by_id(resource_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )

    deleted = repo.delete(resource_id, actor=user_id)
    return {"ok": deleted, "resource_id": resource_id, "message": f"Resource '{resource_id}' deleted."}


@router.post("/{resource_id}/enable", summary="Enable an external resource")
def enable_external_resource(request: Request, resource_id: str):
    """Enables an external resource. Restricted to Platform Admins."""
    user_id = _require_platform_admin(request)
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"External resource '{resource_id}' not found.")
    res.enabled = True
    saved = repo.save(res, actor=user_id, reason="Enabled via REST API")
    return saved.to_dict(mask_secrets=False, is_admin=True)


@router.post("/{resource_id}/disable", summary="Disable an external resource")
def disable_external_resource(request: Request, resource_id: str):
    """Disables an external resource. Restricted to Platform Admins."""
    user_id = _require_platform_admin(request)
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"External resource '{resource_id}' not found.")
    res.enabled = False
    saved = repo.save(res, actor=user_id, reason="Disabled via REST API")
    return saved.to_dict(mask_secrets=False, is_admin=True)



@router.post("/{resource_id}/test", summary="Execute live network reachability and authentication probe")
def test_external_resource_connection(request: Request, resource_id: str):
    """Triggers outbound network test and records telemetry. Restricted to Platform Admins."""
    user_id = _require_platform_admin(request)
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )

    provider = ProviderRegistry.get_provider(res.provider)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No provider driver found for '{res.provider}'."
        )

    test_res = provider.test_connection(res.config, res.secret_refs, endpoint=res.endpoint)

    # Record health telemetry
    health_record = ExternalResourceHealth(
        resource_id=resource_id,
        status=test_res.status,
        latency_ms=test_res.latency_ms,
        http_status=test_res.http_status,
        message=test_res.message,
        diagnostics=test_res.diagnostics,
    )
    repo.record_health(health_record)

    out = test_res.to_dict()
    # Strip any potential sensitive tokens from payload
    out.pop("authorization", None)
    out.pop("Authorization", None)
    return out


@router.get("/{resource_id}/deployments", summary="Discover model deployments dynamically")
def discover_resource_deployments(request: Request, resource_id: str):
    """Dynamically enumerates available deployments (for AI providers like Microsoft Foundry)."""
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )

    provider = ProviderRegistry.get_provider(res.provider)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No provider driver found for '{res.provider}'."
        )

    caps = provider.discover_capabilities(res.config, res.secret_refs, endpoint=res.endpoint)
    return {
        "resource_id": resource_id,
        "provider": res.provider,
        "deployments": caps.deployments,
        "models": caps.models,
        "tools": caps.tools,
        "agents": caps.agents,
        "discovered_at": caps.discovered_at.isoformat() if hasattr(caps.discovered_at, "isoformat") else str(caps.discovered_at),
    }


@router.get("/{resource_id}/models", summary="List model endpoints for AI provider")
def get_resource_models(request: Request, resource_id: str):
    """Lists discovered models (for AI providers like Microsoft Foundry)."""
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"External resource '{resource_id}' not found.")
    provider = ProviderRegistry.get_provider(res.provider)
    if not provider:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"No provider driver found for '{res.provider}'.")
    caps = provider.discover_capabilities(res.config, res.secret_refs, endpoint=res.endpoint)
    return {"resource_id": resource_id, "provider": res.provider, "models": caps.models}


@router.get("/{resource_id}/agents", summary="List agents for AI provider")
def get_resource_agents(request: Request, resource_id: str):
    """Lists discovered agents (for AI providers like Microsoft Foundry)."""
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"External resource '{resource_id}' not found.")
    provider = ProviderRegistry.get_provider(res.provider)
    if not provider:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"No provider driver found for '{res.provider}'.")
    caps = provider.discover_capabilities(res.config, res.secret_refs, endpoint=res.endpoint)
    return {"resource_id": resource_id, "provider": res.provider, "agents": caps.agents}



@router.get("/{resource_id}/capabilities", summary="Get discovered capabilities of resource")
def get_resource_capabilities(request: Request, resource_id: str):
    """Retrieves full capability payload for resource."""
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )
    provider = ProviderRegistry.get_provider(res.provider)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No provider driver found for '{res.provider}'."
        )
    caps = provider.discover_capabilities(res.config, res.secret_refs, endpoint=res.endpoint)
    return caps.to_dict()


@router.get("/{resource_id}/health", summary="Get health check history")
def get_resource_health_history(request: Request, resource_id: str, limit: int = Query(20, ge=1, le=100)):
    """Returns chronological telemetry and health probe results."""
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )
    history = repo.get_health_history(resource_id, limit=limit)
    return [h.to_dict() for h in history]


@router.post("/{resource_id}/sync", summary="Trigger synchronization cycle")
def sync_external_resource(request: Request, resource_id: str):
    """Executes live sync for the external resource. Restricted to Platform Admins."""
    user_id = _require_platform_admin(request)
    repo = _get_repo(request)
    res = repo.get_by_id(resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External resource '{resource_id}' not found."
        )
    provider = ProviderRegistry.get_provider(res.provider)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No provider driver found for '{res.provider}'."
        )
    result = provider.sync(resource_id, res.config, res.secret_refs)
    return result.to_dict()
