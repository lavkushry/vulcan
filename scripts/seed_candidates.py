#!/usr/bin/env python3
"""
Project Vulcan: Repeatable Candidate Catalog Seeder (INV-1 / Curation Quarantine)
Loads candidate modules from corpus JSON, validates candidate invariants (curation_status=CANDIDATE, git_commit_sha IS NULL),
and idempotently upserts into PostgreSQL catalog_items table.
"""
import argparse
import hashlib
import json
import logging
import math
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vulcan.seed_candidates")


def compute_hash_embedding(text: str, dim: int = 1536) -> list[float]:
    """Deterministic hash-based embedding for vector index population when real embedding is absent."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    raw = []
    for i in range(dim):
        seed = hashlib.sha256(h + i.to_bytes(4, "big")).digest()
        val = int.from_bytes(seed[:4], "big") / (2**32) * 2 - 1
        raw.append(val)
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw] if norm > 0 else raw


def find_default_corpus() -> Path:
    base = Path(__file__).resolve().parent.parent
    candidates = [
        base / "data" / "corpus" / "candidates_500.json",
        base / "backend" / "data" / "corpus" / "candidates_500.json",
        Path("data/corpus/candidates_500.json"),
        Path("backend/data/corpus/candidates_500.json"),
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Could not locate candidates_500.json in default search paths.")


def seed_candidates(corpus_path: Path, db_url: str, batch_size: int = 250) -> None:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        logger.critical("psycopg is required to seed candidates. Install psycopg[binary].")
        sys.exit(1)

    logger.info("Reading candidates from: %s", corpus_path)
    with open(corpus_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    logger.info("Loaded %d candidate records from corpus. Validating invariants...", len(items))

    # Validate steel-cage invariant (INV-1): candidates MUST NOT carry git_commit_sha
    for idx, it in enumerate(items):
        sha = it.get("git_commit_sha")
        if sha is not None:
            raise ValueError(
                f"Candidate invariant violation at item #{idx} ({it.get('identifier')}): "
                f"git_commit_sha must be null for CANDIDATE items, got: '{sha}'"
            )
        status = it.get("curation_status", "CANDIDATE")
        if status != "CANDIDATE":
            raise ValueError(
                f"Candidate invariant violation at item #{idx} ({it.get('identifier')}): "
                f"curation_status must be 'CANDIDATE', got: '{status}'"
            )

    logger.info("All %d candidate items satisfy INV-1 (git_commit_sha IS NULL). Connecting to PostgreSQL...", len(items))

    conn = psycopg.connect(db_url, row_factory=dict_row)
    conn.autocommit = False

    upsert_sql = """
        INSERT INTO catalog_items (
            id, identifier, name, engine, description,
            tags, git_commit_sha, git_repo, playbook_or_module_path,
            risk_tier, requires_maker_checker, requires_chg,
            input_schema, rollback_path, category,
            curation_status, provenance, embedding
        ) VALUES (
            %(id)s, %(identifier)s, %(name)s, %(engine)s, %(description)s,
            %(tags)s, %(git_commit_sha)s, %(git_repo)s, %(playbook_or_module_path)s,
            %(risk_tier)s, %(requires_maker_checker)s, %(requires_chg)s,
            %(input_schema)s, %(rollback_path)s, %(category)s,
            %(curation_status)s, %(provenance)s, %(embedding)s::vector
        )
        ON CONFLICT (identifier) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            curation_status = EXCLUDED.curation_status,
            git_commit_sha = EXCLUDED.git_commit_sha,
            git_repo = EXCLUDED.git_repo,
            playbook_or_module_path = EXCLUDED.playbook_or_module_path,
            risk_tier = EXCLUDED.risk_tier,
            requires_maker_checker = EXCLUDED.requires_maker_checker,
            requires_chg = EXCLUDED.requires_chg,
            input_schema = EXCLUDED.input_schema,
            category = EXCLUDED.category,
            tags = EXCLUDED.tags,
            provenance = EXCLUDED.provenance,
            embedding = EXCLUDED.embedding,
            updated_at = NOW();
    """

    inserted = 0
    try:
        with conn.cursor() as cur:
            for i, it in enumerate(items):
                text = f"{it['name']} {it.get('description','')} {it['identifier']} {' '.join(it.get('tags', []))}"
                emb = it.get("embedding") or compute_hash_embedding(text)
                emb_str = "[" + ",".join(str(v) for v in emb) + "]"

                params = {
                    "id": it["id"],
                    "identifier": it["identifier"],
                    "name": it["name"],
                    "engine": it.get("engine", "terraform"),
                    "description": it.get("description", ""),
                    "tags": it.get("tags", []),
                    "git_commit_sha": None,  # Strictly None for candidates
                    "git_repo": it.get("git_repo", ""),
                    "playbook_or_module_path": it.get("playbook_or_module_path", ""),
                    "risk_tier": it.get("risk_tier", "MEDIUM"),
                    "requires_maker_checker": it.get("requires_maker_checker", True),
                    "requires_chg": it.get("requires_chg", False),
                    "input_schema": json.dumps(it.get("input_schema", {})),
                    "rollback_path": it.get("rollback_path"),
                    "category": it.get("category", "cloud"),
                    "curation_status": "CANDIDATE",
                    "provenance": json.dumps(it.get("provenance", {})),
                    "embedding": emb_str,
                }
                cur.execute(upsert_sql, params)
                inserted += 1

                if inserted % batch_size == 0 or inserted == len(items):
                    conn.commit()
                    logger.info("  [+] Upserted %d / %d candidates...", inserted, len(items))

            conn.commit()

            # Verify total count in database
            cur.execute("""
                SELECT 
                    curation_status,
                    COUNT(*) as total_count,
                    COUNT(git_commit_sha) as with_sha,
                    COUNT(*) - COUNT(git_commit_sha) as null_sha
                FROM catalog_items
                GROUP BY curation_status
                ORDER BY curation_status;
            """)
            counts = cur.fetchall()
            logger.info("==================================================================")
            logger.info(" Database Verification Summary (catalog_items):")
            for c in counts:
                logger.info(
                    "   - %s: Total=%d | with_sha=%d | null_sha=%d",
                    c["curation_status"], c["total_count"], c["with_sha"], c["null_sha"]
                )
            logger.info("==================================================================")

    except Exception as e:
        conn.rollback()
        logger.exception("Seeding failed: %s", e)
        sys.exit(1)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Vulcan Candidate Catalog Seeder")
    parser.add_argument("--corpus", type=str, default=None, help="Path to candidates JSON corpus")
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL connection URL (or set DATABASE_URL/POSTGRES_URL)")
    parser.add_argument("--batch-size", type=int, default=250, help="Batch commit size")
    args = parser.parse_args()

    corpus_path = Path(args.corpus) if args.corpus else find_default_corpus()
    if not corpus_path.exists():
        logger.critical("Corpus file does not exist: %s", corpus_path)
        sys.exit(1)

    db_url = (
        args.db_url
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
    )
    if not db_url:
        logger.critical("DATABASE_URL or POSTGRES_URL environment variable must be set, or provide --db-url.")
        sys.exit(1)

    seed_candidates(corpus_path, db_url, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
