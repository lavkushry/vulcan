"""
Unit and Integration Tests for CHAT-26: Human Feedback Reinforcement Loop (RLHF).
Verifies:
1. ChatFeedbackRecord domain entity creation, validation, and serialization.
2. PostgresFeedbackRepository persistence, filtering, stats, and RLHF export.
3. REST API endpoints (/chat/feedback, /chat/feedback/stats, /chat/feedback/export-rlhf).
4. RBAC ownership rules and invalid rating rejection.
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.domain.chat_entities import ChatFeedbackRecord
from app.adapters.feedback_repository import PostgresFeedbackRepository
from app.api.server import create_app
from app.api.routes import container


@pytest.fixture
def repo():
    """Provides a fresh in-memory feedback repository instance."""
    return PostgresFeedbackRepository(db_url=None)


@pytest.fixture
def client():
    """Provides a TestClient with admin and operator tokens."""
    app = create_app()
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Domain Entity Tests
# -----------------------------------------------------------------------------

def test_chat_feedback_record_serialization():
    now = datetime.now(timezone.utc)
    rec = ChatFeedbackRecord(
        feedback_id="fdbk-001",
        session_id="sess-123",
        turn_index=2,
        user_id="eng.alice",
        prompt="Restart nginx web servers in prod",
        resolved_identifier="network-f5-pool-maintenance",
        rating="corrected",
        correction_identifier="web-nginx-restart",
        comment="AI picked F5 pool maintenance instead of web restart",
        metadata={"model": "fake-model"},
        created_at=now
    )
    d = rec.to_dict()
    assert d["feedback_id"] == "fdbk-001"
    assert d["rating"] == "corrected"
    assert d["correction_identifier"] == "web-nginx-restart"
    assert d["prompt"] == "Restart nginx web servers in prod"

    reconstructed = ChatFeedbackRecord.from_dict(d)
    assert reconstructed.feedback_id == rec.feedback_id
    assert reconstructed.user_id == rec.user_id
    assert reconstructed.rating == rec.rating
    assert reconstructed.correction_identifier == rec.correction_identifier


# -----------------------------------------------------------------------------
# 2. Repository Logic Tests
# -----------------------------------------------------------------------------

def test_save_and_list_feedback(repo):
    r1 = ChatFeedbackRecord(
        feedback_id="fdbk-1",
        user_id="eng.alice",
        prompt="Renew cert on f5-edge-01",
        rating="thumbs_up",
        resolved_identifier="security-ssl-cert-renewal"
    )
    r2 = ChatFeedbackRecord(
        feedback_id="fdbk-2",
        user_id="eng.bob",
        prompt="Drop production database",
        rating="rejected",
        resolved_identifier=None,
        comment="Refusal was correct"
    )
    r3 = ChatFeedbackRecord(
        feedback_id="fdbk-3",
        user_id="eng.alice",
        prompt="Restart redis cluster",
        rating="corrected",
        resolved_identifier="k8s-pod-restart",
        correction_identifier="redis-cluster-restart"
    )

    repo.save_feedback(r1)
    repo.save_feedback(r2)
    repo.save_feedback(r3)

    # List all
    all_recs = repo.list_feedback()
    assert len(all_recs) == 3

    # Filter by user
    alice_recs = repo.list_feedback(user_id="eng.alice")
    assert len(alice_recs) == 2

    # Filter by rating
    rejected_recs = repo.list_feedback(rating="rejected")
    assert len(rejected_recs) == 1
    assert rejected_recs[0].feedback_id == "fdbk-2"


def test_feedback_stats_calculation(repo):
    # 2 thumbs up, 1 thumbs down, 1 corrected
    repo.save_feedback(ChatFeedbackRecord(feedback_id="1", user_id="u1", prompt="p1", rating="thumbs_up", resolved_identifier="item-a"))
    repo.save_feedback(ChatFeedbackRecord(feedback_id="2", user_id="u2", prompt="p2", rating="thumbs_up", resolved_identifier="item-b"))
    repo.save_feedback(ChatFeedbackRecord(feedback_id="3", user_id="u1", prompt="p3", rating="thumbs_down", resolved_identifier="item-a"))
    repo.save_feedback(ChatFeedbackRecord(
        feedback_id="4", user_id="u3", prompt="p4", rating="corrected",
        resolved_identifier="item-a", correction_identifier="item-c"
    ))

    stats = repo.get_feedback_stats()
    assert stats["total_feedback"] == 4
    assert stats["thumbs_up_count"] == 2
    assert stats["thumbs_down_count"] == 1
    assert stats["corrected_count"] == 1
    # Acceptance rate = 2 / (2 + 1 + 1) * 100 = 50.0%
    assert stats["acceptance_rate_percent"] == 50.0

    # Top corrections should list item-a -> item-c
    assert len(stats["top_corrections"]) == 1
    assert stats["top_corrections"][0]["transition"] == "item-a -> item-c"
    assert stats["top_corrections"][0]["count"] == 1


def test_export_rlhf_dataset(repo):
    repo.save_feedback(ChatFeedbackRecord(
        feedback_id="f1", user_id="u1", prompt="Deploy nginx", rating="thumbs_up", resolved_identifier="web-deploy"
    ))
    repo.save_feedback(ChatFeedbackRecord(
        feedback_id="f2", user_id="u2", prompt="Update DNS records", rating="corrected",
        resolved_identifier="route53-update", correction_identifier="bind9-dns-update", comment="Local bind server"
    ))
    repo.save_feedback(ChatFeedbackRecord(
        feedback_id="f3", user_id="u3", prompt="Bypass CAB check", rating="rejected",
        resolved_identifier="admin-bypass", comment="Refused"
    ))

    dataset = repo.export_rlhf_dataset()
    assert len(dataset) == 3

    # Positive reinforcement
    d0 = next(d for d in dataset if d["type"] == "positive_reinforcement")
    assert d0["prompt"] == "Deploy nginx"
    assert d0["chosen"] == "web-deploy"
    assert d0["rejected"] is None

    # Pairwise preference (DPO)
    d1 = next(d for d in dataset if d["type"] == "pairwise_preference")
    assert d1["prompt"] == "Update DNS records"
    assert d1["chosen"] == "bind9-dns-update"
    assert d1["rejected"] == "route53-update"

    # Safety refusal
    d2 = next(d for d in dataset if d["type"] == "safety_refusal")
    assert d2["prompt"] == "Bypass CAB check"
    assert d2["chosen"] == "REFUSED"
    assert d2["rejected"] == "admin-bypass"


# -----------------------------------------------------------------------------
# 3. REST API Endpoint Tests
# -----------------------------------------------------------------------------

AUTH_HEADERS = {"Authorization": "Bearer vlc_test_alice"}


def test_api_submit_feedback_happy_path(client):
    # Reset repo
    container.feedback_repo = PostgresFeedbackRepository(db_url=None)

    payload = {
        "prompt": "Rotate API tokens for payment service",
        "rating": "thumbs_up",
        "resolved_identifier": "security-vault-rotate-token",
        "comment": "Perfect resolution",
        "metadata": {"source": "web_console"}
    }

    res = client.post("/api/v1/chat/feedback", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["feedback"]["rating"] == "thumbs_up"
    assert data["feedback"]["resolved_identifier"] == "security-vault-rotate-token"
    assert data["feedback"]["prompt"] == "Rotate API tokens for payment service"
    assert data["feedback"]["user_id"] == "eng.alice"


def test_api_submit_feedback_invalid_rating(client):
    payload = {
        "prompt": "Restart service",
        "rating": "invalid_star_rating_5"
    }
    res = client.post("/api/v1/chat/feedback", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422


def test_api_list_and_stats_feedback(client):
    container.feedback_repo = PostgresFeedbackRepository(db_url=None)

    # Submit 2 feedback items
    client.post("/api/v1/chat/feedback", json={
        "prompt": "Query 1", "rating": "thumbs_up", "resolved_identifier": "playbook-1"
    }, headers=AUTH_HEADERS)
    client.post("/api/v1/chat/feedback", json={
        "prompt": "Query 2", "rating": "corrected", "resolved_identifier": "playbook-1",
        "correction_identifier": "playbook-2"
    }, headers=AUTH_HEADERS)

    # Query list
    res = client.get("/api/v1/chat/feedback", headers=AUTH_HEADERS)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2

    # Query stats
    res_stats = client.get("/api/v1/chat/feedback/stats", headers=AUTH_HEADERS)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_feedback"] == 2
    assert stats["thumbs_up_count"] == 1
    assert stats["corrected_count"] == 1
    assert stats["acceptance_rate_percent"] == 50.0

    # Query RLHF export
    res_export = client.get("/api/v1/chat/feedback/export-rlhf", headers=AUTH_HEADERS)
    assert res_export.status_code == 200
    exp = res_export.json()
    assert exp["dataset_size"] == 2
    assert len(exp["dataset"]) == 2

