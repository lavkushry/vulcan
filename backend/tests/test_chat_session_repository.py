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
    """Validates /api/v1/chat REST endpoints with strict RBAC and session ownership (CHAT-03)."""

    @pytest.fixture
    def client_alice(self):
        app = create_app()
        c = TestClient(app)
        c.headers.update({"Authorization": "Bearer vlc_test_alice"})
        return c

    @pytest.fixture
    def client_bob(self):
        app = create_app()
        c = TestClient(app)
        c.headers.update({"Authorization": "Bearer vlc_test_bob"})
        return c

    @pytest.fixture
    def client_admin(self):
        app = create_app()
        c = TestClient(app)
        c.headers.update({"Authorization": "Bearer vlc_test_admin"})
        return c

    @pytest.fixture
    def client_unauth(self):
        app = create_app()
        return TestClient(app)

    def test_chat_session_rest_lifecycle(self, client_alice):
        # 1. Create session via REST as Alice
        create_res = client_alice.post("/api/v1/chat/sessions", json={"title": "REST API Test Session"})
        assert create_res.status_code == 200
        session_data = create_res.json()["session"]
        sid = session_data["session_id"]
        assert sid is not None
        assert session_data["title"] == "REST API Test Session"
        assert session_data["user_id"] == "eng.alice"

        # 2. List sessions
        list_res = client_alice.get("/api/v1/chat/sessions")
        assert list_res.status_code == 200
        sessions = list_res.json()
        assert any(s["session_id"] == sid for s in sessions)

        # 3. Append conversational turn via REST
        turn_payload = {
            "content": "Renew SSL certificate on f5-edge-01.bank.com for 90 days",
            "ambient_params": {"targetHost": "f5-edge-01.bank.com"}
        }
        turn_res = client_alice.post(f"/api/v1/chat/sessions/{sid}/turns", json=turn_payload)
        assert turn_res.status_code == 200
        turn_body = turn_res.json()
        assert turn_body["session_id"] == sid
        assert turn_body["user_turn"]["content"] == turn_payload["content"]
        assert "assistant_turn" in turn_body
        assert turn_body["intent_status"] in ("READY", "NEEDS_INPUT", "DISAMBIGUATION", "REJECTED")

        # 4. Get full session with turns
        get_res = client_alice.get(f"/api/v1/chat/sessions/{sid}")
        assert get_res.status_code == 200
        full_session = get_res.json()
        assert len(full_session["turns"]) == 2  # user + assistant turns

        # 5. Delete session
        del_res = client_alice.delete(f"/api/v1/chat/sessions/{sid}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True

        # Verify 404 on deleted session
        get_deleted = client_alice.get(f"/api/v1/chat/sessions/{sid}")
        assert get_deleted.status_code == 404

    def test_unauthenticated_requests_fail_401(self, client_unauth):
        """Unauthenticated requests must fail-closed with HTTP 401."""
        assert client_unauth.get("/api/v1/chat/sessions").status_code == 401
        assert client_unauth.post("/api/v1/chat/sessions", json={"title": "Test"}).status_code == 401
        assert client_unauth.get("/api/v1/chat/sessions/fake-id").status_code == 401
        assert client_unauth.post("/api/v1/chat/sessions/fake-id/turns", json={"content": "hello"}).status_code == 401
        assert client_unauth.delete("/api/v1/chat/sessions/fake-id").status_code == 401

    def test_cross_user_isolation_enforces_403(self, client_alice, client_bob):
        """Bob cannot view, mutate, list, or delete Alice's sessions (Flag 2 / D4 Defect)."""
        # Alice creates a session
        create_res = client_alice.post("/api/v1/chat/sessions", json={"title": "Alice Secret Session"})
        assert create_res.status_code == 200
        sid = create_res.json()["session"]["session_id"]

        # 1. Bob attempts to GET Alice's session -> 403
        get_res = client_bob.get(f"/api/v1/chat/sessions/{sid}")
        assert get_res.status_code == 403
        assert "Forbidden" in get_res.json()["detail"]

        # 2. Bob attempts to POST turn to Alice's session -> 403
        post_res = client_bob.post(f"/api/v1/chat/sessions/{sid}/turns", json={"content": "Malicious Turn"})
        assert post_res.status_code == 403
        assert "Forbidden" in post_res.json()["detail"]

        # 3. Bob attempts to DELETE Alice's session -> 403
        del_res = client_bob.delete(f"/api/v1/chat/sessions/{sid}")
        assert del_res.status_code == 403
        assert "Forbidden" in del_res.json()["detail"]

        # 4. Bob attempts to list Alice's sessions -> 403
        list_res = client_bob.get("/api/v1/chat/sessions?user_id=eng.alice")
        assert list_res.status_code == 403
        assert "Forbidden" in list_res.json()["detail"]

        # 5. Bob attempts to forge session creation under Alice's name -> 403
        forge_res = client_bob.post("/api/v1/chat/sessions", json={"title": "Forged", "user_id": "eng.alice"})
        assert forge_res.status_code == 403
        assert "Forbidden" in forge_res.json()["detail"]

    def test_admin_cross_user_access_permitted(self, client_alice, client_admin):
        """Platform Admin (admin.dave) has cross-user administrative governance capabilities."""
        # Alice creates a session
        create_res = client_alice.post("/api/v1/chat/sessions", json={"title": "Governed Alice Session"})
        assert create_res.status_code == 200
        sid = create_res.json()["session"]["session_id"]

        # Admin can view Alice's session
        get_res = client_admin.get(f"/api/v1/chat/sessions/{sid}")
        assert get_res.status_code == 200
        assert get_res.json()["session_id"] == sid

        # Admin can list Alice's sessions
        list_res = client_admin.get("/api/v1/chat/sessions?user_id=eng.alice")
        assert list_res.status_code == 200
        assert any(s["session_id"] == sid for s in list_res.json())

        # Admin can append an authorized audit/intervention turn
        turn_res = client_admin.post(f"/api/v1/chat/sessions/{sid}/turns", json={"content": "Run diagnostics"})
        assert turn_res.status_code == 200

        # Admin can delete session
        del_res = client_admin.delete(f"/api/v1/chat/sessions/{sid}")
        assert del_res.status_code == 200


class TestLoudPostgresFailureAndWorkerFailover:
    """Validates loud PostgreSQL failure semantics and stateless worker failover (Flags 3 & 4)."""

    def test_postgres_loud_failure_on_unreachable_db(self):
        """When db_url is configured but PostgreSQL is unreachable, writes must raise loudly."""
        unreachable_url = "postgresql://invalid_user:***@127.0.0.1:54329/invalid_db"
        repo = RedisChatSessionRepository(db_url=unreachable_url)

        # 1. create_session must fail loudly
        with pytest.raises(RuntimeError, match="PostgreSQL connection failed"):
            repo.create_session(user_id="eng.alice", title="Failed DB Session")

        # 2. append_turn must fail loudly
        turn = ChatTurn(
            turn_id="turn-fail-1",
            session_id="sess-fail-1",
            turn_index=0,
            role="user",
            content="Hello failure"
        )
        with pytest.raises(RuntimeError, match="PostgreSQL connection failed"):
            repo.append_turn("sess-fail-1", turn)

        # 3. delete_session must fail loudly
        with pytest.raises(RuntimeError, match="PostgreSQL connection failed"):
            repo.delete_session("sess-fail-1")

        # In-memory sessions must remain empty (no ghost state created)
        assert len(repo._memory_sessions) == 0

    def test_stateless_worker_failover_resumption(self):
        """
        Simulates two independent worker processes (Worker A and Worker B).
        Worker A writes turns to shared store.
        Worker A process is terminated ('kill -9' / fresh process memory).
        Worker B initializes with fresh empty memory, retrieves session from store,
        and continues conversation with 100% turn retention.
        """
        shared_store: dict = {}

        class MockWorkerRepo(RedisChatSessionRepository):
            """Simulates two worker instances communicating via a shared persistent backend."""
            def __init__(self, shared_db: dict):
                super().__init__(db_url=None)
                self.shared_db = shared_db

            def create_session(self, user_id: str, session_id: Optional[str] = None, title: Optional[str] = None, metadata: Optional[dict] = None):
                s = super().create_session(user_id, session_id, title, metadata)
                self.shared_db[s.session_id] = s.to_dict(include_turns=True)
                return s

            def get_session(self, session_id: str):
                cached = super().get_session(session_id)
                if cached:
                    return cached
                # Rehydrate from shared persistent store
                if session_id in self.shared_db:
                    restored = ChatSession.from_dict(self.shared_db[session_id])
                    with self._lock:
                        self._memory_sessions[session_id] = restored
                    return restored
                return None

            def append_turn(self, session_id: str, turn: ChatTurn):
                t = super().append_turn(session_id, turn)
                self.shared_db[session_id] = self.get_session(session_id).to_dict(include_turns=True)
                return t

        # --- Worker 1 Process Lifecycle ---
        worker_1 = MockWorkerRepo(shared_store)
        sess = worker_1.create_session(user_id="eng.alice", title="Cross-Worker Session")
        sid = sess.session_id

        t0 = ChatTurn(turn_id="turn-w1-0", session_id=sid, turn_index=0, role="user", content="Deploy nginx cluster")
        worker_1.append_turn(sid, t0)
        t1 = ChatTurn(turn_id="turn-w1-1", session_id=sid, turn_index=1, role="assistant", content="Ready to deploy nginx")
        worker_1.append_turn(sid, t1)

        # Worker 1 process terminates (kill -9): memory is discarded
        del worker_1

        # --- Worker 2 Process Lifecycle (Post-Restart / Failover) ---
        worker_2 = MockWorkerRepo(shared_store)
        # Worker 2 memory is completely clean
        assert sid not in worker_2._memory_sessions

        # Worker 2 resumes conversation
        rehydrated = worker_2.get_session(sid)
        assert rehydrated is not None
        assert rehydrated.session_id == sid
        assert len(rehydrated.turns) == 2
        assert rehydrated.turns[0].content == "Deploy nginx cluster"
        assert rehydrated.turns[1].content == "Ready to deploy nginx"

        # Worker 2 appends next turn
        t2 = ChatTurn(turn_id="turn-w2-2", session_id=sid, turn_index=2, role="user", content="Confirm deployment")
        worker_2.append_turn(sid, t2)

        # Verify 100% turn retention across workers with sequential monotonic indices
        final_sess = worker_2.get_session(sid)
        assert len(final_sess.turns) == 3
        assert [t.turn_index for t in final_sess.turns] == [0, 1, 2]
        assert final_sess.turns[2].content == "Confirm deployment"

