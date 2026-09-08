#!/usr/bin/env python3
"""
Project Vulcan: Historical State Backfill & Ledger Epoch Preserver
Author: Alex Xu & Uncle Bob

Migrates historical audit records from JSONL and historical execution jobs
from SQLite into PostgreSQL without breaking the cryptographic Merkle chain.
Enforces zero-epoch-break discipline: Genesis hash chain remains intact.
"""
import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend" if (REPO_ROOT / "backend").exists() else REPO_ROOT
sys.path.insert(0, str(BACKEND_DIR))

from app.domain.entities import AuditRecord
from app.adapters.postgres_audit_adapter import PostgresAuditAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vulcan.backfill")


def backfill_history(
    jsonl_path: Path,
    sqlite_path: Path,
    db_url: str
) -> bool:
    if not db_url:
        logger.error("Database URL is required.")
        return False

    logger.info("==================================================================")
    logger.info(" Project Vulcan: Historical Data Backfill & Merkle Epoch Check")
    logger.info(" JSONL source:  %s", jsonl_path)
    logger.info(" SQLite source: %s", sqlite_path)
    logger.info("==================================================================")

    # 1. Verify JSONL chain integrity locally before touching DB
    records = []
    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        logger.info("Loaded %d historical audit records from %s", len(records), jsonl_path)

        expected_prev = "0" * 64
        for r in records:
            prev_h = r.get("prev_hash", "")
            curr_h = r.get("current_hash", "")
            calc_h = AuditRecord.compute_hash(
                correlation_id=r["correlation_id"],
                timestamp=r["timestamp"],
                actor=r["actor"],
                action=r["action"],
                payload=r["payload"],
                prev_hash=prev_h
            )
            if prev_h != expected_prev:
                logger.critical("Source JSONL chain broken at record #%s: prev != expected", r.get("id"))
                return False
            if calc_h != curr_h:
                logger.critical("Source JSONL hash mismatch at record #%s: calc != curr", r.get("id"))
                return False
            expected_prev = curr_h
        logger.info("✓ Source JSONL chain verified: unbroken from Genesis to tip %s...", expected_prev[:16])
    else:
        logger.warning("JSONL audit file not found at %s; skipping audit backfill.", jsonl_path)

    # 2. Insert into PostgreSQL audit_ledger
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Check current table state
            cur.execute("SELECT COUNT(*), MIN(id), MAX(id) FROM audit_ledger;")
            cnt, min_id, max_id = cur.fetchone()
            logger.info("Current PostgreSQL audit_ledger: count=%s, min_id=%s, max_id=%s", cnt, min_id, max_id)

            if cnt == 0 and records:
                logger.info("Inserting %d historical records into audit_ledger...", len(records))
                for r in records:
                    cur.execute("""
                        INSERT INTO audit_ledger (
                            id, correlation_id, timestamp, actor, action,
                            payload, prev_hash, current_hash, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING;
                    """, (
                        r["id"],
                        r["correlation_id"],
                        r["timestamp"],
                        r["actor"],
                        r["action"],
                        json.dumps(r["payload"]),
                        r["prev_hash"],
                        r["current_hash"],
                        r["timestamp"]
                    ))
                cur.execute("SELECT setval(pg_get_serial_sequence('audit_ledger', 'id'), (SELECT MAX(id) FROM audit_ledger));")
                conn.commit()
                logger.info("✓ Successfully backfilled audit ledger and updated sequence.")
            elif cnt > 0:
                logger.info("audit_ledger already has %d records; preserving existing state.", cnt)

            # 3. Backfill Execution Jobs from SQLite
            if sqlite_path.exists():
                s_conn = sqlite3.connect(sqlite_path)
                s_cur = s_conn.cursor()
                s_cur.execute("SELECT * FROM execution_jobs;")
                col_names = [d[0] for d in s_cur.description]
                sqlite_rows = [dict(zip(col_names, row)) for row in s_cur.fetchall()]
                logger.info("Loaded %d jobs from SQLite %s", len(sqlite_rows), sqlite_path)

                cur.execute("SELECT id FROM execution_jobs;")
                pg_ids = {row[0] for row in cur.fetchall()}

                missing = [r for r in sqlite_rows if r["id"] not in pg_ids]
                logger.info("Found %d jobs missing in PostgreSQL; backfilling...", len(missing))

                for r in missing:
                    params_val = r.get("parameters") or "{}"
                    cur.execute("""
                        INSERT INTO execution_jobs (
                            id, correlation_id, catalog_identifier, status, risk_tier,
                            requester_id, approver_id, dispatched_by, target_resource_id, environment,
                            parameters, servicenow_chg, storage_artifact_uri,
                            storage_artifact_sha256, approval_requested_at,
                            approval_decision, exit_code, error_message,
                            created_at, started_at, completed_at
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s::jsonb, %s, %s,
                            %s, %s,
                            %s::jsonb, %s, %s,
                            %s, %s, %s
                        ) ON CONFLICT (id) DO NOTHING;
                    """, (
                        r.get("id"),
                        r.get("correlation_id"),
                        r.get("catalog_identifier"),
                        r.get("status"),
                        r.get("risk_tier"),
                        r.get("requester_id"),
                        r.get("approver_id"),
                        r.get("dispatched_by"),
                        r.get("target_resource_id") or "unspecified",
                        r.get("environment") or "PROD",
                        params_val if isinstance(params_val, str) else json.dumps(params_val),
                        r.get("servicenow_chg"),
                        r.get("storage_artifact_uri"),
                        r.get("storage_artifact_sha256"),
                        r.get("approval_requested_at"),
                        r.get("approval_decision"),
                        r.get("exit_code"),
                        r.get("error_message"),
                        r.get("created_at"),
                        r.get("started_at"),
                        r.get("completed_at")
                    ))
                conn.commit()
                cur.execute("SELECT COUNT(*) FROM execution_jobs;")
                logger.info("✓ Total PostgreSQL execution_jobs after backfill: %d", cur.fetchone()[0])
            else:
                logger.warning("SQLite database not found at %s; skipping jobs backfill.", sqlite_path)

    # 4. Final Merkle Chain Verification via Adapter
    adapter = PostgresAuditAdapter(db_url=db_url)
    is_valid = adapter.verify_integrity()
    tip_hash = adapter.get_last_hash()
    logger.info("------------------------------------------------------------------")
    logger.info(" Merkle Ledger Integrity Check: %s (Head Hash: %s)", "VALID" if is_valid else "CORRUPT", tip_hash)
    logger.info("------------------------------------------------------------------")
    return is_valid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vulcan Historical Data Backfill")
    parser.add_argument("--jsonl-path", type=Path, default=Path("/app/data/audit_ledger.jsonl"))
    parser.add_argument("--sqlite-path", type=Path, default=Path("/app/data/vulcan.db"))
    parser.add_argument("--db-url", type=str, default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()

    # If running locally outside container, adjust paths if /app doesn't exist
    jsonl = args.jsonl_path
    if not jsonl.exists() and (REPO_ROOT / "backend" / "data" / "audit_ledger.jsonl").exists():
        jsonl = REPO_ROOT / "backend" / "data" / "audit_ledger.jsonl"

    sqlite = args.sqlite_path
    if not sqlite.exists() and (REPO_ROOT / "backend" / "data" / "vulcan.db").exists():
        sqlite = REPO_ROOT / "backend" / "data" / "vulcan.db"

    success = backfill_history(jsonl, sqlite, args.db_url)
    sys.exit(0 if success else 1)
