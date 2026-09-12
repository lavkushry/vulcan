"""
Project Vulcan: Distributed Chat Session Repository Tests (CHAT-03)
Validates:
1. ChatTurn & ChatSession domain serialization and immutability.
2. IChatSessionRepository contract: create, append turns, retrieve, list by user, delete.
3. Redis caching layer: fast-path rehydration (<10ms), key formats, TTL 7200s enforcement.
4. REST API routes (/api/v1/chat/sessions and /turns).
"""
import time
import uuid
import pytest
from unittest.mock import MagicMock, ANY
from fastapi.testclient import TestClient

from app.domain.chat_entities import ChatSession, ChatTurn
from app.adapters.redis_chat_repository import RedisChatSessionRepository, DEFAULT_SESSION_TTL_SECONDS
from app.api.server import create_app
from app.api.routes import container


class TestChatEntities:
    """Validates domain models for multi-turn conversational history."""

    def test_turn_serialization_roundtrip(self):
        turn_id = f"turn-{uuid.uuid4().hex[:8]}"
        turn = ChatTurn(
            turn_id=turn_id,
            session_id="sess-001",
            turn_index=0,
            role="user",
            content="renew ssl cert on f5-edge-01.bank.com for 90 days",
            intent_state="READY",
            catalog_identifier="net-f5-cert-renew",
            parameters={"target_host": "f5-edge-01.bank.com", "validity_days": 90},
            token_usage=320,
            latency_ms=45.2
        )
        d = turn.to_dict()
        assert d["turn_id"] == turn_id
        assert d["role"] == "user"
        assert d["parameters"]["validity_days"] == 90

        restored = ChatTurn.from_dict(d)
        assert restored.turn_id == turn.turn_id
        assert restored.role == turn.role
        assert restored.catalog_identifier == "net-f5-cert-renew"
        assert restored.token_usage == 320

    def test_session_serialization_roundtrip(self):
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            user_id="eng.alice",
            title="F5 SSL Cert Renewal"
        )
        t1 = ChatTurn(
            turn_id="turn-1",
            session_id=session_id,
            turn_index=0,
            role="user",
            content="renew cert"
        )
        session.add_turn(t1)

        d = session.to_dict()
        assert d["session_id"] == session_id
        assert d["turn_count"] == 1
        assert len(d["turns"]) == 1

        restored = ChatSession.from_dict(d)
        assert restored.session_id == session_id
        assert len(restored.turns) == 1
        assert restored.turns[0].content == "renew cert"


class TestRedisChatSessionRepository:
    """Tests IChatSessionRepository implementation with memory and mock Redis."""

    def test_create_and_get_session(self):
        repo = RedisChatSessionRepository()
        session = repo.create_session(user_id="eng.alice", title="Database Maintenance")

        assert session.user_id == "eng.alice"
        assert session.title == "Database Maintenance"
        assert len(session.turns) == 0

        # Retrieve session
        fetched = repo.get_session(session.session_id)
        assert fetched is not None
        assert fetched.session_id == session.session_id
        assert fetched.title == "Database Maintenance"

    def test_append_turns_and_sequence(self):
        repo = RedisChatSessionRepository()
        session = repo.create_session(user_id="lead.bob", title="Patching Session")

        t0 = ChatTurn(
            turn_id="turn-0",
            session_id=session.session_id,
            turn_index=0,
            role="user",
            content="Patch RHEL 9 kernel on srv-app-01"
        )
        repo.append_turn(session.session_id, t0)

        t1 = ChatTurn(
            turn_id="turn-1",
            session_id=session.session_id,
            turn_index=1,
            role="assistant",
            content="Identified sec-linux-kernel-patch. Ready to execute.",
            intent_state="READY",
            catalog_identifier="sec-linux-kernel-patch"
        )
        repo.append_turn(session.session_id, t1)

        fetched = repo.get_session(session.session_id)
        assert len(fetched.turns) == 2
        assert fetched.turns[0].turn_index == 0
        assert fetched.turns[0].role == "user"
        assert fetched.turns[1].turn_index == 1
        assert fetched.turns[1].role == "assistant"

        # Test get_turns limit
        turns = repo.get_turns(session.session_id, limit=1)
        assert len(turns) == 1
        assert turns[0].turn_id == "turn-1"

    def test_list_sessions_for_user_ordering(self):
        repo = RedisChatSessionRepository()
        s1 = repo.create_session(user_id="eng.alice", title="Session 1")
        time.sleep(0.01)
        s2 = repo.create_session(user_id="eng.alice", title="Session 2")
        s_other = repo.create_session(user_id="lead.bob", title="Bob Session")

        alice_sessions = repo.list_sessions_for_user("eng.alice")
        assert len(alice_sessions) == 2
        # Most recent session first
        assert alice_sessions[0].session_id == s2.session_id
        assert alice_sessions[1].session_id == s1.session_id

        bob_sessions = repo.list_sessions_for_user("lead.bob")
        assert len(bob_sessions) == 1
        assert bob_sessions[0].session_id == s_other.session_id

    def test_delete_session(self):
        repo = RedisChatSessionRepository()
        session = repo.create_session(user_id="eng.alice", title="To Delete")
        sid = session.session_id

        assert repo.get_session(sid) is not None
        deleted = repo.delete_session(sid)
        assert deleted is True
        assert repo.get_session(sid) is None
        assert len(repo.list_sessions_for_user("eng.alice")) == 0

    def test_redis_fast_path_and_ttl_enforcement(self):
        """Validates that Redis caching sets keys with 7200s TTL and delivers sub-10ms retrieval."""
        mock_redis = MagicMock()
        repo = RedisChatSessionRepository(redis_client=mock_redis, ttl_seconds=DEFAULT_SESSION_TTL_SECONDS)

        # 1. Create session writes to Redis with TTL
        session = repo.create_session(user_id="eng.alice", title="Redis Session")
        sid = session.session_id

        mock_redis.set.assert_called_with(
            f"vulcan:chat:session:{sid}:meta",
            ANY,
            ex=7200
        )
        mock_redis.zadd.assert_called()

        # 2. Append turn pushes to Redis turns list and refreshes TTL
        turn = ChatTurn(
            turn_id="turn-r1",
            session_id=sid,
            turn_index=0,
            role="user",
            content="Test query"
        )
        repo.append_turn(sid, turn)
        mock_redis.rpush.assert_called()
        mock_redis.expire.assert_called_with(f"vulcan:chat:session:{sid}:turns", 7200)

        # 3. Simulate cache hit on get_session
        import json
        mock_redis.get.return_value = json.dumps(session.to_dict(include_turns=False))
        mock_redis.lrange.return_value = [json.dumps(turn.to_dict())]

        t0 = time.perf_counter()
        cached_session = repo.get_session(sid)
        rehydrate_time_ms = (time.perf_counter() - t0) * 1000

        assert cached_session is not None
        assert cached_session.session_id == sid
        assert len(cached_session.turns) == 1
        assert rehydrate_time_ms < 10.0, f"Rehydration exceeded 10ms budget: {rehydrate_time_ms:.2f}ms"


class TestChatRestApi:
    """Validates /api/v1/chat REST endpoints."""

    @pytest.fixture
    def client(self):
        app = create_app()
        c = TestClient(app)
        c.headers.update({"Authorization": "Bearer vlc_test_bob"})
        return c

    def test_chat_session_rest_lifecycle(self, client):
        # 1. Create session via REST
        create_res = client.post("/api/v1/chat/sessions", json={"title": "REST API Test Session", "user_id": "eng.alice"})
        assert create_res.status_code == 200
        session_data = create_res.json()["session"]
        sid = session_data["session_id"]
        assert sid is not None
        assert session_data["title"] == "REST API Test Session"

        # 2. List sessions
        list_res = client.get("/api/v1/chat/sessions?user_id=eng.alice")
        assert list_res.status_code == 200
        sessions = list_res.json()
        assert any(s["session_id"] == sid for s in sessions)

        # 3. Append conversational turn via REST
        turn_payload = {
            "content": "Renew SSL certificate on f5-edge-01.bank.com for 90 days",
            "ambient_params": {"targetHost": "f5-edge-01.bank.com"}
        }
        turn_res = client.post(f"/api/v1/chat/sessions/{sid}/turns", json=turn_payload)
        assert turn_res.status_code == 200
        turn_body = turn_res.json()
        assert turn_body["session_id"] == sid
        assert turn_body["user_turn"]["content"] == turn_payload["content"]
        assert "assistant_turn" in turn_body
        assert turn_body["intent_status"] in ("READY", "NEEDS_INPUT", "DISAMBIGUATION", "REJECTED")

        # 4. Get full session with turns
        get_res = client.get(f"/api/v1/chat/sessions/{sid}")
        assert get_res.status_code == 200
        full_session = get_res.json()
        assert len(full_session["turns"]) == 2  # user + assistant turns

        # 5. Delete session
        del_res = client.delete(f"/api/v1/chat/sessions/{sid}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True

        # Verify 404 on deleted session
        get_deleted = client.get(f"/api/v1/chat/sessions/{sid}")
        assert get_deleted.status_code == 404
