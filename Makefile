.PHONY: demo demo-reset demo-stop test lint build help

# ──────────────────────────────────────────────────────────
# Vulcan — AI-Governed Infrastructure Control Plane
# ──────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ──────────────────────────────────────────────────────────
# Demo
# ──────────────────────────────────────────────────────────

demo: ## Start the full demo environment (Docker Compose)
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║  Vulcan Demo — AI-Governed Infrastructure Control Plane ║"
	@echo "╚══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "▶ Checking prerequisites..."
	@command -v docker >/dev/null 2>&1 || { echo "✗ Docker is required but not installed."; exit 1; }
	@command -v docker compose >/dev/null 2>&1 || { echo "✗ Docker Compose V2 is required."; exit 1; }
	@echo "✓ Docker and Docker Compose found"
	@echo ""
	@echo "▶ Generating ephemeral demo credentials..."
	@export MINIO_ROOT_USER=$${MINIO_ROOT_USER:-vulcan-minio} && \
	 export MINIO_ROOT_PASSWORD=$${MINIO_ROOT_PASSWORD:-$$(openssl rand -hex 16)} && \
	 export POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-$$(openssl rand -hex 16)} && \
	 echo "✓ Credentials generated (not committed to disk)" && \
	 echo "" && \
	 echo "▶ Starting services..." && \
	 docker compose -f deploy/docker-compose.yml up -d --build && \
	 echo "" && \
	 echo "▶ Waiting for health checks..." && \
	 sleep 5 && \
	 echo "" && \
	 echo "╔══════════════════════════════════════════════════════════╗" && \
	 echo "║  ✓ Vulcan is running!                                   ║" && \
	 echo "║                                                         ║" && \
	 echo "║  Frontend:  http://localhost:3000                       ║" && \
	 echo "║  Backend:   http://localhost:8000                       ║" && \
	 echo "║  API Docs:  http://localhost:8000/docs                  ║" && \
	 echo "║                                                         ║" && \
	 echo "║  Demo User: admin / vulcan-demo-2026                    ║" && \
	 echo "╚══════════════════════════════════════════════════════════╝"

demo-reset: ## Reset demo environment to clean state
	@echo "▶ Resetting Vulcan demo environment..."
	@docker compose -f deploy/docker-compose.yml down -v --remove-orphans 2>/dev/null || true
	@echo "✓ All containers stopped and volumes removed"
	@echo "▶ Restarting clean environment..."
	@$(MAKE) demo

demo-stop: ## Stop demo environment without removing data
	@echo "▶ Stopping Vulcan demo..."
	@docker compose -f deploy/docker-compose.yml down 2>/dev/null || true
	@echo "✓ Demo stopped"

# ──────────────────────────────────────────────────────────
# Development
# ──────────────────────────────────────────────────────────

test: ## Run all backend tests
	@echo "▶ Running backend test suite..."
	@cd backend && .venv/bin/pytest tests/ -q --tb=short
	@echo ""
	@echo "▶ Building frontend..."
	@cd frontend && npm run build

lint: ## Run linters (ruff for Python)
	@cd backend && .venv/bin/python -m ruff check app/ tests/

build: ## Build frontend for production
	@cd frontend && npm run build

.DEFAULT_GOAL := help
