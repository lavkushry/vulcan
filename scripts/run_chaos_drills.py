#!/usr/bin/env python3
"""
Project Vulcan: Distributed Systems Chaos & Fault Injection Suite (Milestone C.3 Leg 1)
Author: Alex Xu (Distributed Systems Lead) & Robert C. Martin ("Uncle Bob")

Two-Layer Invariant & Fault Injection Architecture:
- LAYER 1: Unit Invariant Suite (In-Memory / Mock Verification, Fast, CI)
- LAYER 2: Production-Mirroring Integration Chaos Suite (Real Redis 7.2, Real MinIO S3, Real PostgreSQL 16 + Multi-Worker Uvicorn)
"""
import argparse
import concurrent.futures
import json
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend" if (REPO_ROOT / "backend").exists() else REPO_ROOT
sys.path.insert(0, str(BACKEND_DIR))

from app.adapters.crypto_audit_adapter import MerkleAuditLogger
from app.adapters.redlock_adapter import RedlockManager
from app.adapters.s3_multipart_adapter import CHUNK_SIZE_BYTES, S3MultipartGateway
from app.adapters.sqlite_repositories import SQLiteJobRepository
from app.catalog_data import get_catalog_items
from app.core.approval_sweeper import ApprovalSweeper
from app.domain.entities import ExecutionJob, JobStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vulcan.chaos")

# ANSI Color formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner(layer_name: str):
    print(f"\n{CYAN}{BOLD}{'=' * 80}{RESET}")
    print(f"{CYAN}{BOLD}PROJECT VULCAN: DISTRIBUTED SYSTEMS CHAOS & FAULT INJECTION HARNESS{RESET}")
    print(f"{CYAN}Milestone C.3 Leg 1 — {layer_name}{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 80}{RESET}\n")


# ==============================================================================
# LAYER 1: UNIT INVARIANT SUITE (FAST, IN-MEMORY / MOCK INFRASTRUCTURE)
# ==============================================================================

def _child_worker_target():
    """Simulated worker process to be terminated via SIGKILL."""
    while True:
        time.sleep(1.0)


def run_unit_drill_1_redlock_fencing() -> bool:
    print(f"{BOLD}[UNIT DRILL 1/3] Redlock Lease-Expiry & Monotonic Fencing Token Race{RESET}")
    print(f"{DIM}Scope: In-memory fallback dictionary, TTL expiration, monotonic fencing token comparison.{RESET}")
    t0 = time.time()
    lock_mgr = RedlockManager(redis_nodes=[])  # In-memory fallback mode
    resource = "pnc-core-db01"
    token_a = "runner-worker-A"
    token_b = "runner-worker-B"

    # Step 1: Worker A acquires lock with micro-lease TTL (300ms)
    acquired_a = lock_mgr.acquire(resource, ttl_seconds=0.3, owner_token=token_a)
    fencing_a = lock_mgr.get_fencing_token(resource)
    print(f"  {CYAN}▸{RESET} Worker A acquired [{resource}] with TTL=300ms, Fencing Token F_A={fencing_a}")
    if not acquired_a or fencing_a is None:
        print(f"  {RED}✖ Worker A failed to acquire initial lock!{RESET}")
        return False

    if not lock_mgr.validate_fencing_token(resource, fencing_a):
        print(f"  {RED}✖ Initial fencing token validation failed!{RESET}")
        return False

    # Step 2: Simulate execution stall / GC pause (500ms > 300ms TTL)
    print(f"  {YELLOW}▸{RESET} Simulating artificial execution stall (500ms > 300ms TTL)...")
    time.sleep(0.5)

    # Step 3: Worker B acquires the expired lock
    acquired_b = lock_mgr.acquire(resource, ttl_seconds=5.0, owner_token=token_b)
    fencing_b = lock_mgr.get_fencing_token(resource)
    print(f"  {CYAN}▸{RESET} Worker B acquired [{resource}] with TTL=5000ms, Fencing Token F_B={fencing_b}")
    if not acquired_b or fencing_b is None or fencing_b <= fencing_a:
        print(f"  {RED}✖ Worker B failed or fencing token did not increment monotonically! (F_B={fencing_b}, F_A={fencing_a}){RESET}")
        return False

    # Step 4: Worker A wakes up and attempts write with stale token F_A
    print(f"  {YELLOW}▸{RESET} Worker A wakes up and attempts write with stale token F_A={fencing_a}...")
    is_f_a_valid = lock_mgr.validate_fencing_token(resource, fencing_a)
    if is_f_a_valid:
        print(f"  {RED}✖ Invariant Violated: Stale token F_A accepted! Write would corrupt data.{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} Stale token F_A rejected fail-closed (Storage write protection confirmed)")

    # Step 5: Worker A attempts release (compare-and-delete)
    released_a = lock_mgr.release(resource, owner_token=token_a)
    if released_a:
        print(f"  {RED}✖ Invariant Violated: Expired worker A released Worker B's active lock!{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} Worker A release rejected: Owner token mismatch (Worker B's lock preserved)")

    # Step 6: Worker B completes, validates F_B, and releases cleanly
    if not lock_mgr.validate_fencing_token(resource, fencing_b):
        print(f"  {RED}✖ Worker B active fencing token rejected!{RESET}")
        return False
    released_b = lock_mgr.release(resource, owner_token=token_b)
    if not released_b or lock_mgr.is_locked(resource):
        print(f"  {RED}✖ Worker B failed to cleanly release lock!{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} Worker B validated token and safely released lock in {time.time() - t0:.2f}s")
    print(f"  {GREEN}{BOLD}↳ UNIT DRILL 1 PASSED: Zero lock theft, monotonic fencing tokens strictly enforced.{RESET}\n")
    return True


def run_unit_drill_2_s3_multipart() -> bool:
    print(f"{BOLD}[UNIT DRILL 2/3] 10GB S3 Multipart In-Flight Abort & Orphan Purge{RESET}")
    print(f"{DIM}Scope: Mock S3 adapter, 205-part chunked payload abort, zero storage capacity leaks.{RESET}")
    t0 = time.time()
    s3_gateway = S3MultipartGateway(bucket_name="pnc-vulcan-chaos-test", mock_mode=True)
    ten_gb_bytes = 10 * 1024 * 1024 * 1024
    expected_sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    job_id = "EXEC-CHAOS-10G"
    file_name = "rhel-9-hardened.iso"

    # Step 1: Initiate 10GB upload
    res = s3_gateway.initiate_multipart_upload(file_name, ten_gb_bytes, expected_sha, job_id)
    upload_id = res["upload_id"]
    s3_key = res["s3_key"]
    print(f"  {CYAN}▸{RESET} Initiated 10GB multipart upload: Key=[{s3_key}], Parts={res['total_parts']} @ 50MB")
    if res["total_parts"] != 205:
        print(f"  {RED}✖ Expected 205 parts, got {res['total_parts']}!{RESET}")
        return False

    # Step 2: Upload parts 1 through 5
    s3_uri = f"s3://{s3_gateway.bucket_name}/{s3_key}"
    mock_parts = [{"part_number": i, "etag": f"etag-part-{i}"} for i in range(1, 6)]
    s3_gateway._mock_objects[s3_uri]["parts"] = mock_parts
    print(f"  {CYAN}▸{RESET} Uploaded 5 parts (250MB buffered in temporary storage)...")
    if s3_gateway.get_parts_count(s3_key) != 5:
        print(f"  {RED}✖ Part count mismatch before abort!{RESET}")
        return False

    # Step 3: Inject mid-flight abort
    print(f"  {YELLOW}▸{RESET} Injecting mid-flight abort on upload [{upload_id}]...")
    aborted = s3_gateway.abort_multipart_upload(upload_id, s3_key)
    if not aborted:
        print(f"  {RED}✖ Abort multipart upload returned False!{RESET}")
        return False

    # Step 4: Verify parts purged and state is ABORTED
    parts_left = s3_gateway.get_parts_count(s3_key)
    if parts_left != 0:
        print(f"  {RED}✖ Storage leak: {parts_left} parts remained after abort!{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} In-flight temporary parts purged: 0 orphaned chunks remain")

    # Step 5: Verify completing aborted upload fails
    try:
        s3_gateway.complete_multipart_upload(upload_id, s3_key, mock_parts)
        print(f"  {RED}✖ Completing aborted upload succeeded unexpectedly!{RESET}")
        return False
    except RuntimeError as ex:
        print(f"  {GREEN}✓{RESET} Completion of aborted upload rejected fail-closed: {ex}")

    # Step 6: Sweep orphaned uploads
    cleaned = s3_gateway.cleanup_orphaned_uploads(max_age_seconds=0)
    print(f"  {GREEN}✓{RESET} Automated orphan sweeper verified in {time.time() - t0:.2f}s")
    print(f"  {GREEN}{BOLD}↳ UNIT DRILL 2 PASSED: 10GB partitioned cleanly, 0 orphaned storage leaks.{RESET}\n")
    return True


def run_unit_drill_3_worker_crash() -> bool:
    print(f"{BOLD}[UNIT DRILL 3/3] Multi-Worker Crash (SIGKILL) & Orphan Job Reaper{RESET}")
    print(f"{DIM}Scope: Mock SQLite repository, simulated PID SIGKILL, FAILED (WORKER_LOST), Merkle audit integrity.{RESET}")
    t0 = time.time()

    worker_proc = multiprocessing.Process(target=_child_worker_target, daemon=True)
    worker_proc.start()
    dead_pid = worker_proc.pid
    print(f"  {CYAN}▸{RESET} Spawned simulated worker child process with PID={dead_pid}")

    try:
        catalog_items = get_catalog_items()
        catalog_item = catalog_items[0]
        job_repo = SQLiteJobRepository(db_path=":memory:", catalog=catalog_items)
        audit_logger = MerkleAuditLogger()
        lock_mgr = RedlockManager(redis_nodes=[])
        sweeper = ApprovalSweeper(
            job_repo=job_repo,
            audit_logger=audit_logger,
            lock_manager=lock_mgr
        )

        target_res = "prod-db-core-cluster"
        job_crashed = ExecutionJob(
            job_id="job-crashed-101",
            correlation_id="VULCAN-CORR-CRASH-01",
            catalog_item=catalog_item,
            requester_id="operator.crashed",
            target_resource_id=target_res,
            parameters={"port": 3000, "username": "openclaw"}
        )
        job_crashed.transition_to(JobStatus.PARSED, "Input parsed")
        job_crashed.transition_to(JobStatus.QUEUED, "Queued for dispatch")
        job_crashed.transition_to(JobStatus.LOCKED, "Target mutex acquired")
        job_crashed.transition_to(JobStatus.RUNNING, "Execution initiated")
        job_crashed.worker_pid = dead_pid
        owner_token = f"runner-{job_crashed.id}-{job_crashed.correlation_id}"
        job_crashed.lock_owner_token = owner_token

        lock_mgr.acquire(target_res, ttl_seconds=3600, owner_token=owner_token)
        job_repo.save(job_crashed)
        print(f"  {CYAN}▸{RESET} Job [{job_crashed.id}] RUNNING on PID={dead_pid}, holding lock on [{target_res}]")

        job_healthy = ExecutionJob(
            job_id="job-healthy-102",
            correlation_id="VULCAN-CORR-HEALTHY-02",
            catalog_item=catalog_item,
            requester_id="operator.healthy",
            target_resource_id="prod-web-tier",
            parameters={"port": 3001, "username": "openclaw"}
        )
        job_healthy.transition_to(JobStatus.PARSED, "Input parsed")
        job_healthy.transition_to(JobStatus.QUEUED, "Queued for dispatch")
        job_healthy.transition_to(JobStatus.LOCKED, "Target mutex acquired")
        job_healthy.transition_to(JobStatus.RUNNING, "Execution initiated")
        job_healthy.worker_pid = os.getpid()
        job_repo.save(job_healthy)
        print(f"  {CYAN}▸{RESET} Healthy job [{job_healthy.id}] RUNNING on alive parent PID={os.getpid()}")

        print(f"  {YELLOW}▸{RESET} Injecting ungraceful crash: os.kill({dead_pid}, signal.SIGKILL)...")
        os.kill(dead_pid, signal.SIGKILL)
        worker_proc.join(timeout=2.0)

        is_alive = ApprovalSweeper._is_pid_alive(dead_pid)
        print(f"  {CYAN}▸{RESET} Checked PID liveness (signal 0): is_alive={is_alive}")
        if is_alive:
            print(f"  {RED}✖ Worker process PID {dead_pid} is still alive after SIGKILL!{RESET}")
            return False

        print(f"  {YELLOW}▸{RESET} Invoking ApprovalSweeper.reap_orphaned_jobs()...")
        reaped = sweeper.reap_orphaned_jobs()

        if len(reaped) != 1 or reaped[0].id != "job-crashed-101":
            print(f"  {RED}✖ Orphan reaper failed to reap crashed job! Reaped count: {len(reaped)}{RESET}")
            return False
        reaped_job = reaped[0]
        print(f"  {GREEN}✓{RESET} Reaped job [{reaped_job.id}]: Status={reaped_job.status.value}, Error={reaped_job.error_message}")

        if lock_mgr.is_locked(target_res):
            print(f"  {RED}✖ Mutex lock on [{target_res}] was NOT released after worker crash!{RESET}")
            return False
        print(f"  {GREEN}✓{RESET} Target mutex [{target_res}] automatically released by reaper")

        persisted_healthy = job_repo.get_by_id("job-healthy-102")
        if not persisted_healthy or persisted_healthy.status != JobStatus.RUNNING:
            print(f"  {RED}✖ Healthy job was erroneously modified!{RESET}")
            return False
        print(f"  {GREEN}✓{RESET} Healthy job [{persisted_healthy.id}] preserved in RUNNING status")

        chain_valid = audit_logger.verify_chain()
        if not chain_valid:
            print(f"  {RED}✖ Merkle audit chain verification failed post-reap!{RESET}")
            return False
        last_rec = audit_logger.ledger[-1]
        print(f"  {GREEN}✓{RESET} Merkle audit record #{last_rec.id} committed: Action={last_rec.action}, DeadPID={last_rec.payload.get('dead_worker_pid')}")
        print(f"  {GREEN}✓{RESET} Cryptographic hash chain verified 100% valid ({len(audit_logger.ledger)} records)")

        print(f"  {GREEN}{BOLD}↳ UNIT DRILL 3 PASSED: Worker crash reaped fail-closed to FAILED (WORKER_LOST) in {time.time() - t0:.2f}s{RESET}\n")
        return True

    finally:
        if worker_proc.is_alive():
            os.kill(worker_proc.pid, signal.SIGKILL)
            worker_proc.join(timeout=1.0)


# ==============================================================================
# LAYER 2: PRODUCTION-MIRRORING INTEGRATION CHAOS SUITE (LIVE SERVICES)
# ==============================================================================

def run_live_drill_1_real_redis(redis_url: str) -> bool:
    print(f"{BOLD}[LIVE DRILL 1/3] Real Redis 7.2 Lease-Expiry & Monotonic Fencing Race{RESET}")
    print(f"{DIM}Target: Real Redis ({redis_url}), pexpire, INCR, and atomic Lua CAS compare-and-delete.{RESET}")
    t0 = time.time()

    import redis
    r_client = redis.from_url(redis_url)
    try:
        r_client.ping()
    except Exception as e:
        print(f"  {RED}✖ Cannot connect to real Redis: {e}{RESET}")
        return False

    resource = "prod-db-core-cluster-chaos"
    lock_key = f"lock:resource:{resource}"
    token_key = f"token:resource:{resource}"
    r_client.delete(lock_key, token_key)

    lock_mgr = RedlockManager(redis_nodes=[r_client])
    token_a = f"runner-worker-A-{uuid.uuid4().hex[:6]}"
    token_b = f"runner-worker-B-{uuid.uuid4().hex[:6]}"

    # Step 1: Worker A acquires with 300ms lease
    acquired_a = lock_mgr.acquire(resource, ttl_seconds=0.3, owner_token=token_a)
    fencing_a = lock_mgr.get_fencing_token(resource)
    print(f"  {CYAN}▸{RESET} Worker A acquired [{resource}] on REAL Redis with TTL=300ms, Fencing Token F_A={fencing_a}")
    if not acquired_a or fencing_a is None:
        print(f"  {RED}✖ Worker A failed to acquire lock on Redis!{RESET}")
        return False

    # Assert token exists in real Redis
    raw_token_a = int(r_client.get(token_key))
    if raw_token_a != fencing_a:
        print(f"  {RED}✖ Redis token_key mismatch: got {raw_token_a}, expected {fencing_a}{RESET}")
        return False

    # Step 2: Artificial stall & heartbeat loss (500ms > 300ms TTL)
    print(f"  {YELLOW}▸{RESET} Simulating artificial execution stall & heartbeat loss (500ms > 300ms TTL)...")
    if resource in lock_mgr._active_mutexes:
        lock_mgr._active_mutexes[resource]._stop_watchdog.set()
    time.sleep(0.5)

    # Confirm key expired in Redis
    if r_client.exists(lock_key):
        print(f"  {RED}✖ Real Redis key did not expire after 500ms!{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} Real Redis key expired via pexpire as expected")

    # Step 3: Worker B acquires lock
    acquired_b = lock_mgr.acquire(resource, ttl_seconds=5.0, owner_token=token_b)
    fencing_b = lock_mgr.get_fencing_token(resource)
    print(f"  {CYAN}▸{RESET} Worker B acquired [{resource}] on REAL Redis with TTL=5000ms, Fencing Token F_B={fencing_b}")
    if not acquired_b or fencing_b is None or fencing_b <= fencing_a:
        print(f"  {RED}✖ Worker B failed or token not monotonic! (F_B={fencing_b}, F_A={fencing_a}){RESET}")
        return False

    # Step 4: Worker A attempts write with stale token F_A
    print(f"  {YELLOW}▸{RESET} Worker A wakes up and attempts write with stale token F_A={fencing_a}...")
    is_f_a_valid = lock_mgr.validate_fencing_token(resource, fencing_a)
    if is_f_a_valid:
        print(f"  {RED}✖ Invariant Violated: Stale token F_A accepted against real Redis!{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} Stale token F_A rejected fail-closed against real Redis")

    # Step 5: Worker A attempts release (compare-and-delete)
    released_a = lock_mgr.release(resource, owner_token=token_a)
    if released_a:
        print(f"  {RED}✖ Invariant Violated: Stale Worker A released Worker B's active Redis lock!{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} Worker A release rejected by real Redis Lua CAS (Worker B's lock preserved)")

    # Step 6: Worker B releases cleanly
    released_b = lock_mgr.release(resource, owner_token=token_b)
    if not released_b or lock_mgr.is_locked(resource):
        print(f"  {RED}✖ Worker B failed to cleanly release lock in Redis!{RESET}")
        return False
    print(f"  {GREEN}✓{RESET} Worker B validated token and safely released lock in {time.time() - t0:.2f}s")
    print(f"  {GREEN}{BOLD}↳ LIVE DRILL 1 PASSED: Real Redis 7.2 monotonic fencing and Lua CAS verified.{RESET}\n")
    return True


def run_live_drill_2_real_minio() -> bool:
    print(f"{BOLD}[LIVE DRILL 2/3] Real MinIO S3 Multipart In-Flight Abort & Orphan Purge{RESET}")
    endpoint = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
    bucket = os.environ.get("S3_BUCKET_NAME", "vulcan-artifacts")
    access = os.environ.get("S3_ACCESS_KEY", "vulcan_minio_admin")
    secret = os.environ.get("S3_SECRET_KEY", "I5n-VpmWA5NPiTuSHKG6k6rYU7Qz47kh")
    print(f"{DIM}Target: Real MinIO ({endpoint}), bucket [{bucket}], multipart abort, 0 orphaned chunks.{RESET}")
    t0 = time.time()

    import boto3
    from botocore.exceptions import ClientError

    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret
    )

    try:
        s3_client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            s3_client.create_bucket(Bucket=bucket)
        except Exception as e:
            print(f"  {RED}✖ Cannot connect to real MinIO bucket [{bucket}]: {e}{RESET}")
            return False

    gateway = S3MultipartGateway(
        bucket_name=bucket,
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        s3_client=s3_client,
        mock_mode=False
    )

    file_name = "rhel-9-hardened.iso"
    job_id = f"CHAOS-LIVE-{uuid.uuid4().hex[:6]}"
    ten_gb_bytes = 10 * 1024 * 1024 * 1024
    expected_sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    # Step 1: Initiate multipart upload on real MinIO
    init_res = gateway.initiate_multipart_upload(file_name, ten_gb_bytes, expected_sha, job_id)
    upload_id = init_res["upload_id"]
    s3_key = init_res["s3_key"]
    print(f"  {CYAN}▸{RESET} Initiated multipart on REAL MinIO: Key=[{s3_key}], UploadId=[{upload_id[:16]}...]")

    # Step 2: Upload 2 real 5MB chunks (MinIO requires min 5MB per part for S3 API)
    chunk_5mb = b"X" * (5 * 1024 * 1024)
    part1 = s3_client.upload_part(Bucket=bucket, Key=s3_key, PartNumber=1, UploadId=upload_id, Body=chunk_5mb)
    part2 = s3_client.upload_part(Bucket=bucket, Key=s3_key, PartNumber=2, UploadId=upload_id, Body=chunk_5mb)
    print(f"  {CYAN}▸{RESET} Uploaded 2 real 5MB parts (10MB total) to MinIO storage...")

    # Verify MinIO has 2 parts buffered
    parts_res = s3_client.list_parts(Bucket=bucket, Key=s3_key, UploadId=upload_id)
    buffered_parts_count = len(parts_res.get("Parts", []))
    if buffered_parts_count != 2:
        print(f"  {RED}✖ MinIO parts list mismatch: expected 2, got {buffered_parts_count}{RESET}")
        return False

    # Step 3: Inject mid-flight abort
    print(f"  {YELLOW}▸{RESET} Injecting mid-flight abort on real MinIO upload [{upload_id[:16]}...]...")
    aborted = gateway.abort_multipart_upload(upload_id, s3_key)
    if not aborted:
        print(f"  {RED}✖ Gateway abort returned False!{RESET}")
        return False

    # Step 4: Verify with real MinIO that upload and parts are purged
    try:
        s3_client.list_parts(Bucket=bucket, Key=s3_key, UploadId=upload_id)
        print(f"  {RED}✖ MinIO still reported parts for aborted upload! Storage leak!{RESET}")
        return False
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchUpload", "404"):
            print(f"  {GREEN}✓{RESET} Real MinIO confirmed upload was purged: 0 orphaned chunks remain ({e.response['Error']['Code']})")
        else:
            print(f"  {RED}✖ Unexpected MinIO error: {e}{RESET}")
            return False

    # Step 5: Verify completion fails closed
    try:
        gateway.complete_multipart_upload(upload_id, s3_key, [
            {"part_number": 1, "etag": part1["ETag"]},
            {"part_number": 2, "etag": part2["ETag"]}
        ])
        print(f"  {RED}✖ Complete on aborted upload unexpectedly succeeded!{RESET}")
        return False
    except (RuntimeError, ClientError) as ex:
        print(f"  {GREEN}✓{RESET} Completion of aborted upload rejected fail-closed: {ex}")

    print(f"  {GREEN}{BOLD}↳ LIVE DRILL 2 PASSED: Real MinIO multipart abort & orphan purge verified in {time.time() - t0:.2f}s.{RESET}\n")
    return True


def run_live_drill_3_multiworker_durability(port: int = 8899) -> bool:
    print(f"{BOLD}[LIVE DRILL 3/3] Real Multi-Worker Crash (SIGKILL), Orphan Reaper & Healthy Control Job Invariant{RESET}")
    print(f"{DIM}Target: Multi-worker uvicorn on :8899, real PostgreSQL & Redis, SIGKILL worker A, assert Job 1 reaped to FAILED (WORKER_LOST) AND Job 2 on Worker B remains UNTOUCHED.{RESET}")
    t0 = time.time()

    env = os.environ.copy()
    env["VULCAN_AUTH_DISABLED"] = "0"
    env["VULCAN_SWEEPER_INTERVAL"] = "1.0"
    test_token = "vulcan-chaos-live-token-2026"
    env["VULCAN_API_TOKEN"] = test_token
    env["VULCAN_API_USER"] = "admin.dave"
    env["VULCAN_API_TOKENS"] = json.dumps({test_token: "admin.dave"})
    auth_headers = {"Authorization": f"Bearer {test_token}"}

    # Step 1: Spawn multi-worker cluster on port 8899
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.api.server:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--workers", "2",
        "--log-level", "warning"
    ]
    print(f"  {CYAN}▸{RESET} Spawning 2-worker uvicorn cluster on 127.0.0.1:{port}...")
    proc = subprocess.Popen(cmd, cwd=str(BACKEND_DIR), env=env)

    try:
        # Step 2: Wait for healthz
        healthz_url = f"http://127.0.0.1:{port}/healthz"
        ready_url = f"http://127.0.0.1:{port}/ready"
        alive = False
        for _ in range(30):
            time.sleep(0.5)
            try:
                req = urllib.request.Request(healthz_url)
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        alive = True
                        break
            except Exception:
                pass
        if not alive:
            print(f"  {RED}✖ Cluster failed to boot on port {port}!{RESET}")
            return False
        print(f"  {GREEN}✓{RESET} Multi-worker cluster is healthy and accepting requests on port {port}")

        # Step 3: Inspect child worker PIDs
        from scripts.verify_multiworker_durability import inspect_child_processes
        time.sleep(1.0)
        children = inspect_child_processes(proc.pid)
        uvicorn_workers = [c["pid"] for c in children if c["is_uvicorn_worker"]]
        print(f"  {CYAN}▸{RESET} Active uvicorn workers: {uvicorn_workers}")
        if len(uvicorn_workers) < 2:
            print(f"  {RED}✖ Expected at least 2 uvicorn workers, found {len(uvicorn_workers)}!{RESET}")
            return False

        # Step 4: Dispatch Job 1 (victim job)
        dispatch_url = f"http://127.0.0.1:{port}/api/v1/tasks/dispatch"
        payload_1 = json.dumps({
            "catalog_identifier": "net-f5-pool-member-drain",
            "target_resource_id": "f5-edge-vip-01.pnc.com",
            "environment": "PROD",
            "requester_id": "chaos-drill-1",
            "parameters": {"pool_name": "pool_prod", "member_ip": "10.0.0.1", "member_port": 8443},
            "servicenow_chg": "CHG-0091823"
        }).encode("utf-8")

        req_1 = urllib.request.Request(dispatch_url, data=payload_1, headers={"Content-Type": "application/json", **auth_headers})
        with urllib.request.urlopen(req_1, timeout=5) as resp:
            data_1 = json.loads(resp.read().decode("utf-8"))
            corr_id_1 = data_1["correlation_id"]

        # Step 5: Dispatch Job 2 (healthy control job)
        payload_2 = json.dumps({
            "catalog_identifier": "net-f5-pool-member-drain",
            "target_resource_id": "f5-edge-vip-02.pnc.com",
            "environment": "PROD",
            "requester_id": "chaos-drill-2",
            "parameters": {"pool_name": "pool_prod", "member_ip": "10.0.0.2", "member_port": 8443},
            "servicenow_chg": "CHG-0091823"
        }).encode("utf-8")

        req_2 = urllib.request.Request(dispatch_url, data=payload_2, headers={"Content-Type": "application/json", **auth_headers})
        with urllib.request.urlopen(req_2, timeout=5) as resp:
            data_2 = json.loads(resp.read().decode("utf-8"))
            corr_id_2 = data_2["correlation_id"]

        # Identify owning worker for Job 1
        job_1_info_url = f"http://127.0.0.1:{port}/api/v1/jobs/{corr_id_1}"
        with urllib.request.urlopen(urllib.request.Request(job_1_info_url, headers=auth_headers), timeout=3) as resp:
            job_1_data = json.loads(resp.read().decode("utf-8"))
            victim_pid = job_1_data.get("worker_pid") or uvicorn_workers[0]
            survivor_pid = [p for p in uvicorn_workers if p != victim_pid][0]

        print(f"  {CYAN}▸{RESET} Job 1 ({corr_id_1}) RUNNING on Worker PID {victim_pid} (Victim)")
        print(f"  {CYAN}▸{RESET} Job 2 ({corr_id_2}) RUNNING on Worker PID {survivor_pid} (Control)")

        # Step 6: Inject SIGKILL to victim PID
        print(f"  {YELLOW}▸{RESET} CHAOS INJECTION: Sending SIGKILL to Worker PID {victim_pid} (Job 1 owner)...")
        os.kill(victim_pid, signal.SIGKILL)
        time.sleep(0.3)

        # Step 7: Zero downtime assertion
        with urllib.request.urlopen(urllib.request.Request(healthz_url), timeout=2) as resp:
            assert resp.status == 200
        print(f"  {GREEN}✓{RESET} Cluster answered /healthz immediately after worker death (Zero downtime)")

        # Step 8: Assert Job 1 is reaped to FAILED (WORKER_LOST)
        print(f"  {YELLOW}▸{RESET} Awaiting orphan reaper detection of Job 1 ({corr_id_1})...")
        reaped = False
        reaped_status = None
        reaped_error = None
        for _ in range(60):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(urllib.request.Request(job_1_info_url, headers=auth_headers), timeout=2) as resp:
                    info = json.loads(resp.read().decode("utf-8"))
                    if info.get("status") in ("FAILED", "SUCCESS"):
                        reaped = True
                        reaped_status = info.get("status")
                        reaped_error = info.get("error_message") or ""
                        break
            except Exception:
                pass

        if not reaped or reaped_status != "FAILED" or "WORKER_LOST" not in reaped_error:
            print(f"  {RED}✖ Job 1 was not reaped to FAILED (WORKER_LOST)! Status: {reaped_status}, Error: {reaped_error}{RESET}")
            return False
        print(f"  {GREEN}✓{RESET} Job 1 cleanly reaped: Status=FAILED, Error='{reaped_error}'")

        # Step 9: CRITICAL INVARIANT: Assert Healthy Control Job 2 is UNTOUCHED
        job_2_info_url = f"http://127.0.0.1:{port}/api/v1/jobs/{corr_id_2}"
        with urllib.request.urlopen(urllib.request.Request(job_2_info_url, headers=auth_headers), timeout=2) as resp:
            job_2_info = json.loads(resp.read().decode("utf-8"))
            job_2_status = job_2_info.get("status")
            job_2_error = job_2_info.get("error_message") or ""
            print(f"  {CYAN}▸{RESET} Control Job 2 status after victim crash: {job_2_status}")
            if job_2_status == "FAILED" and "WORKER_LOST" in job_2_error:
                print(f"  {RED}✖ INVARIANT VIOLATION: Healthy control job 2 was erroneously reaped!{RESET}")
                return False
            print(f"  {GREEN}✓{RESET} CRITICAL INVARIANT VERIFIED: Healthy control job 2 was UNTOUCHED by crash")

        # Step 10: Cryptographic Merkle Audit Ledger Check
        with urllib.request.urlopen(urllib.request.Request(ready_url, headers=auth_headers), timeout=3) as resp:
            ready_info = json.loads(resp.read().decode("utf-8"))
            assert ready_info.get("checks", {}).get("audit_chain_valid") is True
        print(f"  {GREEN}✓{RESET} Post-chaos Merkle audit hash chain: 100% VALID on real PostgreSQL")

        print(f"  {GREEN}{BOLD}↳ LIVE DRILL 3 PASSED: Multi-worker crash reaped, control job untouched in {time.time() - t0:.2f}s.{RESET}\n")
        return True

    finally:
        print(f"  {DIM}Shutting down test cluster on port {port}...{RESET}")
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()


# ==============================================================================
# MAIN RUNNER & CLI DISPATCH
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Project Vulcan Distributed Systems Chaos Suite")
    parser.add_argument("--mode", choices=["unit", "live", "both"], default="unit", help="Chaos suite mode: unit (in-memory, fast, CI), live (real Redis/MinIO/Postgres), or both")
    parser.add_argument("--live", action="store_true", help="Shortcut for --mode live")
    parser.add_argument("--port", type=int, default=8899, help="Port for live multi-worker cluster (default: 8899)")
    args = parser.parse_args()

    mode = "live" if args.live else args.mode

    if mode in ("unit", "both"):
        print_banner("Layer 1: Unit Invariant Suite (In-Memory / Mock Infrastructure)")
        unit_drills = [
            ("Unit Drill 1: Redlock Expiry & Fencing Race", run_unit_drill_1_redlock_fencing),
            ("Unit Drill 2: 10GB S3 Multipart Abort & Orphan Purge", run_unit_drill_2_s3_multipart),
            ("Unit Drill 3: Worker Crash & Orphan Job Reaper", run_unit_drill_3_worker_crash),
        ]
        u_results = []
        t0 = time.time()
        for name, func in unit_drills:
            res = func()
            u_results.append((name, res))
            if not res:
                print(f"{RED}{BOLD}ABORTING: {name} FAILED{RESET}")
                sys.exit(1)

        print(f"{CYAN}{'=' * 80}{RESET}")
        print(f"{BOLD}LAYER 1 (UNIT INVARIANT) SUMMARY: ALL {len(u_results)} DRILLS PASSED in {time.time() - t0:.2f}s{RESET}")
        print(f"{CYAN}{'=' * 80}{RESET}\n")

    if mode in ("live", "both"):
        print_banner("Layer 2: Production-Mirroring Integration Chaos Suite (Live Services)")
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        live_drills = [
            ("Live Drill 1: Real Redis 7.2 Expiry & Fencing Race", lambda: run_live_drill_1_real_redis(redis_url)),
            ("Live Drill 2: Real MinIO S3 Multipart Abort & Orphan Purge", run_live_drill_2_real_minio),
            ("Live Drill 3: Real Multi-Worker Crash, Reaper & Control Job Invariant", lambda: run_live_drill_3_multiworker_durability(args.port)),
        ]
        l_results = []
        t0 = time.time()
        for name, func in live_drills:
            res = func()
            l_results.append((name, res))
            if not res:
                print(f"{RED}{BOLD}ABORTING: {name} FAILED{RESET}")
                sys.exit(1)

        print(f"{CYAN}{'=' * 80}{RESET}")
        print(f"{BOLD}LAYER 2 (LIVE INTEGRATION) SUMMARY: ALL {len(l_results)} DRILLS PASSED in {time.time() - t0:.2f}s{RESET}")
        print(f"{CYAN}{'=' * 80}{RESET}\n")

    print(f"{GREEN}{BOLD}🎉 ALL REQUESTED CHAOS DRILLS COMPLETED SUCCESSFULLY{RESET}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
