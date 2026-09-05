# Vulcan MVP Task Board

Tasks are completed only after two defect-free ECC critiques and independent verifier sign-off.

- [~] Monorepo scaffold: apps/api, apps/sync, apps/worker, packages/domain, packages/contracts; startable process entrypoints, per-process Dockerfiles, and dedicated Compose with Postgres/Redis/MinIO (runtime integration pending)
- [~] Domain: board aggregate, principal/capability model, BoardUpdatePublisher port
- [~] Persistence: append-only repository contract, PostgreSQL adapter with transaction-scoped board locking, contiguous replay sequences, snapshots, migrations for identity/sharing/AI/audit tables, and tamper-evident audit ledger (independent verifier sign-off pending)
- [~] Sync gateway: ordered replay log, bounded 5 MB queues, 150 ms lossy presence, Yjs board session, Redis Streams-compatible adapter, authenticated WebSocket broadcast, and reconnect replay (Redis integration soak/backpressure tests pending)
- [~] Share links + guest sessions: hashed scoped tokens, ≤24h expiry, write quotas, and revocation checks bounded to 60s (API/cache integration pending)
- [~] AI pipeline: sanitized and 8K-token bounded context, Zod validation, idempotent generation, repair/retry policy, preview/confirm commit, and idempotent worker queue (Redis transport/operational retries pending)
- [~] Layered rate limits with injectable clock/port (domain window limiter covered; API integration pending)
- [~] Correlation context/tracer contract carrying request, board, operation, and generation IDs (OpenTelemetry exporter wiring pending)
- [~] Frontend editor route with synced/offline/reconnecting/rejected states, unsynced count, and 10K/50-cursor fixture (Playwright interaction coverage pending)
- [~] Tests/CI: root typecheck, lint, unit, API loopback integration, build, frontend checks, compose-config smoke gate, and GitHub workflow (database/E2E/perf/coverage gates pending)

## Evidence

Domain RED/GREEN evidence: `packages/domain/src/board.test.ts`; run `npm test` from this directory after TypeScript dependencies are installed.
Persistence, audit, rate-limit, sync, AI, observability, guest-session, API, and worker RED/GREEN evidence: `packages/domain/src/persistence.test.ts`, `packages/domain/src/audit.test.ts`, `packages/domain/src/rate-limit.test.ts`, `packages/domain/src/sync.test.ts`, `packages/domain/src/ai-pipeline.test.ts`, `packages/domain/src/ai.test.ts`, `packages/domain/src/observability.test.ts`, `packages/domain/src/guest-session.test.ts`, `packages/domain/src/security.test.ts`, `apps/sync/src/index.test.ts`, `apps/api/src/index.test.ts`, `apps/worker/src/index.test.ts`; latest combined run: 56 tests passed, including server-authoritative workspace/board creation with membership checks, Redis generation consumption with status transitions and acknowledgements, snapshot-surviving API idempotency lookup, generation board binding, anchored prompt sanitization, atomic one-transaction AI proposal application, finite-geometry rejection, same-millisecond Redis stream cursor replay, serialized concurrent WebSocket idempotency, replay-backend failure reporting, the 10K-element sync materialization benchmark, injected-clock share-link expiry, runtime share-scope validation, guest write capability/expiry rechecks, Redis generation deduplication with atomic NX claims and claim cleanup after stream failure, API rate-limit and OTLP exporter coverage, and quota regression coverage, with all workspace typechecks/builds passed. Recursive workspace tests now execute for every package. `npm run smoke:postgres` passed against a fresh PostgreSQL container, applying both migrations and exercising append, idempotency, snapshot, and tail loading. Dedicated Compose runtime smoke passed with API `/healthz` returning 200 and API, sync, worker, PostgreSQL, Redis, and MinIO services starting successfully. Frontend `/whiteboard` typecheck and production build pass.
Independent verifier: pending; harness agents were unavailable because no active model credentials were exposed.

Latest hardening evidence: the API source-IP limiter regression passes with rotating capabilities; current root suite is 56 tests green. Workspace/board creation, persistent identity storage, Redis worker consumption, bounded API request bodies, and production `/whiteboard` HTTP smoke coverage, and share-link revocation are merged to `main`.
