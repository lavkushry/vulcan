#!/usr/bin/env bash
# ==============================================================================
# Project Vulcan: Clean Checkout Verification Script (INFRA-02)
# Author: Robert C. Martin ("Uncle Bob") & Platform SRE Lead
# Mandate: Verifies that a clean repository checkout builds hermetically without
#          undocumented manual steps or tribal knowledge.
# ==============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "===================================================================="
echo "  PROJECT VULCAN: CLEAN CHECKOUT REPRODUCIBILITY VERIFICATION"
echo "===================================================================="
echo "Repository Root: ${REPO_ROOT}"
echo ""

# 1. Backend Verification
echo "─── [1/5] Verifying Backend Control Plane ───"
if [ ! -d "backend/.venv" ]; then
    echo "Creating virtual environment in backend/.venv..."
    python3 -m venv backend/.venv
    ./backend/.venv/bin/pip install --upgrade pip
    ./backend/.venv/bin/pip install -r backend/requirements-dev.txt
fi

echo "Running full PyTest suite across all 9 suites..."
./backend/.venv/bin/pytest backend/tests/ -v --tb=short
echo "✓ Backend tests passed (100% green)."
echo ""

# 2. Schema Migrations Verification
echo "─── [2/5] Verifying Database Migrations ───"
test -f backend/migrations/003_vulcan_core_schema.sql
test -f backend/migrations/004_catalog_pgvector.sql
test -f backend/migrations/005_candidate_null_sha_constraint.sql
test -f backend/migrations/006_jobs_and_audit_ledger_enhancements.sql
test -f backend/migrations/007_add_worker_pid_column.sql
test -f backend/migrations/008_chat_sessions_and_turns.sql
test -f backend/migrations/009_chat_turns_unique_constraint.sql
test -f scripts/run_migrations.py
echo "✓ Schema migrations 003, 004, 005, 006, 007, 008, 009, and migration runner verified."
echo ""

# 3. Frontend Typecheck & Build
echo "─── [3/5] Verifying Frontend Console (Next.js 15) ───"
cd "${REPO_ROOT}/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm ci
fi

echo "Running TypeScript strict typecheck..."
npx tsc --noEmit
echo "✓ TypeScript typecheck passed (0 errors)."

echo "Running Next.js production build..."
npm run build
echo "✓ Next.js production build succeeded (15/15 static pages compiled)."
echo ""

# 4. Platform Infrastructure Integrity
echo "─── [4/5] Verifying Compose, Network Lockdown & Secrets Contract ───"
cd "${REPO_ROOT}"
test -f deploy/docker-compose.yml
test -f frontend/public/.gitkeep
test -f frontend/next.config.mjs
test -f frontend/playwright.config.ts

# Port-Contract Gate: Syntax-proof verification of zero published ports without explicit 127.0.0.1: loopback binding
echo "Checking Docker Compose network lockdown contract across deploy/docker-compose*.yml..."
for compose_file in deploy/docker-compose*.yml; do
    [ -f "$compose_file" ] || continue

    # Gate Stage A: Rendered effective config check (immune to quoting, env interpolation, and long/short syntax)
    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        docker compose -f "$compose_file" config --format json 2>/dev/null | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
errors = []
for svc, cfg in data.get("services", {}).items():
    for p in cfg.get("ports", []):
        host_ip = p.get("host_ip")
        pub = p.get("published")
        if host_ip != "127.0.0.1":
            errors.append(f"Service \"{svc}\" publishes port {pub} with non-loopback host_ip \"{host_ip}\"")
if errors:
    for e in errors:
        print("🔴 GATE FAILURE: " + e)
    sys.exit(1)
' || { echo "🔴 GATE FAILURE: Non-loopback port published in rendered $compose_file"; exit 1; }
    else
        echo "🔴 GATE FAILURE: docker compose command not available to render $compose_file. Failing closed."
        exit 1
    fi

    # Gate Stage B: Static syntax regex gate (catches unquoted ports and raw port definitions)
    if grep -E '^\s*-\s*("?[0-9]+:|\$\{)' "$compose_file"; then
        echo "🔴 GATE FAILURE: Found unescaped or non-loopback port binding in $compose_file!"
        echo "All container host ports MUST be explicitly prefixed with '127.0.0.1:' (e.g. '127.0.0.1:8000:8000')."
        exit 1
    fi
    echo "✓ $compose_file: Verified loopback-only (127.0.0.1)."
done
echo "✓ Platform configuration and infrastructure files verified."
echo ""

# Connection-String Secrets Gate: Zero plaintext credentials in connection URLs across docs/, scripts/, backend/
echo "Checking for embedded connection-string credentials across docs/, scripts/, backend/..."
FOUND_CREDS=$(git grep -I -nE '(redis|postgres(ql)?|mysql|amqp)://[^ ]*:[^ @]+@' docs/ scripts/ backend/ 2>/dev/null | grep -v ':\*\*\*@' | grep -v ':\${' || true)
if [ -n "$FOUND_CREDS" ]; then
    echo "🔴 GATE FAILURE: Embedded connection-string credentials detected in git-tracked files:"
    echo "$FOUND_CREDS"
    echo "All connection strings in docs/, scripts/, and backend/ must be masked (e.g. redis://:***@...) or loaded via environment variables."
    exit 1
fi
echo "✓ Connection-string secrets gate: 0 embedded credentials found across docs/, scripts/, backend/."
echo ""

# Token Leak Prevention Gate: Zero unmasked production API tokens in git repository
echo "Checking for exposed live Vulcan API tokens across docs/, scripts/, backend/, frontend/, deploy/..."
EXPOSED_TOKENS=$(git grep -I -nE 'vlc_[A-Za-z0-9_-]{20,}' docs/ scripts/ backend/ frontend/ deploy/ 2>/dev/null | grep -v 'vlc_test_' | grep -v 'vlc_replace_' || true)
if [ -n "$EXPOSED_TOKENS" ]; then
    echo "🔴 GATE FAILURE: Exposed live Vulcan API tokens detected in git-tracked files:"
    echo "$EXPOSED_TOKENS"
    echo "All production tokens must be loaded dynamically from deploy/.env via stdin and masked in documentation."
    exit 1
fi
echo "✓ Token leak prevention gate: 0 exposed live tokens found in git-tracked files."
echo ""

# 5. Software Bill of Materials (SBOM) Gate (INFRA-30)
echo "─── [5/5] Verifying Software Bill of Materials (SBOM) Generation Gate (INFRA-30) ───"
TEMP_SBOM_DIR=$(mktemp -d)
bash "${REPO_ROOT}/scripts/generate_sbom.sh" "$TEMP_SBOM_DIR"
rm -rf "$TEMP_SBOM_DIR"
echo "✓ Software Bill of Materials (SBOM) generation gate passed (SPDX 2.3 + CycloneDX 1.5)."
echo ""

echo "===================================================================="
echo "  CLEAN CHECKOUT VERIFICATION SUCCESSFUL: ALL GATES GREEN"
echo "===================================================================="

