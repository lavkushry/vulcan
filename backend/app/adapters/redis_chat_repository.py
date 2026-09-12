"""
Project Vulcan: Distributed Redis-Backed Chat Session Repository (CHAT-03)
Author: Alex Xu (Distributed Systems Lead)
Guarantees conversational state persistence across pods, workers, and browser reloads:
- Sub-10ms Redis caching layer with 7200s TTL.
- Durable PostgreSQL backing tables (chat_sessions, chat_turns).
- Hermetic thread-safe memory fallback for offline/isolated execution.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.domain.chat_entities import ChatSession, ChatTurn
from app.ports.repositories import IChatSessionRepository

logger = logging.getLogger("vulcan.chat_repo")

DEFAULT_SESSION_TTL_SECONDS = 7200  # 2 hours per CHAT-03 spec


class RedisChatSessionRepository(IChatSessionRepository):
    """
    Two-tier distributed repository for multi-turn conversational chat sessions:
    1. Fast-path Redis Cache (TTL 7200s).
    2. Durable PostgreSQL Store (chat_sessions, chat_turns).
    3. Thread-safe in-memory fallback if external infra is unavailable.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        db_url: Optional[str] = None,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
    ):
        self.redis = redis_client
        self.db_url = db_url
        self.ttl = ttl_seconds

        # In-memory storage fallback
        self._lock = threading.RLock()
        self._memory_sessions: Dict[str, ChatSession] = {}
        self._memory_user_index: Dict[str, List[str]] = {}

    def _redis_meta_key(self, session_id: str) -> str:
        return f"vulcan:chat:session:{session_id}:meta"

    def _redis_turns_key(self, session_id: str) -> str:
        return f"vulcan:chat:session:{session_id}:turns"

    def _redis_user_key(self, user_id: str) -> str:
        return f"vulcan:chat:user:{user_id}:sessions"

    # -------------------------------------------------------------------------
    # PostgreSQL Helper Methods
    # -------------------------------------------------------------------------

    def _get_pg_conn(self):
        if not self.db_url:
            return None
        try:
            import psycopg
            return psycopg.connect(self.db_url, autocommit=True)
        except Exception as e:
            logger.debug("PostgreSQL connection unavailable for chat repo: %s", e)
            return None

    def _pg_save_session(self, session: ChatSession) -> None:
        conn = self._get_pg_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, title, metadata, created_at, updated_at)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    (
                        session.session_id,
                        session.user_id,
                        session.title,
                        json.dumps(session.metadata),
                        session.created_at,
                        session.updated_at
                    )
                )
        except Exception as e:
            logger.warning("PostgreSQL save session failed: %s", e)
        finally:
            conn.close()

    def _pg_save_turn(self, turn: ChatTurn) -> None:
        conn = self._get_pg_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_turns (
                        turn_id, session_id, turn_index, role, content,
                        intent_state, catalog_identifier, parameters,
                        token_usage, latency_ms, metadata, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s::jsonb,
                        %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT (turn_id) DO NOTHING;
                    """,
                    (
                        turn.turn_id,
                        turn.session_id,
                        turn.turn_index,
                        turn.role,
                        turn.content,
                        turn.intent_state,
                        turn.catalog_identifier,
                        json.dumps(turn.parameters),
                        turn.token_usage,
                        turn.latency_ms,
                        json.dumps(turn.metadata),
                        turn.created_at
                    )
                )
                # Update session updated_at in PG
                cur.execute(
                    "UPDATE chat_sessions SET updated_at = %s WHERE session_id = %s;",
                    (turn.created_at, turn.session_id)
                )
        except Exception as e:
            logger.warning("PostgreSQL save turn failed: %s", e)
        finally:
            conn.close()

    def _pg_load_session(self, session_id: str) -> Optional[ChatSession]:
        conn = self._get_pg_conn()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, user_id, title, metadata, created_at, updated_at FROM chat_sessions WHERE session_id = %s;",
                    (session_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None

                cur.execute(
                    """
                    SELECT turn_id, session_id, turn_index, role, content,
                           intent_state, catalog_identifier, parameters,
                           token_usage, latency_ms, metadata, created_at
                    FROM chat_turns
                    WHERE session_id = %s
                    ORDER BY turn_index ASC;
                    """,
                    (session_id,)
                )
                turn_rows = cur.fetchall()
                turns = []
                for tr in turn_rows:
                    turns.append(ChatTurn(
                        turn_id=tr[0],
                        session_id=tr[1],
                        turn_index=tr[2],
                        role=tr[3],
                        content=tr[4],
                        intent_state=tr[5],
                        catalog_identifier=tr[6],
                        parameters=tr[7] if isinstance(tr[7], dict) else json.loads(tr[7] or "{}"),
                        token_usage=tr[8],
                        latency_ms=tr[9],
                        metadata=tr[10] if isinstance(tr[10], dict) else json.loads(tr[10] or "{}"),
                        created_at=tr[11]
                    ))

                return ChatSession(
                    session_id=row[0],
                    user_id=row[1],
                    title=row[2],
                    turns=turns,
                    metadata=row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                    created_at=row[4],
                    updated_at=row[5]
                )
        except Exception as e:
            logger.warning("PostgreSQL load session failed: %s", e)
            return None
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # IChatSessionRepository Contract Implementation
    # -------------------------------------------------------------------------

    def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        sid = session_id or str(uuid.uuid4())
        session = ChatSession(
            session_id=sid,
            user_id=user_id,
            title=title or "New Session",
            turns=[],
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        # 1. Memory store
        with self._lock:
            self._memory_sessions[sid] = session
            if user_id not in self._memory_user_index:
                self._memory_user_index[user_id] = []
            if sid not in self._memory_user_index[user_id]:
                self._memory_user_index[user_id].insert(0, sid)

        # 2. Redis store
        if self.redis:
            try:
                meta_json = json.dumps(session.to_dict(include_turns=False))
                self.redis.set(self._redis_meta_key(sid), meta_json, ex=self.ttl)
                score = session.updated_at.timestamp()
                self.redis.zadd(self._redis_user_key(user_id), {sid: score})
                self.redis.expire(self._redis_user_key(user_id), self.ttl * 4)
            except Exception as e:
                logger.warning("Redis create session failed: %s", e)

        # 3. PostgreSQL store
        self._pg_save_session(session)

        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        t0 = time.perf_counter()

        # 1. Check Redis Fast Path
        if self.redis:
            try:
                meta_raw = self.redis.get(self._redis_meta_key(session_id))
                if meta_raw:
                    meta_dict = json.loads(meta_raw)
                    turns_raw = self.redis.lrange(self._redis_turns_key(session_id), 0, -1)
                    turns = []
                    for raw in turns_raw:
                        turns.append(ChatTurn.from_dict(json.loads(raw)))
                    meta_dict["turns"] = [t.to_dict() for t in turns]
                    session = ChatSession.from_dict(meta_dict)

                    # Refresh TTL
                    self.redis.expire(self._redis_meta_key(session_id), self.ttl)
                    self.redis.expire(self._redis_turns_key(session_id), self.ttl)

                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    if elapsed_ms > 10.0:
                        logger.warning("ChatSession rehydration took >10ms (%.2f ms)", elapsed_ms)
                    return session
            except Exception as e:
                logger.debug("Redis cache read failed, falling back: %s", e)

        # 2. Check PostgreSQL Persistent Layer
        pg_session = self._pg_load_session(session_id)
        if pg_session:
            # Rehydrate into Redis
            if self.redis:
                try:
                    self.redis.set(self._redis_meta_key(session_id), json.dumps(pg_session.to_dict(include_turns=False)), ex=self.ttl)
                    if pg_session.turns:
                        turn_payloads = [json.dumps(t.to_dict()) for t in pg_session.turns]
                        self.redis.delete(self._redis_turns_key(session_id))
                        self.redis.rpush(self._redis_turns_key(session_id), *turn_payloads)
                        self.redis.expire(self._redis_turns_key(session_id), self.ttl)
                except Exception as e:
                    logger.debug("Redis backfill failed: %s", e)
            return pg_session

        # 3. Check In-Memory Fallback
        with self._lock:
            return self._memory_sessions.get(session_id)

    def append_turn(self, session_id: str, turn: ChatTurn) -> ChatTurn:
        session = self.get_session(session_id)
        if not session:
            # Create on the fly if missing
            session = self.create_session(user_id=getattr(turn, "metadata", {}).get("user_id", "operator"))

        # Fix turn index if necessary
        if turn.turn_index != len(session.turns):
            turn = ChatTurn(
                turn_id=turn.turn_id,
                session_id=session_id,
                turn_index=len(session.turns),
                role=turn.role,
                content=turn.content,
                intent_state=turn.intent_state,
                catalog_identifier=turn.catalog_identifier,
                parameters=turn.parameters,
                token_usage=turn.token_usage,
                latency_ms=turn.latency_ms,
                metadata=turn.metadata,
                created_at=turn.created_at
            )

        session.add_turn(turn)

        # 1. Update in-memory
        with self._lock:
            self._memory_sessions[session_id] = session

        # 2. Update Redis
        if self.redis:
            try:
                turn_json = json.dumps(turn.to_dict())
                self.redis.rpush(self._redis_turns_key(session_id), turn_json)
                self.redis.expire(self._redis_turns_key(session_id), self.ttl)

                # Update session metadata in Redis
                meta_json = json.dumps(session.to_dict(include_turns=False))
                self.redis.set(self._redis_meta_key(session_id), meta_json, ex=self.ttl)

                # Update user index score
                score = session.updated_at.timestamp()
                self.redis.zadd(self._redis_user_key(session.user_id), {session_id: score})
            except Exception as e:
                logger.warning("Redis append turn failed: %s", e)

        # 3. Update PostgreSQL
        self._pg_save_turn(turn)

        return turn

    def get_turns(self, session_id: str, limit: int = 50) -> List[ChatTurn]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.turns[-limit:]

    def list_sessions_for_user(self, user_id: str, limit: int = 20) -> List[ChatSession]:
        session_ids: List[str] = []

        # 1. Try Redis Sorted Set
        if self.redis:
            try:
                members = self.redis.zrevrange(self._redis_user_key(user_id), 0, limit - 1)
                session_ids = [m.decode() if isinstance(m, bytes) else str(m) for m in members]
            except Exception as e:
                logger.debug("Redis list sessions failed: %s", e)

        # 2. Try PostgreSQL if Redis returned nothing
        if not session_ids and self.db_url:
            conn = self._get_pg_conn()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT session_id FROM chat_sessions WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s;",
                            (user_id, limit)
                        )
                        session_ids = [r[0] for r in cur.fetchall()]
                except Exception as e:
                    logger.warning("PostgreSQL list sessions failed: %s", e)
                finally:
                    conn.close()

        # 3. In-memory fallback
        if not session_ids:
            with self._lock:
                session_ids = self._memory_user_index.get(user_id, [])[:limit]

        results = []
        for sid in session_ids:
            s = self.get_session(sid)
            if s:
                results.append(s)
        return results

    def delete_session(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        user_id = session.user_id if session else None

        # 1. Memory
        with self._lock:
            if session_id in self._memory_sessions:
                del self._memory_sessions[session_id]
            if user_id and user_id in self._memory_user_index:
                self._memory_user_index[user_id] = [
                    s for s in self._memory_user_index[user_id] if s != session_id
                ]

        # 2. Redis
        if self.redis:
            try:
                self.redis.delete(self._redis_meta_key(session_id))
                self.redis.delete(self._redis_turns_key(session_id))
                if user_id:
                    self.redis.zrem(self._redis_user_key(user_id), session_id)
            except Exception as e:
                logger.warning("Redis delete session failed: %s", e)

        # 3. PostgreSQL
        conn = self._get_pg_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM chat_sessions WHERE session_id = %s;", (session_id,))
            except Exception as e:
                logger.warning("PostgreSQL delete session failed: %s", e)
            finally:
                conn.close()

        return True
