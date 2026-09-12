"""
Project Vulcan: Distributed Conversational Chat REST Endpoints (CHAT-03)
Author: Alex Xu & Jordan Walke
Exposes multi-turn session lifecycle and conversational turn endpoints:
- Session creation, retrieval, and deletion with UUIDv4.
- Turn appending integrated with IntentResolver and tokenomics.
- Correlation ID and User ID propagation.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.routes import container
from app.domain.chat_entities import ChatSession, ChatTurn

chat_router = APIRouter(prefix="/chat", tags=["Conversational Chat"])


class CreateSessionRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Operator user identifier (e.g. eng.alice)")
    title: Optional[str] = Field(default="New Automation Session", description="Session title or intent summary")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Session context metadata")


class AppendTurnRequest(BaseModel):
    content: str = Field(..., description="Natural language prompt or operator message")
    ambient_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Ambient context (targetHost, environment)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional client telemetry")


def _get_current_user(request: Request, fallback: str = "eng.alice") -> str:
    """Extracts authenticated username from request state or fallback."""
    user = getattr(request.state, "user", None)
    if user and isinstance(user, str):
        return user
    return fallback


@chat_router.get("/sessions")
def list_sessions(
    request: Request,
    user_id: Optional[str] = Query(None, description="Optional filter by operator user ID"),
    limit: int = Query(20, ge=1, le=100)
):
    """Lists recent multi-turn chat sessions for an operator."""
    current_user = user_id or _get_current_user(request)
    repo = container.chat_session_repo
    sessions = repo.list_sessions_for_user(current_user, limit=limit)
    return [s.to_dict(include_turns=False) for s in sessions]


@chat_router.post("/sessions")
def create_session(request: Request, req: CreateSessionRequest):
    """Creates a new distributed conversational session (UUIDv4)."""
    user_id = req.user_id or _get_current_user(request)
    repo = container.chat_session_repo
    session_id = str(uuid.uuid4())
    session = repo.create_session(
        user_id=user_id,
        session_id=session_id,
        title=req.title,
        metadata=req.metadata
    )
    return {
        "status": "SUCCESS",
        "session": session.to_dict(include_turns=True)
    }


@chat_router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Retrieves an existing chat session and all historical turns (<10ms rehydration)."""
    repo = container.chat_session_repo
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Chat session '{session_id}' not found.")
    return session.to_dict(include_turns=True)


@chat_router.post("/sessions/{session_id}/turns")
def append_turn(session_id: str, req: AppendTurnRequest, request: Request):
    """
    Appends an operator turn to a session, invokes IntentResolver,
    records assistant response with tokenomics, and persists to distributed store.
    """
    repo = container.chat_session_repo
    session = repo.get_session(session_id)
    user_id = session.user_id if session else _get_current_user(request)

    if not session:
        session = repo.create_session(user_id=user_id, session_id=session_id)

    turn_start = time.perf_counter()

    # 1. Record operator turn
    user_turn = ChatTurn(
        turn_id=f"turn-usr-{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        turn_index=len(session.turns),
        role="user",
        content=req.content,
        metadata={"ambient_params": req.ambient_params or {}, **(req.metadata or {})}
    )
    repo.append_turn(session_id, user_turn)

    # 2. Invoke Intent Resolver
    intent_res = container.intent_resolver.resolve(req.content, req.ambient_params)
    latency_ms = round((time.perf_counter() - turn_start) * 1000, 2)

    cat_id = intent_res.catalog_item.identifier if intent_res.catalog_item else None
    params = intent_res.extracted_parameters or {}

    # Format assistant message
    if intent_res.status == "READY":
        asst_msg = f"Ready to launch **{intent_res.catalog_item.name}**."
    elif intent_res.status == "NEEDS_INPUT":
        asst_msg = f"Identified playbook **{intent_res.catalog_item.name}**, but missing required parameters: {', '.join(intent_res.missing_fields)}."
    elif intent_res.status == "DISAMBIGUATION":
        cands = [c.name for c in (intent_res.disambiguation_candidates or [])]
        asst_msg = f"Multiple matching playbooks found: {', '.join(cands)}."
    elif intent_res.status == "SERVICE_UNAVAILABLE":
        asst_msg = intent_res.refusal_reason or "AI service temporarily unavailable."
    else:
        asst_msg = intent_res.refusal_reason or "Request does not match any approved catalog playbooks."

    # 3. Record assistant turn
    asst_turn = ChatTurn(
        turn_id=f"turn-ast-{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        turn_index=len(session.turns) + 1,
        role="assistant",
        content=asst_msg,
        intent_state=intent_res.status,
        catalog_identifier=cat_id,
        parameters=params,
        token_usage=getattr(intent_res, "tokens_used", None),
        latency_ms=latency_ms,
        metadata={
            "missing_fields": intent_res.missing_fields,
            "refusal_reason": intent_res.refusal_reason,
            "tokens_used": getattr(intent_res, "tokens_used", None)
        }
    )
    repo.append_turn(session_id, asst_turn)

    return {
        "session_id": session_id,
        "user_turn": user_turn.to_dict(),
        "assistant_turn": asst_turn.to_dict(),
        "intent_status": intent_res.status,
        "catalog_identifier": cat_id,
        "parameters": params,
        "missing_fields": intent_res.missing_fields
    }


@chat_router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Deletes a chat session and historical turns."""
    repo = container.chat_session_repo
    deleted = repo.delete_session(session_id)
    return {"status": "SUCCESS", "session_id": session_id, "deleted": deleted}
