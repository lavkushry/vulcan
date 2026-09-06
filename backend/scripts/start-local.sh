#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "================================================================"
echo "          PROJECT VULCAN: Local Control Plane Stack"
echo "================================================================"

echo "[1/3] Checking ports 8000 & 3000..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :3000 | xargs kill -9 2>/dev/null || true

echo "[2/3] Starting FastAPI Backend on http://localhost:8000..."
cd "$ROOT_DIR/backend"
PYTHONPATH=. .venv/bin/uvicorn app.api.server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "[3/3] Starting Next.js Operator Console on http://localhost:3000..."
cd "$ROOT_DIR/frontend"
PORT=3000 HOSTNAME=0.0.0.0 npm run dev &
FRONTEND_PID=$!

echo ""
echo " Vulcan Operator Console is live:"
echo "   - Web UI:     http://localhost:3000"
echo "   - Backend:    http://localhost:8000"
echo "   - API Docs:   http://localhost:8000/docs"
echo "   - Health:     http://localhost:8000/healthz"
echo ""
echo "Press [Ctrl+C] to stop all services."

trap "echo 'Stopping Project Vulcan...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0" INT TERM

wait
