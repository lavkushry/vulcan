# Project Vulcan: Verification Walkthrough & Live Production Sync

**Live Deployment Host:** `http://141.148.195.233:3000` (Oracle Cloud VM, Ubuntu 22.04 LTS)  
**Backend API & Swagger:** `http://141.148.195.233:8000/docs`  
**Git Commit:** [`bcf995b`](https://github.com/lavkushry/vulcan/commit/bcf995b) (`main`)  
**Backend PyTest Matrix:** 118 passed in 3.48s  
**Deterministic Reality Probes:** 11/11 Probes 🟢 PASSED  

---

## 1. Accomplished Objectives

### A. Live MinIO S3 Object Storage & BKND-14 Lifecycle (`boto3` Integration)
- **Live Boto3 Gateway:** Implemented [`S3MultipartGateway`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/s3_multipart_adapter.py) wired to the live `vulcan-minio` container (`http://minio:9000`) with AWS Signature Version 4 (`s3v4`).
- **External URL Rewriter:** Presigned PUT upload URLs are rewritten via `rewrite_presigned_url` to translate internal Docker origins (`http://minio:9000`) into externally reachable browser endpoints (`http://141.148.195.233:9000`).
- **End-to-End Live Verification:** Executed multi-part chunk PUT upload, completed assembly into `s3://vulcan-artifacts/jobs/JOB-LIVE-1/smoke_test_blob.bin`, verified metadata SHA-256 integrity, and ran orphaned upload cleanup.
- **BKND-14 Abort & Orphan Sweep:** Added `abort_multipart_upload` and `cleanup_orphaned_uploads` to sweep unfinished uploads older than `max_age_seconds`.

### B. Decoupled Dependency Injection & Circular Import Resolution
- **Root Cause Identified:** Standalone import `from app.config import container` previously failed when Redis was active because `AppContainer.__init__` imported `ws_hub` which loaded `app.api.__init__` -> `server.py` -> `routes.py` -> `from app.config import container`.
- **Clean Architecture Resolution:** Decoupled `ws_hub.set_redis_client` out of `AppContainer.__init__` and moved it into the FastAPI `lifespan` handler in [`app/api/server.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/api/server.py).
- `app.config` is now completely pure and independent of the API presentation layer.

### C. Live Real Ansible Playbook Execution on Sandbox (`vulcan-sandbox`)
- **Container Target:** Connected `vulcan-backend` to `vulcan-sandbox` over OpenSSH using Ed25519 key authentication (`/app/ansible/keys/id_ed25519`).
- **Live Ping & Fact Gathering:** Executed `ansible/playbooks/ping_check.yml` via [`AnsibleRunnerExecutionEngine`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/backend/app/adapters/ansible_runner_adapter.py).
- **Execution Pipeline:** Dispatched via `POST /api/v1/jobs` -> `POST /api/v1/jobs/EXEC-348B32/execute`, ran in background worker thread, streamed 37 lines of live stdout through `ws_hub` ring buffer, and returned `status: SUCCESS` with `exit_code: 0`.

### D. Deterministic Reality Verification Suite
- Maintained [`scripts/verify-matrix-claims.py`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/scripts/verify-matrix-claims.py) with 11 strict probes covering:
  1. D4 RBAC Gate (Lead authorized, Operator 403)
  2. D2 ServiceNow Fail-Closed
  3. Frozen 14-State Machine Invariant
  4. Maker-Checker 15-Minute Timeout
  5. INV-1 Candidate Execution Blocking
  6. SQLite WAL Crash-Recovery
  7. Cryptographic Merkle Ledger Tamper Detection
  8. BPE Subword Tokenizer Budgeting
  9. Stack Composer 40-char SHA Binding
  10. Remote VM Health Check (`http://141.148.195.233:8000/healthz`)
  11. S3 Multipart Lifecycle & BKND-14 Cleanup

---

## 2. Verification Results Summary

```
=================================================================
        PROJECT VULCAN: REALITY MATRIX VERIFICATION PROBES        
=================================================================
🟢 D4_APPROVAL_RBAC               : PASSED (Operator: Blocked, Lead: Allowed, SecAdmin: Blocked)
🟢 D2_SERVICENOW_FAIL_CLOSED      : PASSED (Unknown ticket rejected, windows return False)
🟢 STATE_MACHINE_14_STATES        : PASSED (14/14 states present)
🟢 APPROVAL_TIMEOUT               : PASSED (Transitioned to TIMEOUT_DENIED)
🟢 INV1_EXECUTION_BLOCK           : PASSED: PolicyViolationError raised, EXEC_BLOCKED recorded
🟢 SQLITE_PERSISTENCE             : PASSED (Recovered across process instance boundaries)
🟢 MERKLE_AUDIT_LEDGER            : PASSED (Clean chain verified, tampering instantly detected)
🟢 BPE_TOKENIZER                  : PASSED (25 tokens measured)
🟢 STACK_COMPOSER_SHA             : PASSED (Rejects non-40-char commit SHAs with ParameterValidationError)
🟢 REMOTE_VM_HEALTH               : PASSED (HTTP 200 OK - Backend ALIVE)
🟢 S3_MULTIPART_LIFECYCLE         : PASSED (205-chunk math, browser host rewrite & BKND-14 abort)
=================================================================
```

### PyTest Suite
```
118 passed, 2 warnings in 3.48s
```
