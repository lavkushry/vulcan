#!/usr/bin/env bash
# scripts/schedule_backup.sh — Operational Automated PostgreSQL Backup & MinIO Archival
# Scheduled nightly backup with SHA-256 validation, MinIO S3 upload, 7-day retention policy, and structured logging.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VULCAN_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${VULCAN_DIR}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/backup.log"

# Load environment securely if available
if [ -f "${VULCAN_DIR}/deploy/.env" ]; then
    # shellcheck disable=SC1091
    source "${VULCAN_DIR}/deploy/.env" 2>/dev/null || true
fi

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
DUMP_FILENAME="vulcan_pg_dump_${TIMESTAMP}.dump"
TEMP_DIR="/tmp/vulcan_scheduled_backup"
mkdir -p "$TEMP_DIR"
LOCAL_DUMP="${TEMP_DIR}/${DUMP_FILENAME}"
POSTGRES_CONTAINER="vulcan-postgres"
S3_BUCKET="${S3_BUCKET_NAME:-vulcan-artifacts}"
S3_PREFIX="backups/daily"
RETENTION_DAYS=7

START_TIME=$(date +%s)

log_json() {
    local status="$1"
    local msg="$2"
    local duration="$3"
    local size="$4"
    local sha="$5"
    local pruned="$6"
    printf '{"timestamp":"%s","status":"%s","message":"%s","duration_seconds":%s,"size_bytes":%s,"sha256":"%s","pruned_count":%s}\n' \
        "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$status" "$msg" "$duration" "$size" "$sha" "$pruned" | tee -a "$LOG_FILE"
}

cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# 1. Verify PostgreSQL container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    log_json "FAILED" "PostgreSQL container ${POSTGRES_CONTAINER} not running" 0 0 "" 0
    exit 1
fi

# 2. Execute pg_dump custom format
if ! docker exec "$POSTGRES_CONTAINER" pg_dump -U "${POSTGRES_USER:-vulcan_admin}" -d "${POSTGRES_DB:-vulcan_control_plane}" --format=c --compress=6 > "$LOCAL_DUMP" 2>/dev/null; then
    log_json "FAILED" "pg_dump failed" 0 0 "" 0
    exit 1
fi

DUMP_SIZE=$(stat -c%s "$LOCAL_DUMP" 2>/dev/null || stat -f%z "$LOCAL_DUMP")
DUMP_SHA256=$(sha256sum "$LOCAL_DUMP" 2>/dev/null | awk '{print $1}' || shasum -a 256 "$LOCAL_DUMP" | awk '{print $1}')

# 3. Upload to MinIO S3 & Enforce Retention via deploy-backend container (Hermetic, zero host dependencies)
ACCESS_KEY="${S3_ACCESS_KEY:-${MINIO_ROOT_USER:-vulcan_minio_admin}}"
SECRET_KEY="${S3_SECRET_KEY:-${MINIO_ROOT_PASSWORD:-}}"

PRUNED_COUNT=$(docker run --rm \
    --network deploy_default \
    -v "${TEMP_DIR}:${TEMP_DIR}" \
    -e "S3_ENDPOINT=http://minio:9000" \
    -e "AWS_ACCESS_KEY_ID=${ACCESS_KEY}" \
    -e "AWS_SECRET_ACCESS_KEY=${SECRET_KEY}" \
    deploy-backend python3 -c "
import boto3, os, sys
from datetime import datetime, timezone, timedelta

s3 = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT'], aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'], region_name='us-east-1')

# Upload daily snapshot
key = f'${S3_PREFIX}/${DUMP_FILENAME}'
s3.upload_file('${LOCAL_DUMP}', '${S3_BUCKET}', key, ExtraArgs={'Metadata': {'sha256': '${DUMP_SHA256}', 'timestamp': '${TIMESTAMP}'}})

# Enforce retention policy: delete snapshots older than ${RETENTION_DAYS} days
cutoff = datetime.now(timezone.utc) - timedelta(days=${RETENTION_DAYS})
res = s3.list_objects_v2(Bucket='${S3_BUCKET}', Prefix='${S3_PREFIX}/')
deleted = 0
for obj in res.get('Contents', []):
    if obj['LastModified'] < cutoff:
        s3.delete_object(Bucket='${S3_BUCKET}', Key=obj['Key'])
        deleted += 1
print(deleted)
")

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

log_json "SUCCESS" "Backup completed and archived to s3://${S3_BUCKET}/${S3_PREFIX}/${DUMP_FILENAME}" "$DURATION" "$DUMP_SIZE" "$DUMP_SHA256" "$PRUNED_COUNT"
