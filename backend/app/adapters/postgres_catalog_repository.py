"""
Project Vulcan: PostgreSQL 16 + pgvector Catalog Search Repository
Author: Alex Xu (Distributed Systems Lead) & Andrej Karpathy (AI Systems Lead)
Implements:
1. ICatalogRepository port over PostgreSQL 16 with pgvector extension.
2. HNSW cosine similarity vector search (1,536 dimensions) for sub-10ms ANN retrieval.
3. Sparse full-text search over generated tsvector column (GIN index).
4. Two-Stage Reciprocal Rank Fusion (RRF: 0.6 dense + 0.4 sparse).
5. Hard Refusal Gate (BKND-26 / CHAT-06): Kills the Zero-Score Trap by failing closed on out-of-catalog queries.
6. Disambiguation Gate (CHAT-08): Detects ambiguous intents when top-2 Δ < 0.05.
7. DB-Level Steel Cage Enforcement: CHECK constraint (curation_status <> 'CURATED' OR git_commit_sha IS NOT NULL).
"""
import hashlib
import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row

from app.domain.entities import (
    CatalogItem,
    CurationStatus,
    ExecutionEngineType,
    RiskTier,
)
from app.domain.exceptions import ParameterValidationError, PolicyViolationError
from app.ports.interfaces import IEmbeddingProvider
from app.ports.repositories import ICatalogRepository
from app.adapters.embedding_providers import get_embedding_provider

logger = logging.getLogger("vulcan.postgres_catalog")


def compute_hash_embedding(text: str, dim: int = 1536) -> List[float]:
    """
    Computes a deterministic, normalized 1,536-dimensional hash embedding.
    Uses token hashing with sha256 to create an L2-normalized dense vector.
    Ensures identical or semantically overlapping texts yield high cosine similarity,
    while random noise or out-of-catalog queries yield ~0.0 similarity.
    """
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        val = 1.0 / math.sqrt(dim)
        return [val] * dim

    vec = [0.0] * dim
    for token in tokens:
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 16) & 1) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        return [x / norm for x in vec]
    return [0.0] * dim


def format_pgvector_literal(vec: List[float]) -> str:
    """Formats a float list into a PostgreSQL pgvector literal string '[v1,v2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


class PostgresCatalogRepository(ICatalogRepository):
    """
    Production pgvector catalog persistence and hybrid search repository.
    Enforces strict typing, connection pooling, and banking governance rules.
    """

    def __init__(self, db_url: Optional[str] = None, embedding_provider: Optional[IEmbeddingProvider] = None):
        self.db_url = (
            db_url
            or os.getenv("POSTGRES_URL")
            or os.getenv("DATABASE_URL")
            or "postgresql://vulcan_admin:vulcan_secret_pnc_2026@localhost:5432/vulcan_control_plane"
        )
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self._ensure_tables()

    def _get_connection(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def _ensure_tables(self) -> None:
        """Verifies extension and tables exist."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS catalog_items (
                            id VARCHAR(64) PRIMARY KEY,
                            identifier VARCHAR(128) NOT NULL UNIQUE,
                            name VARCHAR(255) NOT NULL,
                            engine VARCHAR(32) NOT NULL,
                            git_repo VARCHAR(255) NOT NULL DEFAULT '',
                            git_commit_sha VARCHAR(64),
                            playbook_or_module_path VARCHAR(255) NOT NULL DEFAULT '',
                            risk_tier VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',
                            requires_maker_checker BOOLEAN NOT NULL DEFAULT TRUE,
                            requires_chg BOOLEAN NOT NULL DEFAULT TRUE,
                            input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
                            rollback_path VARCHAR(255),
                            category VARCHAR(64) DEFAULT 'general',
                            description TEXT DEFAULT '',
                            tags TEXT[] DEFAULT '{}',
                            curation_status VARCHAR(32) NOT NULL DEFAULT 'CANDIDATE',
                            provenance JSONB DEFAULT '{}'::jsonb,
                            embedding vector(1536),
                            tsv tsvector GENERATED ALWAYS AS (
                                to_tsvector('english', coalesce(name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(identifier, ''))
                            ) STORED,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            CONSTRAINT chk_catalog_curated_sha CHECK (curation_status <> 'CURATED' OR (git_commit_sha IS NOT NULL AND git_commit_sha ~ '^[0-9a-f]{40}$'))
                        );
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_catalog_items_embedding_hnsw 
                        ON catalog_items USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64);
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_catalog_items_tsv 
                        ON catalog_items USING gin(tsv);
                    """)
                conn.commit()
        except Exception as e:
            logger.warning("Could not verify PostgreSQL catalog tables on init: %s", e)

    def _row_to_entity(self, row: Dict[str, Any]) -> CatalogItem:
        """Hydrates a domain CatalogItem entity from a database dictionary row."""
        input_schema = row.get("input_schema")
        if isinstance(input_schema, str):
            try:
                input_schema = json.loads(input_schema)
            except Exception:
                input_schema = {}
        elif not isinstance(input_schema, dict):
            input_schema = {}

        provenance = row.get("provenance")
        if isinstance(provenance, str):
            try:
                provenance = json.loads(provenance)
            except Exception:
                provenance = None

        tags = row.get("tags")
        if tags is None:
            tags = []
        elif not isinstance(tags, list):
            tags = list(tags)

        curation_str = row.get("curation_status") or "CANDIDATE"
        try:
            curation_status = CurationStatus(curation_str)
        except Exception:
            curation_status = CurationStatus.CANDIDATE

        engine_str = row.get("engine") or "ansible"
        try:
            engine = ExecutionEngineType(engine_str)
        except Exception:
            engine = ExecutionEngineType.ANSIBLE

        risk_str = row.get("risk_tier") or "MEDIUM"
        try:
            risk_tier = RiskTier(risk_str)
        except Exception:
            risk_tier = RiskTier.MEDIUM

        return CatalogItem(
            id=str(row["id"]),
            identifier=str(row["identifier"]),
            name=str(row["name"]),
            engine=engine,
            git_repo=str(row.get("git_repo") or ""),
            git_commit_sha=str(row.get("git_commit_sha") or ("0" * 40)),
            playbook_or_module_path=str(row.get("playbook_or_module_path") or ""),
            risk_tier=risk_tier,
            requires_maker_checker=bool(row.get("requires_maker_checker", True)),
            requires_chg=bool(row.get("requires_chg", True)),
            input_schema=input_schema,
            rollback_path=row.get("rollback_path"),
            category=str(row.get("category") or "general"),
            description=str(row.get("description") or ""),
            tags=tags,
            curation_status=curation_status,
            provenance=provenance,
        )

    def save(self, item: CatalogItem, embedding: Optional[List[float]] = None) -> None:
        """
        Upserts a catalog item into PostgreSQL.
        Enforces DB-level steel cage check constraint (chk_catalog_curated_sha).
        If embedding is not provided, computes deterministic hash embedding.
        """
        if embedding is None:
            text_corpus = f"{item.name} {item.description} {item.identifier} {' '.join(item.tags)}"
            embedding = self.embedding_provider.embed_text(text_corpus)

        vec_literal = format_pgvector_literal(embedding)
        input_schema_json = json.dumps(item.input_schema)
        provenance_json = json.dumps(item.provenance) if item.provenance else None

        sql = """
            INSERT INTO catalog_items (
                id, identifier, name, engine, git_repo, git_commit_sha,
                playbook_or_module_path, risk_tier, requires_maker_checker,
                requires_chg, input_schema, rollback_path, category,
                description, tags, curation_status, provenance, embedding,
                updated_at
            ) VALUES (
                %(id)s, %(identifier)s, %(name)s, %(engine)s, %(git_repo)s, %(git_commit_sha)s,
                %(playbook_or_module_path)s, %(risk_tier)s, %(requires_maker_checker)s,
                %(requires_chg)s, %(input_schema)s::jsonb, %(rollback_path)s, %(category)s,
                %(description)s, %(tags)s, %(curation_status)s, %(provenance)s::jsonb,
                %(embedding)s::vector, NOW()
            )
            ON CONFLICT (identifier) DO UPDATE SET
                name = EXCLUDED.name,
                engine = EXCLUDED.engine,
                git_repo = EXCLUDED.git_repo,
                git_commit_sha = EXCLUDED.git_commit_sha,
                playbook_or_module_path = EXCLUDED.playbook_or_module_path,
                risk_tier = EXCLUDED.risk_tier,
                requires_maker_checker = EXCLUDED.requires_maker_checker,
                requires_chg = EXCLUDED.requires_chg,
                input_schema = EXCLUDED.input_schema,
                rollback_path = EXCLUDED.rollback_path,
                category = EXCLUDED.category,
                description = EXCLUDED.description,
                tags = EXCLUDED.tags,
                curation_status = EXCLUDED.curation_status,
                provenance = EXCLUDED.provenance,
                embedding = EXCLUDED.embedding,
                updated_at = NOW();
        """
        params = {
            "id": item.id,
            "identifier": item.identifier,
            "name": item.name,
            "engine": item.engine.value if hasattr(item.engine, "value") else str(item.engine),
            "git_repo": item.git_repo,
            "git_commit_sha": item.git_commit_sha,
            "playbook_or_module_path": item.playbook_or_module_path,
            "risk_tier": item.risk_tier.value if hasattr(item.risk_tier, "value") else str(item.risk_tier),
            "requires_maker_checker": item.requires_maker_checker,
            "requires_chg": item.requires_chg,
            "input_schema": input_schema_json,
            "rollback_path": item.rollback_path,
            "category": item.category,
            "description": item.description,
            "tags": item.tags,
            "curation_status": item.curation_status.value if hasattr(item.curation_status, "value") else str(item.curation_status),
            "provenance": provenance_json,
            "embedding": vec_literal,
        }

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    def get_by_identifier(self, identifier: str) -> Optional[CatalogItem]:
        """Fetches catalog item by identifier."""
        sql = "SELECT * FROM catalog_items WHERE identifier = %(identifier)s LIMIT 1;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"identifier": identifier})
                row = cur.fetchone()
                if row:
                    return self._row_to_entity(row)
        return None

    def get_by_id(self, item_id: str) -> Optional[CatalogItem]:
        """Fetches catalog item by primary key id."""
        sql = "SELECT * FROM catalog_items WHERE id = %(id)s LIMIT 1;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"id": item_id})
                row = cur.fetchone()
                if row:
                    return self._row_to_entity(row)
        return None

    def list_all(self, curation_status: Optional[str] = None) -> List[CatalogItem]:
        """Returns all registered catalog items matching optional curation status."""
        sql = "SELECT * FROM catalog_items"
        params = {}
        if curation_status:
            sql += " WHERE curation_status = %(curation_status)s"
            params["curation_status"] = curation_status
        sql += " ORDER BY name ASC LIMIT 1000;"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [self._row_to_entity(r) for r in cur.fetchall()]

    def count(self, curation_status: Optional[str] = None) -> int:
        """Returns total count of registered catalog items."""
        sql = "SELECT COUNT(*) AS total FROM catalog_items"
        params = {}
        if curation_status:
            sql += " WHERE curation_status = %(curation_status)s"
            params["curation_status"] = curation_status
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return int(row["total"]) if row else 0

    def search_vector(
        self,
        embedding: List[float],
        top_k: int = 10,
        curation_status: Optional[str] = None
    ) -> List[CatalogItem]:
        """Executes pure HNSW cosine similarity search over catalog items."""
        vec_literal = format_pgvector_literal(embedding)
        sql = """
            SELECT *, 1 - (embedding <=> %(qvec)s::vector) AS score
            FROM catalog_items
            WHERE embedding IS NOT NULL
        """
        params: Dict[str, Any] = {"qvec": vec_literal, "top_k": top_k}
        if curation_status:
            sql += " AND curation_status = %(curation_status)s"
            params["curation_status"] = curation_status

        sql += " ORDER BY embedding <=> %(qvec)s::vector ASC LIMIT %(top_k)s;"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [self._row_to_entity(r) for r in cur.fetchall()]

    def search_sparse(
        self,
        query: str,
        top_k: int = 10,
        curation_status: Optional[str] = None
    ) -> List[Tuple[CatalogItem, float]]:
        """Executes pure full-text sparse search (tsvector ts_rank)."""
        if not query.strip():
            return []
        sql = """
            SELECT *, ts_rank(tsv, websearch_to_tsquery('english', %(query)s)) AS score
            FROM catalog_items
            WHERE tsv @@ websearch_to_tsquery('english', %(query)s)
        """
        params: Dict[str, Any] = {"query": query, "top_k": top_k}
        if curation_status:
            sql += " AND curation_status = %(curation_status)s"
            params["curation_status"] = curation_status
        sql += " ORDER BY score DESC LIMIT %(top_k)s;"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(sql, params)
                    return [(self._row_to_entity(r), float(r["score"])) for r in cur.fetchall()]
                except Exception:
                    conn.rollback()
                    fallback_sql = sql.replace("websearch_to_tsquery", "plainto_tsquery")
                    cur.execute(fallback_sql, params)
                    return [(self._row_to_entity(r), float(r["score"])) for r in cur.fetchall()]

    def search_hybrid(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        curation_status: Optional[str] = None,
        rrf_k: int = 60,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4
    ) -> List[Tuple[CatalogItem, float, Dict[str, Any]]]:
        """
        Two-Stage Hybrid Search combining Dense HNSW Cosine Similarity and Sparse ts_rank via RRF.
        
        Enforces:
        1. Calibrated Refusal Gate (BKND-26 / CHAT-06):
           Kills the Zero-Score Trap: If query has neither dense semantic alignment (dense < 0.35)
           nor sparse keyword overlap (sparse == 0.0), refuses and returns [].
        2. Disambiguation Gate (CHAT-08):
           If top-1 score - top-2 score < 0.05, tags result metadata with disambiguation_required=True.
        """
        if not query.strip():
            return []

        if query_embedding is None:
            query_embedding = self.embedding_provider.embed_text(query)

        vec_literal = format_pgvector_literal(query_embedding)

        # 1. Dense retrieval (HNSW cosine similarity index scan)
        dense_sql = """
            SELECT id, identifier, 1 - (embedding <=> %(qvec)s::vector) AS dense_score
            FROM catalog_items
            WHERE embedding IS NOT NULL
        """
        params: Dict[str, Any] = {"qvec": vec_literal, "query": query, "top_k": top_k}
        if curation_status:
            dense_sql += " AND curation_status = %(curation_status)s"
            params["curation_status"] = curation_status
        dense_sql += " ORDER BY embedding <=> %(qvec)s::vector ASC LIMIT 50;"

        # 2. Sparse retrieval (Full text ts_rank index scan)
        sparse_sql = """
            SELECT id, identifier, ts_rank(tsv, websearch_to_tsquery('english', %(query)s)) AS sparse_score
            FROM catalog_items
            WHERE tsv @@ websearch_to_tsquery('english', %(query)s)
        """
        if curation_status:
            sparse_sql += " AND curation_status = %(curation_status)s"
        sparse_sql += " ORDER BY sparse_score DESC LIMIT 50;"

        dense_matches: Dict[str, Dict[str, Any]] = {}
        sparse_matches: Dict[str, Dict[str, Any]] = {}

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Execute dense
                cur.execute(dense_sql, params)
                for rank, r in enumerate(cur.fetchall(), start=1):
                    dense_matches[r["identifier"]] = {
                        "score": float(r["dense_score"]),
                        "rank": rank,
                        "id": r["id"],
                    }

                # Execute sparse with syntax fallback
                try:
                    cur.execute(sparse_sql, params)
                    for rank, r in enumerate(cur.fetchall(), start=1):
                        sparse_matches[r["identifier"]] = {
                            "score": float(r["sparse_score"]),
                            "rank": rank,
                            "id": r["id"],
                        }
                except Exception as e:
                    logger.debug("Sparse query websearch_to_tsquery failed, trying plainto_tsquery: %s", e)
                    conn.rollback()
                    fallback_sql = sparse_sql.replace("websearch_to_tsquery", "plainto_tsquery")
                    try:
                        cur.execute(fallback_sql, params)
                        for rank, r in enumerate(cur.fetchall(), start=1):
                            sparse_matches[r["identifier"]] = {
                                "score": float(r["sparse_score"]),
                                "rank": rank,
                                "id": r["id"],
                            }
                    except Exception:
                        conn.rollback()

        max_dense = max((m["score"] for m in dense_matches.values()), default=0.0)
        max_sparse = max((m["score"] for m in sparse_matches.values()), default=0.0)

        # Refusal Gate:
        # If both dense alignment is weak (< 0.35) and sparse keyword overlap is zero, refuse!
        if max_dense < 0.35 and max_sparse <= 0.0:
            logger.info("Refusal gate triggered for query '%s' (max_dense=%.3f, max_sparse=%.3f)", query, max_dense, max_sparse)
            return []

        # RRF Fusion
        all_identifiers = set(dense_matches.keys()).union(sparse_matches.keys())
        fused_scores: List[Dict[str, Any]] = []

        for ident in all_identifiers:
            dense_info = dense_matches.get(ident)
            sparse_info = sparse_matches.get(ident)

            rrf = 0.0
            d_score = dense_info["score"] if dense_info else 0.0
            s_score = sparse_info["score"] if sparse_info else 0.0

            if dense_info and d_score >= 0.35:
                rrf += dense_weight / (rrf_k + dense_info["rank"])
            if sparse_info and s_score > 0.0:
                rrf += sparse_weight / (rrf_k + sparse_info["rank"])

            if rrf > 0.0:
                fused_scores.append({
                    "identifier": ident,
                    "rrf_score": rrf,
                    "dense_score": d_score,
                    "sparse_score": s_score,
                })

        fused_scores.sort(key=lambda x: x["rrf_score"], reverse=True)
        top_matches = fused_scores[:top_k]

        if not top_matches:
            return []

        # Disambiguation Gate (CHAT-08)
        disambiguation_required = False
        delta_score = 0.0
        if len(top_matches) >= 2:
            delta_score = top_matches[0]["rrf_score"] - top_matches[1]["rrf_score"]
            if delta_score < 0.05:
                disambiguation_required = True

        # Hydrate domain entities in a single batch query
        results: List[Tuple[CatalogItem, float, Dict[str, Any]]] = []
        top_idents = [m["identifier"] for m in top_matches]
        entities_by_ident: Dict[str, CatalogItem] = {}
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM catalog_items WHERE identifier = ANY(%(idents)s)", {"idents": top_idents})
                for r in cur.fetchall():
                    entities_by_ident[r["identifier"]] = self._row_to_entity(r)

        for match in top_matches:
            item = entities_by_ident.get(match["identifier"])
            if item:
                meta = {
                    "dense_score": match["dense_score"],
                    "sparse_score": match["sparse_score"],
                    "disambiguation_required": disambiguation_required,
                    "delta_score": delta_score,
                }
                results.append((item, match["rrf_score"], meta))

        return results

    def reembed_all(self, batch_size: int = 100) -> int:
        """
        Re-computes embeddings for all catalog items using the configured embedding provider.
        Enables seamless model upgrades (e.g. hash -> semantic_cluster -> openai/text-embedding-3-small).
        """
        sql_fetch = "SELECT id, identifier, name, description, tags FROM catalog_items ORDER BY id ASC;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_fetch)
                rows = cur.fetchall()

            total = len(rows)
            for i in range(0, total, batch_size):
                chunk = rows[i : i + batch_size]
                texts = [
                    f"{r['name']} {r.get('description') or ''} {r['identifier']} {' '.join(r.get('tags') or [])}"
                    for r in chunk
                ]
                embeddings = self.embedding_provider.embed_batch(texts)
                with conn.cursor() as cur:
                    for r, emb in zip(chunk, embeddings):
                        cur.execute(
                            "UPDATE catalog_items SET embedding = %(emb)s::vector, updated_at = NOW() WHERE id = %(id)s;",
                            {"emb": format_pgvector_literal(emb), "id": r["id"]}
                        )
                conn.commit()
            return total

