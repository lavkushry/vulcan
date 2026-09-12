"""
Project Vulcan: PostgreSQL & In-Memory RLHF Feedback Repository (CHAT-26)
Author: Andrej Karpathy (AI Systems Lead) & Uncle Bob
Implements IFeedbackRepository for operator feedback capture, RLHF dataset curation,
and model intent alignment.
"""
from __future__ import annotations

import collections
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.domain.chat_entities import ChatFeedbackRecord
from app.ports.repositories import IFeedbackRepository

logger = logging.getLogger("vulcan.feedback_repo")


class PostgresFeedbackRepository(IFeedbackRepository):
    """
    Two-tier persistence adapter for operator reinforcement feedback (CHAT-26):
    - Fast-path thread-safe in-memory cache and offline fallback.
    - PostgreSQL durable backing store (chat_intent_feedback).
    - Statistical aggregation and RLHF/DPO dataset export.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url
        self._lock = threading.RLock()
        self._memory_feedback: Dict[str, ChatFeedbackRecord] = {}
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensures the feedback table exists in PostgreSQL if db_url is configured."""
        if not self.db_url:
            return
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS chat_intent_feedback (
                            feedback_id VARCHAR(64) PRIMARY KEY,
                            session_id VARCHAR(64),
                            turn_index INT,
                            user_id VARCHAR(128) NOT NULL,
                            prompt TEXT NOT NULL,
                            resolved_identifier VARCHAR(128),
                            rating VARCHAR(32) NOT NULL,
                            correction_identifier VARCHAR(128),
                            comment TEXT,
                            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                        CREATE INDEX IF NOT EXISTS idx_chat_feedback_user_id ON chat_intent_feedback(user_id, created_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_chat_feedback_rating ON chat_intent_feedback(rating);
                        CREATE INDEX IF NOT EXISTS idx_chat_feedback_resolved ON chat_intent_feedback(resolved_identifier);
                        CREATE INDEX IF NOT EXISTS idx_chat_feedback_created ON chat_intent_feedback(created_at DESC);
                        """
                    )
            logger.info("Verified PostgreSQL chat_intent_feedback schema.")
        except Exception as e:
            logger.warning("Could not verify PostgreSQL feedback schema (%s). Operating in memory mode.", e)

    def _get_pg_conn(self, autocommit: bool = True):
        if not self.db_url:
            return None
        import psycopg
        return psycopg.connect(self.db_url, autocommit=autocommit)

    def save_feedback(self, record: ChatFeedbackRecord) -> ChatFeedbackRecord:
        """Persists an operator feedback record to PostgreSQL and in-memory cache."""
        with self._lock:
            self._memory_feedback[record.feedback_id] = record

        if self.db_url:
            try:
                with self._get_pg_conn(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO chat_intent_feedback (
                                feedback_id, session_id, turn_index, user_id, prompt,
                                resolved_identifier, rating, correction_identifier, comment, metadata, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                            ON CONFLICT (feedback_id) DO UPDATE SET
                                rating = EXCLUDED.rating,
                                correction_identifier = EXCLUDED.correction_identifier,
                                comment = EXCLUDED.comment,
                                metadata = EXCLUDED.metadata;
                            """,
                            (
                                record.feedback_id,
                                record.session_id,
                                record.turn_index,
                                record.user_id,
                                record.prompt,
                                record.resolved_identifier,
                                record.rating,
                                record.correction_identifier,
                                record.comment,
                                json.dumps(record.metadata),
                                record.created_at
                            )
                        )
            except Exception as e:
                logger.error("Failed to persist feedback to PostgreSQL: %s", e)

        return record

    def list_feedback(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        rating: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ChatFeedbackRecord]:
        """Lists feedback records with optional filtering and pagination."""
        if self.db_url:
            try:
                query = "SELECT feedback_id, session_id, turn_index, user_id, prompt, resolved_identifier, rating, correction_identifier, comment, metadata, created_at FROM chat_intent_feedback"
                filters = []
                params: List[Any] = []

                if session_id:
                    filters.append("session_id = %s")
                    params.append(session_id)
                if user_id:
                    filters.append("user_id = %s")
                    params.append(user_id)
                if rating:
                    filters.append("rating = %s")
                    params.append(rating)

                if filters:
                    query += " WHERE " + " AND ".join(filters)

                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s;"
                params.extend([limit, offset])

                with self._get_pg_conn(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, params)
                        rows = cur.fetchall()
                        records = []
                        for r in rows:
                            meta = r[9] if isinstance(r[9], dict) else json.loads(r[9]) if r[9] else {}
                            records.append(
                                ChatFeedbackRecord(
                                    feedback_id=r[0],
                                    session_id=r[1],
                                    turn_index=r[2],
                                    user_id=r[3],
                                    prompt=r[4],
                                    resolved_identifier=r[5],
                                    rating=r[6],
                                    correction_identifier=r[7],
                                    comment=r[8],
                                    metadata=meta,
                                    created_at=r[10]
                                )
                            )
                        return records
            except Exception as e:
                logger.error("Failed to query feedback from PostgreSQL: %s. Falling back to memory.", e)

        # In-memory fallback
        with self._lock:
            all_records = list(self._memory_feedback.values())
            filtered = all_records
            if session_id:
                filtered = [r for r in filtered if r.session_id == session_id]
            if user_id:
                filtered = [r for r in filtered if r.user_id == user_id]
            if rating:
                filtered = [r for r in filtered if r.rating == rating]

            filtered.sort(key=lambda r: r.created_at, reverse=True)
            return filtered[offset : offset + limit]

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Aggregates feedback metrics including volume, ratings, and acceptance rate."""
        records = self.list_feedback(limit=10000)

        total = len(records)
        thumbs_up = sum(1 for r in records if r.rating == "thumbs_up")
        thumbs_down = sum(1 for r in records if r.rating == "thumbs_down")
        rejected = sum(1 for r in records if r.rating == "rejected")
        corrected = sum(1 for r in records if r.rating == "corrected" or r.correction_identifier)

        eval_total = thumbs_up + thumbs_down + corrected
        acceptance_rate = round((thumbs_up / eval_total * 100.0), 2) if eval_total > 0 else 100.0

        # Top corrected playbooks
        corrections: Dict[str, int] = collections.defaultdict(int)
        for r in records:
            if r.correction_identifier:
                pair = f"{r.resolved_identifier or 'UNRESOLVED'} -> {r.correction_identifier}"
                corrections[pair] += 1

        top_corrections = [
            {"transition": pair, "count": count}
            for pair, count in sorted(corrections.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return {
            "total_feedback": total,
            "thumbs_up_count": thumbs_up,
            "thumbs_down_count": thumbs_down,
            "rejected_count": rejected,
            "corrected_count": corrected,
            "acceptance_rate_percent": acceptance_rate,
            "top_corrections": top_corrections
        }

    def export_rlhf_dataset(self) -> List[Dict[str, Any]]:
        """
        Generates paired preference dataset for Direct Preference Optimization (DPO),
        Kahneman-Tversky Optimization (KTO), and supervised fine-tuning (SFT).
        """
        records = self.list_feedback(limit=10000)
        dataset = []

        for r in records:
            if r.rating == "thumbs_up":
                dataset.append({
                    "prompt": r.prompt,
                    "chosen": r.resolved_identifier or "MATCHED",
                    "rejected": None,
                    "type": "positive_reinforcement",
                    "rating": r.rating,
                    "feedback_id": r.feedback_id,
                    "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime) else str(r.created_at)
                })
            elif r.rating in ("thumbs_down", "corrected") and r.correction_identifier:
                dataset.append({
                    "prompt": r.prompt,
                    "chosen": r.correction_identifier,
                    "rejected": r.resolved_identifier or "REFUSED",
                    "type": "pairwise_preference",
                    "rating": r.rating,
                    "comment": r.comment,
                    "feedback_id": r.feedback_id,
                    "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime) else str(r.created_at)
                })
            elif r.rating == "rejected":
                dataset.append({
                    "prompt": r.prompt,
                    "chosen": "REFUSED",
                    "rejected": r.resolved_identifier or "UNRESOLVED",
                    "type": "safety_refusal",
                    "rating": r.rating,
                    "comment": r.comment,
                    "feedback_id": r.feedback_id,
                    "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime) else str(r.created_at)
                })

        return dataset
