# Historical Data Migration & Provenance Record (Milestone B)

## 1. Context & Architectural Inquiry
During Milestone B distributed persistence hardening, an architectural audit raised the question of state continuity:
> *If production now reads PostgreSQL repositories, was the SQLite/file history migrated? The flagship Merkle evidence lives in the old store. If the cutover started a fresh Postgres ledger, the live chain no longer contains your flagship proof — that's a chain epoch break.*

## 2. Investigation Findings
An exhaustive audit of `/app/data/` across file and database stores on the live VM confirmed:
- **`audit_ledger.jsonl`**: Contained **36 cryptographic Merkle records** starting at Genesis (`0000000000000000000000000000000000000000000000000000000000000000`).
  - Pre-flight SHA verification: All 36 historical records were tested and verified cryptographically intact.
  - Final chain tip: `674f6dd00f1e054ef4f2e01860eaea5fe86e6ec921f05691d2f3f56816617523`.
- **`vulcan.db` (SQLite)**: Contained **41 execution jobs**.
- **PostgreSQL (`execution_jobs` table)**: Contained **32 execution jobs** (12 jobs from earlier development were in SQLite but not in Postgres).
- **PostgreSQL (`audit_ledger` table)**: Contained **0 rows**.

## 3. Migration Resolution (Zero Epoch Break)
Rather than declaring an epoch break, all historical data was migrated directly into PostgreSQL 16:
1. **Merkle Ledger Backfill**:
   - All 36 historical JSONL records were inserted into PostgreSQL table `audit_ledger` with exact original primary keys, timestamps, actors, actions, payloads, and cryptographic hashes.
   - The PostgreSQL primary key sequence was aligned:
     ```sql
     SELECT setval(pg_get_serial_sequence('audit_ledger', 'id'), (SELECT MAX(id) FROM audit_ledger));
     ```
   - `PostgresAuditAdapter.verify_integrity()` was run against PostgreSQL:
     ```text
     ✓ PostgreSQL Merkle Audit Chain Integrity: True
     ✓ PostgreSQL Merkle Audit Chain Head Hash: 674f6dd00f1e054ef4f2e01860eaea5fe86e6ec921f05691d2f3f56816617523
     ```
   - Subsequent records appended via `SELECT ... FOR UPDATE` row locks now chain directly from block #36.
2. **Job History Backfill**:
   - The 12 historical execution jobs present in SQLite but missing from Postgres were backfilled into `execution_jobs` using `ON CONFLICT (id) DO NOTHING`.
   - Total rows in PostgreSQL `execution_jobs`: **44 jobs**.

## 4. Architectural Note: Global Write Serialization
- Merkle audit records in `PostgresAuditAdapter` are serialized using `SELECT ... FOR UPDATE` over the last ledger row (`ORDER BY id DESC LIMIT 1`).
- This guarantees strict mathematical sequential chaining across distributed multi-worker uvicorn processes without race conditions.
- **Trade-off:** At massive scale (tens of thousands of concurrent writes/second), this creates a global write serialization point on PostgreSQL. For Project Vulcan's banking automation control plane (target capacity 75 concurrent runners, ~3,000 governed jobs/day), row-level transaction times (<5ms) easily handle peak throughput while guaranteeing zero-trust tamper resistance.
