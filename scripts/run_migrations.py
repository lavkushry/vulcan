#!/usr/bin/env python3
"""
Project Vulcan: Idempotent PostgreSQL Migration Runner
Applies all SQL migrations in backend/migrations/*.sql in alphanumeric order,
tracking applied versions in the schema_migrations table.
Works cleanly in local environments, CI service containers, and production.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if (BASE_DIR / "backend" / "migrations").exists():
    MIGRATIONS_DIR = BASE_DIR / "backend" / "migrations"
elif (BASE_DIR / "migrations").exists():
    MIGRATIONS_DIR = BASE_DIR / "migrations"
elif Path("/app/migrations").exists():
    MIGRATIONS_DIR = Path("/app/migrations")
else:
    MIGRATIONS_DIR = BASE_DIR / "backend" / "migrations"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vulcan.migrate")


def run_migrations(db_url: str, migrations_dir: str = None) -> None:
    target_dir = Path(migrations_dir) if migrations_dir else MIGRATIONS_DIR
    try:
        import psycopg
    except ImportError:
        logger.critical("psycopg is required to run migrations. Install psycopg[binary].")
        sys.exit(1)

    logger.info("Connecting to PostgreSQL to run migrations from %s...", target_dir)
    conn = psycopg.connect(db_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            # 1. Ensure migrations tracking table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()

            # 2. Get list of already applied migrations
            cur.execute("SELECT version FROM schema_migrations;")
            applied = {row[0] for row in cur.fetchall()}

            # 3. Find and sort all SQL files
            migration_files = sorted(target_dir.glob("*.sql"))
            if not migration_files:
                logger.warning("No migration files found in %s", target_dir)
                return

            applied_count = 0
            for mf in migration_files:
                version = mf.name
                if version in applied:
                    logger.info("  [-] %s already applied, skipping.", version)
                    continue

                logger.info("  [+] Applying migration: %s...", version)
                sql_content = mf.read_text(encoding="utf-8")
                
                # Execute migration
                cur.execute(sql_content)
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s);", (version,))
                conn.commit()
                applied_count += 1
                logger.info("  [✓] Successfully applied: %s", version)

            logger.info("Migration complete: %d new migrations applied. Total applied: %d.",
                        applied_count, len(applied) + applied_count)

    except Exception as e:
        conn.rollback()
        logger.exception("Migration failed: %s", e)
        sys.exit(1)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Vulcan PostgreSQL Migration Runner")
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL connection URL")
    parser.add_argument("--migrations-dir", type=str, default=None, help="Custom path to migrations directory")
    args = parser.parse_args()

    db_url = (
        args.db_url
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or "postgresql://vulcan_admin:vulcan_secret_pnc_2026@localhost:5432/vulcan_control_plane"
    )

    run_migrations(db_url, migrations_dir=args.migrations_dir)


if __name__ == "__main__":
    main()
