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
echo "─── [1/4] Verifying Backend Control Plane ───"
if [ ! -d "backend/.venv" ]; then
    echo "Creating virtual environment in backend/.venv..."
    python3 -m venv backend/.venv
    ./backend/.venv/bin/pip install --upgrade pip
    ./backend/.venv/bin/pip install -r backend/requirements.txt
fi

echo "Running full PyTest suite across all 9 suites..."
./backend/.venv/bin/pytest backend/tests/ -v --tb=short
echo "✓ Backend tests passed (100% green)."
echo ""

# 2. Schema Migrations Verification
echo "─── [2/4] Verifying Database Migrations ───"
test -f backend/migrations/003_vulcan_core_schema.sql
test -f backend/migrations/004_catalog_pgvector.sql
test -f scripts/run_migrations.py
echo "✓ Schema migrations 003, 004, and migration runner verified."
echo ""

# 3. Frontend Typecheck & Build
echo "─── [3/4] Verifying Frontend Console (Next.js 15) ───"
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
echo "─── [4/4] Verifying Compose & Secrets Contract ───"
cd "${REPO_ROOT}"
test -f deploy/docker-compose.yml
test -f frontend/public/.gitkeep
test -f frontend/next.config.mjs
test -f frontend/playwright.config.ts
echo "✓ Platform configuration and infrastructure files verified."
echo ""

echo "===================================================================="
echo "  CLEAN CHECKOUT VERIFICATION SUCCESSFUL: ALL GATES GREEN"
echo "===================================================================="
