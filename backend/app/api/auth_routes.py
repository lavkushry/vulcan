"""
Project Vulcan: Authentication & Session Verification Endpoints
Provides honest identity, role derivation, and permission reporting directly
from server-side token validation.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.auth import authenticate_token, load_token_map
from app.domain.roles_and_policies import (
    Permission,
    ROLE_PERMISSIONS,
    ROLE_BADGES,
    USER_ROLE_MAP,
    UserRole,
    resolve_user_role,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


class TokenVerifyRequest(BaseModel):
    token: str = Field(..., description="API token to validate")


def _resolve_user_and_role(user_id: Optional[str]) -> tuple[UserRole, str, List[str]]:
    """Resolves UserRole, badge string, and permission strings for a given user_id."""
    if not user_id:
        return UserRole.OPERATOR, "GUEST", []
    role = resolve_user_role(user_id)
    badge = ROLE_BADGES.get(role, role.value)
    permissions = [p.value for p in ROLE_PERMISSIONS.get(role, [])]
    return role, badge, permissions



def _extract_token_from_request(request: Request) -> Optional[str]:
    """Extracts raw API token from Authorization header or query param."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.headers.get("x-vulcan-api-key") or request.query_params.get("token")


@router.get("/session", summary="Check current session authentication state")
def get_session(request: Request):
    """
    Exempt from mandatory blocking.
    Returns authenticated user profile, real RBAC role, and permissions if a valid token is provided.
    Returns unauthenticated state if token is missing or invalid.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        token = _extract_token_from_request(request)
        if token:
            user_id = authenticate_token(token)

    if not user_id:
        return {
            "authenticated": False,
            "user_id": None,
            "role": None,
            "role_badge": None,
            "permissions": [],
            "status": "unauthenticated",
        }

    role, badge, permissions = _resolve_user_and_role(user_id)
    return {
        "authenticated": True,
        "user_id": user_id,
        "role": role.value,
        "role_badge": badge,
        "permissions": permissions,
        "status": "authenticated",
    }


@router.get("/me", summary="Get authenticated caller details")
def get_current_user(request: Request):
    """
    Requires authentication. Returns 401 if unauthenticated.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        token = _extract_token_from_request(request)
        if token:
            user_id = authenticate_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token. Please sign in.",
        )

    role, badge, permissions = _resolve_user_and_role(user_id)
    return {
        "authenticated": True,
        "user_id": user_id,
        "role": role.value,
        "role_badge": badge,
        "permissions": permissions,
    }


@router.post("/verify-token", summary="Verify token and return authenticated session")
def verify_token(req: TokenVerifyRequest):
    """
    Validates client-supplied token against server token map.
    Returns user details and permissions upon successful validation, or 401 if invalid.
    """
    user_id = authenticate_token(req.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token. Access denied.",
        )

    role, badge, permissions = _resolve_user_and_role(user_id)
    return {
        "authenticated": True,
        "user_id": user_id,
        "role": role.value,
        "role_badge": badge,
        "permissions": permissions,
        "token": req.token,
    }


@router.get("/test-personas", summary="List known personas for test / simulation mode")
def list_test_personas():
    """Returns available test personas with their real roles for local onboarding."""
    return [
        {
            "id": "admin.dave",
            "name": "Dave Admin",
            "role": "PLATFORM_ADMIN",
            "role_badge": "PLATFORM ADMIN",
            "token": "vlc_test_dave_ci_token",
            "description": "Full administrative control, resource mutations, policy management",
        },
        {
            "id": "lead.bob",
            "name": "Bob Lead",
            "role": "APPROVING_LEAD",
            "role_badge": "APPROVING LEAD",
            "token": "vlc_test_bob_ci_token",
            "description": "Dual-control approval authority for high-risk production jobs",
        },
        {
            "id": "sec.carol",
            "name": "Carol Security",
            "role": "SECURITY_ADMIN",
            "role_badge": "SECURITY ADMIN",
            "token": "vlc_test_carol_ci_token",
            "description": "Security review, policy enforcement, Merkle audit verification",
        },
        {
            "id": "eng.alice",
            "name": "Alice Engineer",
            "role": "OPERATOR",
            "role_badge": "OPERATOR",
            "token": "vlc_test_alice_ci_token",
            "description": "Standard engineering operator for routine infrastructure tasks",
        },
    ]
