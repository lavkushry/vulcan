# Project Vulcan: Security Incident & Credential Remediation Log

**Document Purpose:** Complete forensic record of credential exposures, security regressions, root-cause analyses, immediate remediations, and permanent automated CI/CD gates added during Project Vulcan development.  
**Auditing Standard:** SOX 404, SOC 2 Type II Compliance, Zero-Trust Enterprise Automation Governance.

---

## Incident Summary Register

| Incident ID | Date | Category | Exposure Vector | Affected Secret(s) | Remediation Status | Automated Gate Added |
| :--- | :---: | :--- | :--- | :--- | :---: | :--- |
| **SEC-INC-01** | 2026-08-30 | Network / Auth | Host firewall & probe execution | CI test token (`vlc_test_alice`) | 🟢 Resolved | Port-Contract Gate (`verify-clean-checkout.sh`) |
| **SEC-INC-02** | 2026-09-02 | Repository Leak | Markdown architectural debate | Synthetic AI API tokens | 🟢 Resolved | Gitleaks SARIF scan (`deploy.yml`) |
| **SEC-INC-03** | 2026-09-06 | Infrastructure | Git-tracked `docker-compose.yml` (Defect D5) | Postgres & MinIO default passwords | 🟢 Resolved | Parameterized `.env` (`0600`) & Gitignore gate |
| **SEC-INC-04** | 2026-09-08 | Transcript Leak | Docker exec `-e` command flags | PostgreSQL 16, Redis 7.2, MinIO S3 credentials | 🟢 Resolved | Stdin-Only Secret Injection Protocol |
| **SEC-INC-05** | 2026-09-08 | Codebase / Docs | Fallback strings in adapters & benchmark docs | PostgreSQL connection strings & Redis password | 🟢 Resolved | Connection-String Regex Gate (`verify-clean-checkout.sh`) |
| **SEC-INC-06** | 2026-09-09 | Transcript Leak | Chat prompt text | Gemini API Key (`AQ.Ab8...1hvA`) | 🟢 Resolved | Immediate AI Studio rotation & Stdin-Transfer protocol |

---

## Detailed Forensic Records

### SEC-INC-01: Public Port Exposure & CI Token Network Probe
* **Timestamp:** 2026-08-30T17:45:00Z
* **Description:** Following an update to `deploy/docker-compose.yml`, ports 8000 (FastAPI) and 3000 (Next.js) were published without explicit `127.0.0.1:` loopback bindings (`"8000:8000"`, `"3000:3000"`), binding them to `0.0.0.0` on the remote VM. During network verification, an external probe was executed against the public IP using the CI test token (`vlc_test_alice`).
* **Impact & Exposure:** Public IP answered on 8000 and 3000. The production API rejected the test token with `401 Unauthorized` (confirming production auth enforcement), but the API was externally accessible.
* **Remediation:**
  1. Bound all Docker Compose published ports strictly to `127.0.0.1:8000:8000` and `127.0.0.1:3000:3000`.
  2. Applied defense-in-depth iptables drop rules on `DOCKER-USER` chain for external interface `eth0` across ports 3000, 8000, 9000, persisted to `/etc/iptables/rules.v4`.
* **Automated Preventive Gate:** Added two-stage Port-Contract Gate to `scripts/verify-clean-checkout.sh` (Stage A: rendered effective `docker compose config --format json` inspection; Stage B: static regex check). Verified 0 open ports outside SSH (22).

---

### SEC-INC-02: Synthetic API Tokens Drafted in Documentation
* **Timestamp:** 2026-09-02T11:20:00Z
* **Description:** During architecture debate sessions exploring the AI chat subsystem, mock/synthetic API key strings for LLM providers were drafted into documentation files.
* **Impact & Exposure:** Synthetic tokens entered git history in feature branches.
* **Remediation:**
  1. Scrubbed all synthetic keys and replaced them with standard environment variable placeholders (`${OPENAI_API_KEY}`).
  2. Implemented `DeterministicFakeChatProvider` in Python for all CI test suites to ensure zero external network calls or tokens are required.
* **Automated Preventive Gate:** Integrated `gitleaks/gitleaks-action@v2` into `.github/workflows/deploy.yml` producing SARIF report artifacts on every pull request and push to `main`.

---

### SEC-INC-03: Default Passwords in Git-Tracked Docker Compose (Defect D5)
* **Timestamp:** 2026-09-06T08:15:00Z
* **Description:** Forensic audit during the Platform Architecture Debate surfaced Defect D5: `deploy/docker-compose.yml` contained hardcoded passwords in plaintext (`POSTGRES_PASSWORD: vulcan_secure_password_2026`, `MINIO_ROOT_PASSWORD: vulcan_minio_secret_2026`).
* **Impact & Exposure:** Anyone cloning the repository could deploy with identical, well-known credentials.
* **Remediation:**
  1. Refactored `deploy/docker-compose.yml` to strictly interpolate from environment variables (`${POSTGRES_PASSWORD}`, `${MINIO_ROOT_PASSWORD}`, `${REDIS_PASSWORD}`).
  2. Created template `deploy/.env.example` with empty secrets.
  3. Placed live secrets strictly into `deploy/.env` with atomic `chmod 0600` permissions on the VM, permanently gitignored.
* **Automated Preventive Gate:** Clean-checkout gate enforces that `deploy/.env` is never checked into git and that all compose variables require external interpolation.

---

### SEC-INC-04: Infrastructure Secrets Burned via CLI `-e` Flags in Session Transcripts
* **Timestamp:** 2026-09-08T15:30:00Z
* **Description:** During the execution of Milestone C.3 live chaos drills on the remote VM, commands were invoked passing live credentials via `-e` flags (`-e REDIS_URL='redis://:xSvmNW88...'`, `-e S3_SECRET_KEY=...`, `-e DATABASE_URL='postgresql://vulcan_admin:1uxFd4lX...'`). This emitted plaintext credentials six times into command strings and session transcripts.
* **Impact & Exposure:** Critical infrastructure credentials for PostgreSQL 16, Redis 7.2, and MinIO S3 were permanently recorded in session transcripts.
* **Remediation:**
  1. Generated three cryptographically secure, 32-character high-entropy tokens locally (`secrets.token_urlsafe(24)`).
  2. Executed zero-exposure rotation on live VM `141.148.195.233` via SSH stdin pipe (zero CLI arguments or flags).
  3. Rotated `ALTER USER vulcan_admin WITH PASSWORD` in PostgreSQL, updated `deploy/.env` atomically, and force-recreated containers.
  4. Verified live connectivity from `vulcan-backend` across PostgreSQL (2,022 jobs intact), Redis (`r.ping()`), and MinIO (`s3.list_buckets()`).
  5. Unlinked all temporary runner scripts immediately.
* **Automated Preventive Gate:** Mandated the Stdin-Only Secret Injection Protocol for all administrative scripts; updated `scripts/run_chaos_drills.py` to mask connection strings before printing (`re.sub(r'://([^:]*):[^@]+@', r'://\1:***@', redis_url)`).

---

### SEC-INC-05: Hardcoded Connection Strings in Code Fallbacks & Benchmark Reports
* **Timestamp:** 2026-09-08T16:00:00Z
* **Description:** Static code audit following SEC-INC-04 revealed that 10 codebase files (`backend/app/adapters/postgres_*.py`, `backend/scripts/run_migrations.py`, `backend/tests/test_postgres_*.py`, etc.) contained hardcoded fallback connection strings (`"postgresql://vulcan_admin:***@localhost:5432/..."`). Furthermore, `docs/LOAD_AND_CHAOS_BENCHMARK_REPORT.md` and `docs/PLATFORM_INFRASTRUCTURE_CI_OBSERVABILITY_DEBATE.md` contained unredacted Redis and PostgreSQL connection strings.
* **Impact & Exposure:** Stale development credentials remained scattered across production adapters and documentation.
* **Remediation:**
  1. Removed all hardcoded fallback connection strings across all 10 files, replacing them with dynamic environment variable assembly (`f"postgresql://{user}@{host}:5432/{db}"`).
  2. Redacted all connection strings in markdown documentation to masked formats (`redis://:***@redis:6379/0`, `postgresql://vulcan_admin:***@postgres:5432/...`).
* **Automated Preventive Gate:** Added Connection-String Secrets Gate to `scripts/verify-clean-checkout.sh`:
  ```bash
  FOUND_CREDS=$(git grep -I -nE '(redis|postgres(ql)?|mysql|amqp)://[^ ]*:[^ @]+@' docs/ scripts/ backend/ 2>/dev/null | grep -v ':\*\*\*@' | grep -v ':\${' || true)
  ```
  Integrated into CI Stage 3 (Hermetic Clean Checkout Gate), guaranteeing that any future unmasked connection string immediately fails the build.

### SEC-INC-06: Gemini API Token Emitted in Chat Transcript Prompt
* **Timestamp:** 2026-09-09T04:55:00Z
* **Description:** During the transition to the live model decision protocol, an unredacted Google AI Studio Gemini API key (`AQ.Ab8...1hvA`) was pasted into the conversational transcript prompt.
* **Impact & Exposure:** Free-tier Gemini API key was recorded in conversation history. Key was not exposed to public repositories, logs, or deployed to production containers.
* **Remediation:**
  1. Mandated immediate revocation and deletion of the exposed key on `aistudio.google.com`.
  2. Enforced issuance of a fresh replacement key transferred strictly via the zero-exposure stdin injection protocol (`read -s -p "Key: " KEY && ...`).
  3. Verified zero persistent footprint in git-tracked code, test fixtures, or public perimeter.
* **Automated Preventive Gate:** Reaffirmed that API credentials must strictly be injected via interactive stdin into `.env` (`0600`) without CLI arguments or terminal prompt emission.

---

## Ongoing Governance Protocol
1. **Zero Plaintext Secrets in Commands:** No command may pass credentials via `-e`, `--password`, or CLI positional arguments. All credentials must be injected via standard input or loaded from container environment.
2. **Pre-Commit Connection String Gate:** All PRs must pass the connection-string regex gate in `scripts/verify-clean-checkout.sh`.
3. **Formal Incident Escalation:** Any newly identified credential exposure must be logged in this register within 2 hours of discovery, with rotation executed within 1 hour.
