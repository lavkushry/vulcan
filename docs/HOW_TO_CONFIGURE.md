# Project Vulcan: Complete Configuration Guide (How to Configure)

This guide provides the authoritative operational reference for configuring, hardening, and deploying the **Project Vulcan Enterprise Automation Control Plane** across local workstations, staging environments, and production cloud infrastructure.

---

## Table of Contents
1. [Environment Architecture & 12-Factor Contract](#1-environment-architecture--12-factor-contract)
2. [Complete Environment Variable Reference](#2-complete-environment-variable-reference)
   - [2.1 Backend Control Plane & Infrastructure](#21-backend-control-plane--infrastructure)
   - [2.2 AI Reasoning & LLM Provider Configuration](#22-ai-reasoning--llm-provider-configuration)
   - [2.3 Frontend Web Console Configuration](#23-frontend-web-console-configuration)
3. [AI Model & Embedding Provider Setup](#3-ai-model--embedding-provider-setup)
   - [3.1 Google Gemini (Recommended for Production)](#31-google-gemini-recommended-for-production)
   - [3.2 Hugging Face Inference API](#32-hugging-face-inference-api)
   - [3.3 OpenRouter & OpenAI Providers](#33-openrouter--openai-providers)
   - [3.4 Deterministic Fake Provider (Zero-Network Hermetic Mode)](#34-deterministic-fake-provider-zero-network-hermetic-mode)
4. [Storage, Database & Cache Configuration](#4-storage-database--cache-configuration)
   - [4.1 PostgreSQL 16 & pgvector HNSW Setup](#41-postgresql-16--pgvector-hnsw-setup)
   - [4.2 Redis 7.2 Redlock & Watchdog Heartbeat](#42-redis-72-redlock--watchdog-heartbeat)
   - [4.3 MinIO S3 Object Storage & Multipart Decoupling](#43-minio-s3-object-storage--multipart-decoupling)
5. [Network Ingress, Ports & Firewall Topology](#5-network-ingress-ports--firewall-topology)
   - [5.1 Multi-Interface Ingress (`0.0.0.0`) vs Loopback (`127.0.0.1`)](#51-multi-interface-ingress-0000-vs-loopback-127001)
   - [5.2 Port Allocation Matrix](#52-port-allocation-matrix)
   - [5.3 Host iptables & Cloud Security List Rules](#53-host-iptables--cloud-security-list-rules)
6. [Authentication, RBAC & Secret Hygiene](#6-authentication-rbac--secret-hygiene)
   - [6.1 Token Map Syntax & Role Definition](#61-token-map-syntax--role-definition)
   - [6.2 Generating High-Entropy Tokens](#62-generating-high-entropy-tokens)
   - [6.3 Stdin-Only Secret Injection Protocol](#63-stdin-only-secret-injection-protocol)
7. [Step-by-Step Production Deployment Guide](#7-step-by-step-production-deployment-guide)
   - [7.1 Prerequisites & Host Provisioning](#71-prerequisites--host-provisioning)
   - [7.2 Initial Bootstrap & Container Launch](#72-initial-bootstrap--container-launch)
   - [7.3 Database Migrations & Validation](#73-database-migrations--validation)
   - [7.4 Zero-Downtime Updates](#74-zero-downtime-updates)

---

## 1. Environment Architecture & 12-Factor Contract

Project Vulcan enforces strict **12-Factor App principles** (INFRA-08). Secrets and configuration parameters are never committed to version control; they are injected exclusively via environment variables or loaded from a permissions-restricted file:

```
deploy/
├── docker-compose.yml       # Composable container topologies with dynamic interpolation
├── .env.example             # Clean template documenting all required variables (safe for git)
└── .env                     # Production environment file (chmod 0600, strictly gitignored)
```

> [!IMPORTANT]
> The production `deploy/.env` file on host servers must have permissions set to `chmod 0600` (`-rw-------`) owned by the deploying service user to prevent cross-process credential leakage.

---

## 2. Complete Environment Variable Reference

### 2.1 Backend Control Plane & Infrastructure

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | *Required* | PostgreSQL 16 connection string (e.g. `postgresql://user:***@postgres:5432/vulcan_control_plane`). |
| `POSTGRES_DB` | `vulcan_control_plane` | Database name initialized inside PostgreSQL container. |
| `POSTGRES_USER` | `vulcan_admin` | Database administrative username. |
| `POSTGRES_PASSWORD` | *Required in Prod* | Database password. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 7.2 connection URL. For password-protected instances: `redis://:***@redis:6379/0`. |
| `REDIS_PASSWORD` | `""` | Redis authentication password. |
| `S3_ENDPOINT_URL` | `http://minio:9000` | Internal S3 endpoint reachable by the backend container. |
| `S3_PUBLIC_ENDPOINT_URL` | `http://<HOST>:9000` | Publicly reachable S3 URL used when rewriting presigned upload/download URLs for browser clients. |
| `S3_ACCESS_KEY` | `vulcan_minio_admin` | MinIO / S3 Access Key. |
| `S3_SECRET_KEY` | *Required in Prod* | MinIO / S3 Secret Key. |
| `S3_BUCKET_NAME` | `vulcan-artifacts` | S3 bucket for storing 10GB binary artifacts and execution logs. |
| `VULCAN_CATALOG_BACKEND` | `postgres` | Catalog storage mode: `postgres` (pgvector HNSW) or `sqlite` / `memory`. |
| `VULCAN_PERSISTENCE_BACKEND` | `postgres` | Job and audit persistence: `postgres` or `memory`. |
| `SIMULATION_MODE` | `false` | When `true`, executes simulation runs instead of dispatching actual Ansible/Terraform pods. |
| `UVICORN_WORKERS` | `2` | Number of Uvicorn worker processes in backend container. |
| `VULCAN_AUTH_DISABLED` | `0` | Set to `1` only during offline local UI mock tests to bypass token verification. Must be `0` in production. |
| `VULCAN_API_TOKENS` | *Required* | JSON dictionary defining valid bearer tokens, usernames, and RBAC roles. |

---

### 2.2 AI Reasoning & LLM Provider Configuration

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `VULCAN_CHAT_PROVIDER` | `gemini` | Chat intent resolution provider: `gemini`, `huggingface`, `openrouter`, `openai`, or `fake`. |
| `VULCAN_EMBEDDING_PROVIDER`| `huggingface` | Vector embedding provider: `huggingface`, `gemini`, `openai`, `openrouter`, or `fake`. |
| `GEMINI_API_KEY` | `""` | Google Gemini API key (used if provider is `gemini`). |
| `GEMINI_CHAT_MODEL` | `gemini-2.5-flash` | Gemini model name for intent resolution and slot filling. |
| `GEMINI_EMBEDDING_MODEL` | `text-embedding-004` | Gemini model name for 768-dim vector embeddings. |
| `HUGGINGFACE_API_KEY` | `""` | Hugging Face user access token. |
| `HUGGINGFACE_EMBEDDING_MODEL`| `BAAI/bge-large-en-v1.5`| Hugging Face embedding model (1024 dimensions). |
| `OPENAI_API_KEY` | `""` | OpenAI API key. |
| `OPENAI_CHAT_MODEL` | `gpt-4o` | OpenAI model for intent resolution. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small`| OpenAI embedding model (1536 dimensions). |
| `OPENROUTER_API_KEY` | `""` | OpenRouter unified API key. |
| `OPENROUTER_CHAT_MODEL` | `liquid/lfm-2.5-2.6b:free` | Model routed via OpenRouter. |
| `OPENROUTER_EMBEDDING_MODEL`| `openai/text-embedding-3-small`| Embedding model routed via OpenRouter. |

---

### 2.3 Frontend Web Console Configuration

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL for FastAPI REST endpoints. Dynamically matched in browser if omitted. |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | Base URL for WebSocket connections. Dynamically matched in browser if omitted. |
| `NEXT_PUBLIC_VULCAN_API_TOKEN`| `""` | Optional default API token injected into console for operator convenience. |
| `PORT` | `3000` | Port on which the Next.js production server listens. |
| `HOSTNAME` | `0.0.0.0` | Host interface binding for the Next.js process. |

---

## 3. AI Model & Embedding Provider Setup

Project Vulcan decouples intent understanding and vector retrieval through the `IChatModelProvider` and `IEmbeddingProvider` interfaces.

### 3.1 Google Gemini (Recommended for Production)
Provides high-speed, sub-1.5s intent resolution with high slot-filling precision:

```bash
# In deploy/.env
VULCAN_CHAT_PROVIDER=gemini
VULCAN_EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY="AIzaSy..."
GEMINI_CHAT_MODEL="gemini-2.5-flash"
GEMINI_EMBEDDING_MODEL="text-embedding-004"
```

### 3.2 Hugging Face Inference API
Ideal for high-accuracy embedding models like BGE:

```bash
# In deploy/.env
VULCAN_CHAT_PROVIDER=gemini
VULCAN_EMBEDDING_PROVIDER=huggingface
HUGGINGFACE_API_KEY="hf_..."
HUGGINGFACE_EMBEDDING_MODEL="BAAI/bge-large-en-v1.5"
```

### 3.3 OpenRouter & OpenAI Providers
For multi-model fallback or OpenAI native models:

```bash
# In deploy/.env
VULCAN_CHAT_PROVIDER=openrouter
VULCAN_EMBEDDING_PROVIDER=openrouter
OPENROUTER_API_KEY="sk-or-v1-..."
OPENROUTER_CHAT_MODEL="liquid/lfm-2.5-2.6b:free"
OPENROUTER_EMBEDDING_MODEL="openai/text-embedding-3-small"
```

### 3.4 Deterministic Fake Provider (Zero-Network Hermetic Mode)
Used in automated CI pipelines (`deploy.yml`) and isolated offline environments. Eliminates all external API calls while executing deterministic keyword parsing, slot-filling, and 100% prompt injection refusal:

```bash
# In deploy/.env
VULCAN_CHAT_PROVIDER=fake
VULCAN_EMBEDDING_PROVIDER=fake
```

---

## 4. Storage, Database & Cache Configuration

### 4.1 PostgreSQL 16 & pgvector HNSW Setup
PostgreSQL 16 serves as the persistent catalog, execution ledger, and cryptographic Merkle audit store. The `pgvector` extension accelerates hybrid vector search.

* **Schema Migrations:** Managed via `scripts/run_migrations.py` in atomic sequence (`001` through `010`).
* **HNSW Index Configuration:**
  ```sql
  CREATE INDEX IF NOT EXISTS idx_catalog_embedding_hnsw 
  ON catalog_items 
  USING hnsw (embedding vector_cosine_ops) 
  WITH (m = 16, ef_construction = 64);
  ```
* **Applying Migrations in Production:**
  ```bash
  docker exec vulcan-backend python3 scripts/run_migrations.py
  ```

---

### 4.2 Redis 7.2 Redlock & Watchdog Heartbeat
Redis provides distributed target mutual exclusion (`Redlock`) to prevent concurrent executions from colliding on the same server, switch, or database.

* **Distributed Lock Acquisition:** Uses unique random tokens (`uuid.uuid4().hex`) and millisecond TTLs (default: 30,000ms).
* **Watchdog Thread:** Automatically renews the lease every 10 seconds while the runner process is active.
* **Safe Release:** Uses an atomic Lua script that releases the lock only if the stored token matches the runner's fencing token.
* **Pub/Sub Backplane:** Channels `job_events:{job_id}` stream stdout lines to WebSocket hubs.

---

### 4.3 MinIO S3 Object Storage & Multipart Decoupling
To support 10GB Terraform state files and disk images without saturating API memory:

* **Decoupled Architecture:** Client requests presigned part URLs from FastAPI, uploads binary chunks directly to MinIO, and notifies FastAPI on completion.
* **Ephemeral Bucket Provisioner (`vulcan-minio-init`):** Bootstraps the `vulcan-artifacts` bucket and configures download permissions upon container startup.
* **Cleanup Lifecycle:** Uncompleted multipart uploads older than 24 hours are automatically aborted.

---

## 5. Network Ingress, Ports & Firewall Topology

### 5.1 Multi-Interface Ingress (`0.0.0.0`) vs Loopback (`127.0.0.1`)
In `deploy/docker-compose.yml`, published ports are bound to `0.0.0.0` to permit multi-interface ingress (browser access from external IPs):

```yaml
services:
  frontend:
    ports:
      - "0.0.0.0:3000:3000"
  backend:
    ports:
      - "0.0.0.0:8000:8000"
  minio:
    ports:
      - "0.0.0.0:9000:9000"
      - "0.0.0.0:9001:9001"
```

> [!NOTE]
> To restrict access strictly to SSH loopback tunnels (`ssh -L 3000:localhost:3000`), replace `0.0.0.0:` with `127.0.0.1:` in `docker-compose.yml`.

---

### 5.2 Port Allocation Matrix

| Service | Container Port | Host Port | Ingress Interface | Protocol | Purpose |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Next.js Frontend** | `3000` | `3000` | `0.0.0.0` | HTTP | Web Console & UI Views |
| **FastAPI Backend** | `8000` | `8000` | `0.0.0.0` | HTTP / WS | REST Control Plane & WebSocket Stream |
| **MinIO S3 Data** | `9000` | `9000` | `0.0.0.0` | HTTP | Presigned Binary Chunk Uploads |
| **MinIO Console** | `9001` | `9001` | `0.0.0.0` | HTTP | MinIO Management Web Interface |
| **PostgreSQL 16** | `5432` | *Internal* | Bridge Network | TCP | pgvector & Merkle Audit Storage |
| **Redis 7.2** | `6379` | *Internal* | Bridge Network | TCP | Redlock Mutex & Pub/Sub Backplane |
| **Sandbox Runner** | `22` | *Internal* | Bridge Network | SSH | Ansible / Terraform Isolated Target |

---

### 5.3 Host iptables & Cloud Security List Rules
On cloud hosts (Oracle Cloud Infrastructure, AWS, GCP):
1. **Cloud Security List / Ingress Security Group:**
   * Allow TCP Port `22` (SSH management)
   * Allow TCP Port `3000` (Web Console)
   * Allow TCP Port `8000` (API Gateway)
2. **Host Firewall (`iptables`):**
   * Keep internal ports (`5432`, `6379`) shielded inside the Docker bridge network (`172.18.0.0/16`).
   * Never publish database or cache ports to `0.0.0.0`.

---

## 6. Authentication, RBAC & Secret Hygiene

### 6.1 Token Map Syntax & Role Definition
`VULCAN_API_TOKENS` is defined as a JSON dictionary string mapping cryptographic tokens to user metadata:

```json
{
  "vlc_adm_8f921a4bc89e": {
    "user_id": "alice.admin",
    "name": "Alice Administrator",
    "role": "ADMIN"
  },
  "vlc_app_3c4d5e6f7a8b": {
    "user_id": "bob.lead",
    "name": "Bob Approving Lead",
    "role": "APPROVER"
  },
  "vlc_opr_1a2b3c4d5e6f": {
    "user_id": "charlie.operator",
    "name": "Charlie SRE Operator",
    "role": "OPERATOR"
  }
}
```

#### RBAC Capabilities:
* **`OPERATOR`:** Can resolve intents, draft jobs, inspect catalogs, and run execution simulations. Cannot approve jobs.
* **`APPROVER`:** Can approve or reject jobs submitted by others. Enforces Maker-Checker ($requester \ne approver$).
* **`ADMIN`:** Full platform control including catalog curation, workflow definition, policy overrides, and RLHF dataset export.

---

### 6.2 Generating High-Entropy Tokens
To generate secure 32-character tokens:

```bash
python3 -c "import secrets; print('vlc_' + secrets.token_urlsafe(24))"
```

---

### 6.3 Stdin-Only Secret Injection Protocol
To prevent credentials from appearing in bash history (`.bash_history`), process listings (`ps aux`), or agent session transcripts:

```bash
# Correct: Inject via stdin pipe directly to .env
python3 -c "import secrets; print(f'REDIS_PASSWORD={secrets.token_urlsafe(24)}')" >> deploy/.env

# Strictly Prohibited:
# docker run -e SECRET=foo ... (appears in docker inspect)
# python script.py --token=foo (appears in ps aux)
```

---

## 7. Step-by-Step Production Deployment Guide

### 7.1 Prerequisites & Host Provisioning
* **OS:** Ubuntu 22.04 LTS / Debian 12 / Oracle Linux 9
* **Specs:** Minimum 2 vCPU, 4GB RAM, 20GB SSD (Recommended: 4 vCPU, 8GB RAM for large vector catalogs)
* **Software:** Docker Engine 24+ and Docker Compose v2.20+

### 7.2 Initial Bootstrap & Container Launch

```bash
# 1. Clone the repository
git clone https://github.com/lavkushry/vulcan.git
cd vulcan

# 2. Prepare environment configuration
cp deploy/.env.example deploy/.env
chmod 0600 deploy/.env

# 3. Populate production passwords and API tokens in deploy/.env
# (Edit deploy/.env with your preferred editor)

# 4. Build and start the container fleet
cd deploy
docker compose up -d --build
```

### 7.3 Database Migrations & Validation

```bash
# Apply all PostgreSQL migrations atomically
docker exec vulcan-backend python3 scripts/run_migrations.py

# Verify system health
curl -s http://127.0.0.1:8000/healthz
curl -s -I http://127.0.0.1:3000/chat
```

### 7.4 Zero-Downtime Updates

```bash
# Pull new releases from GitHub
git pull origin main

# Rebuild and recreate updated containers gracefully
docker compose build backend frontend
docker compose up -d --no-deps backend frontend

# Clean up dangling builder caches
docker image prune -f
```
