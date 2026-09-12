"""
Project Vulcan: Conversational Chat Domain Entities (CHAT-03)
Author: Alex Xu & Uncle Bob
Clean Architecture domain models for multi-turn conversational sessions and turns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


@dataclass(frozen=True)
class ChatTurn:
    """A single conversational turn between human operator and Vulcan copilot."""
    turn_id: str
    session_id: str
    turn_index: int
    role: str  # "user" | "assistant" | "system"
    content: str
    intent_state: Optional[str] = None  # "READY", "NEEDS_INPUT", "DISAMBIGUATION", "REJECTED"
    catalog_identifier: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    token_usage: Optional[int] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "role": self.role,
            "content": self.content,
            "intent_state": self.intent_state,
            "catalog_identifier": self.catalog_identifier,
            "parameters": self.parameters,
            "token_usage": self.token_usage,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChatTurn:
        created = data.get("created_at")
        if isinstance(created, str):
            try:
                created_dt = datetime.fromisoformat(created)
            except Exception:
                created_dt = datetime.now(timezone.utc)
        elif isinstance(created, datetime):
            created_dt = created
        else:
            created_dt = datetime.now(timezone.utc)

        return cls(
            turn_id=data.get("turn_id") or f"turn-{uuid.uuid4().hex[:12]}",
            session_id=data.get("session_id", ""),
            turn_index=int(data.get("turn_index", 0)),
            role=data.get("role", "user"),
            content=data.get("content", ""),
            intent_state=data.get("intent_state"),
            catalog_identifier=data.get("catalog_identifier"),
            parameters=data.get("parameters") or {},
            token_usage=data.get("token_usage"),
            latency_ms=data.get("latency_ms"),
            metadata=data.get("metadata") or {},
            created_at=created_dt
        )


@dataclass
class ChatSession:
    """An operator conversational session aggregate root."""
    session_id: str
    user_id: str
    title: str = "New Session"
    turns: List[ChatTurn] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_turn(self, turn: ChatTurn) -> None:
        self.turns.append(turn)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self, include_turns: bool = True) -> Dict[str, Any]:
        d = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "title": self.title,
            "turn_count": len(self.turns),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else str(self.updated_at)
        }
        if include_turns:
            d["turns"] = [t.to_dict() for t in self.turns]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChatSession:
        created = data.get("created_at")
        if isinstance(created, str):
            try:
                created_dt = datetime.fromisoformat(created)
            except Exception:
                created_dt = datetime.now(timezone.utc)
        else:
            created_dt = created or datetime.now(timezone.utc)

        updated = data.get("updated_at")
        if isinstance(updated, str):
            try:
                updated_dt = datetime.fromisoformat(updated)
            except Exception:
                updated_dt = datetime.now(timezone.utc)
        else:
            updated_dt = updated or datetime.now(timezone.utc)

        raw_turns = data.get("turns", [])
        turns = [ChatTurn.from_dict(t) if isinstance(t, dict) else t for t in raw_turns]

        return cls(
            session_id=data.get("session_id") or str(uuid.uuid4()),
            user_id=data.get("user_id", "anonymous"),
            title=data.get("title", "New Session"),
            turns=turns,
            metadata=data.get("metadata") or {},
            created_at=created_dt,
            updated_at=updated_dt
        )
