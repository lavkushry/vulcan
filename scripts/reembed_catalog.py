#!/usr/bin/env python3
"""
Project Vulcan: Catalog Re-Embedding Utility (Milestone A2)
Embeds all items in catalog_items in PostgreSQL with real (OpenAI/Gemini) or calibrated cluster embeddings.
Includes loud fail-closed guard against synthetic degradation when real embeddings are mandated.
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add backend to path
BASE_DIR = Path(__file__).resolve().parent.parent
if (BASE_DIR / "app").exists():
    sys.path.insert(0, str(BASE_DIR))
else:
    sys.path.insert(0, str(BASE_DIR / "backend"))

from app.adapters.embedding_providers import get_embedding_provider
from app.ports.interfaces import IEmbeddingProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vulcan.reembed")


def reembed_catalog(
    db_url: str,
    provider: IEmbeddingProvider,
    forbid_synthetic: bool = False,
    batch_size: int = 100,
    curation_status: str = None
) -> None:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        logger.critical("psycopg is required to re-embed catalog. Install psycopg[binary].")
        sys.exit(1)

    provider_name = getattr(provider, "provider_name", "unknown")
    logger.info("Active Embedding Provider: %s (dim=%d)", provider_name, provider.dimension)

    # Loud guard against synthetic fallback
    if forbid_synthetic:
        if "semantic" in provider_name.lower() or "hash" in provider_name.lower() or "fake" in provider_name.lower():
            logger.critical(
                "LOUD GUARD TRIGGERED: --require-real was specified, but active provider is synthetic: '%s'. "
                "Failing closed to prevent corrupting benchmark measurements with synthetic data.",
                provider_name
            )
            sys.exit(1)

    conn = psycopg.connect(db_url, row_factory=dict_row)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            query = "SELECT id, identifier, name, description, tags, curation_status FROM catalog_items"
            params = []
            if curation_status:
                query += " WHERE curation_status = %s"
                params.append(curation_status)
            query += " ORDER BY id;"

            cur.execute(query, params)
            rows = cur.fetchall()
            total_items = len(rows)
            logger.info("Fetched %d catalog items to embed from database.", total_items)

            if total_items == 0:
                logger.warning("No items found to embed.")
                return

            t0 = time.perf_counter()
            processed = 0

            for i in range(0, total_items, batch_size):
                batch_rows = rows[i : i + batch_size]
                texts = [
                    f"{r['name']} {r.get('description', '')} {r['identifier']} {' '.join(r.get('tags') or [])}".strip()
                    for r in batch_rows
                ]

                b_start = time.perf_counter()
                embeddings = provider.embed_batch(texts)
                b_elapsed = time.perf_counter() - b_start

                # Update embeddings in database
                for r, emb in zip(batch_rows, embeddings):
                    emb_str = "[" + ",".join(str(v) for v in emb) + "]"
                    cur.execute(
                        "UPDATE catalog_items SET embedding = %s::vector, updated_at = NOW() WHERE id = %s;",
                        (emb_str, r["id"])
                    )

                conn.commit()
                processed += len(batch_rows)
                rate = processed / (time.perf_counter() - t0)
                logger.info(
                    "  [+] Embedded %d / %d items (batch: %.2fs | rate: %.1f items/s)",
                    processed, total_items, b_elapsed, rate
                )

            total_elapsed = time.perf_counter() - t0
            logger.info("==================================================================")
            logger.info(" Re-Embedding Complete:")
            logger.info("   - Provider:       %s", provider_name)
            logger.info("   - Total Items:    %d", processed)
            logger.info("   - Total Time:     %.2f seconds", total_elapsed)
            logger.info("   - Avg Throughput: %.1f items/sec", processed / total_elapsed if total_elapsed > 0 else 0)
            logger.info("==================================================================")

            # Verification
            cur.execute("SELECT count(*) as total, count(embedding) as with_emb FROM catalog_items;")
            v_row = cur.fetchone()
            logger.info("DB Verification: Total=%d | With Embedding=%d", v_row["total"], v_row["with_emb"])

        # Post-reembed index maintenance (prevents index bloat & optimizes HNSW search)
        logger.info("Running post-reembedding maintenance: VACUUM ANALYZE catalog_items...")
        conn.autocommit = True
        with conn.cursor() as m_cur:
            m_cur.execute("VACUUM ANALYZE catalog_items;")
            logger.info("Running post-reembedding maintenance: REINDEX INDEX idx_catalog_items_embedding_hnsw...")
            m_cur.execute("REINDEX INDEX idx_catalog_items_embedding_hnsw;")
        conn.autocommit = False
        logger.info("Post-reembedding maintenance completed successfully.")

    except Exception as e:
        conn.rollback()
        logger.exception("Re-embedding failed: %s", e)
        sys.exit(1)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Vulcan Catalog Re-Embedding Tool")
    parser.add_argument("--provider", type=str, default=None, choices=["openai", "gemini", "semantic-cluster", "hash"],
                        help="Explicit embedding provider to use")
    parser.add_argument("--require-real", action="store_true",
                        help="Loudly forbid synthetic/cluster providers (must use live OpenAI or Gemini)")
    parser.add_argument("--db-url", type=str, default=None,
                        help="PostgreSQL connection string (or set DATABASE_URL/POSTGRES_URL)")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Batch size for embedding generation (default: 100)")
    parser.add_argument("--curation-status", type=str, default=None,
                        help="Optional filter: CURATED or CANDIDATE only")
    args = parser.parse_args()

    db_url = (
        args.db_url
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
    )
    if not db_url:
        logger.critical("DATABASE_URL or POSTGRES_URL environment variable must be set, or provide --db-url.")
        sys.exit(1)

    provider = get_embedding_provider(provider_type=args.provider)
    reembed_catalog(
        db_url=db_url,
        provider=provider,
        forbid_synthetic=args.require_real,
        batch_size=args.batch_size,
        curation_status=args.curation_status
    )


if __name__ == "__main__":
    main()
