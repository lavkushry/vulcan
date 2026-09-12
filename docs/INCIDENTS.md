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
| **SEC-INC-07** | 2026-09-09 | Transcript Leak | Chat prompt text (Recurrence Pattern) | Hugging Face Token (`hf_UrW...hete`) | 🟡 Pending Rotation | Out-of-band `read -s` injection protocol mandate |
| **SEC-INC-08** | 2026-09-09 | Transcript Leak | Chat prompt text (Recurrence Pattern #2) | OpenRouter API Key (`sk-or-v1-01e...91b9`) | 🟡 Pending Rotation | Out-of-band `read -s` injection protocol re-enforcement |
| **SEC-INC-09** | 2026-09-12 | Transcript Leak | CLI `curl` command with Bearer token | Production API Token (`vlc_qf7...Lojw`) | 🟢 Resolved | Pre-flight Stdin Token Rotation & Cardinal Protocol Enforcement |

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
* **Quota Telemetry:** 538.7 / 1,000 daily free-tier requests consumed during morning verification prior to fail-closed `INV-AI-01` trip and Hugging Face pivot.
* **Rotation Status:** Revoked & Rotated at aistudio.google.com (Date: 2026-09-09)
* **Remediation:**
  1. Mandated immediate revocation and deletion of the exposed key on `aistudio.google.com`.
  2. Enforced issuance of a fresh replacement key transferred strictly via the zero-exposure stdin injection protocol (`read -s -p "Key: " KEY && ...`).
  3. Verified zero persistent footprint in git-tracked code, test fixtures, or public perimeter.
* **Automated Preventive Gate:** Reaffirmed that API credentials must strictly be injected via interactive stdin into `.env` (`0600`) without CLI arguments or terminal prompt emission.

---

### SEC-INC-07: Transcript Leak (Recurrence Pattern: Prompt Text)
* **Timestamp:** 2026-09-09T06:15:00Z
* **Category:** Transcript Credential Leak (Recurrence Pattern)
* **Exposure Vector:** Chat prompt input field during target environment provisioning
* **Affected Secret(s):** Hugging Face User Access Token (`hf_UrW...hete`, account: `lavkushry`)
* **Rotation Status:** Pending Operator Rotation in huggingface.co/settings/tokens (Date: 2026-09-09)
* **Root Cause & Recurrence Pattern:**
  Immediately following the remediation of SEC-INC-06, a secondary provider token (Hugging Face) was pasted directly into the agent prompt for VM provisioning. This identified a systemic human operational anti-pattern: developers/operators instinctively paste secrets into chat interfaces when attempting to transfer keys to remote environments, rather than using out-of-band stdin streaming.
* **Impact & Exposure:**
  The Hugging Face access token was recorded in the LLM chat transcript. While not exposed in public repositories or git commits, conversational transcripts persist in agent logging systems and constitute an unauthorized plaintext boundary crossing.
* **Remediation & Action Items:**
  1. **Immediate Revocation**: Mandated immediate revocation and regeneration of the Hugging Face token on `huggingface.co/settings/tokens` (`lavkushry` account).
  2. **Audit Gemini Status**: Verified that the Gemini API key from SEC-INC-06 was revoked and rotated at `aistudio.google.com`.
  3. **Target VM Sanitization**: Verified that remote environment file `deploy/.env` retains restrictive `0600` permissions and that tokens are never echoed to bash history or stdout.
* **Mandatory Governance Protocol Rule:**
  > **CARDINAL RULE**: *A key never touches a text field anywhere, including conversations with agents. Keys must be provisioned out-of-band directly to the target environment (`read -s` into `.env`, never via chat).*

---

### SEC-INC-08: Transcript Leak (Recurrence Pattern #2: OpenRouter Key in Prompt)
* **Timestamp:** 2026-09-09T06:36:00Z
* **Category:** Transcript Credential Leak (Recurrence Pattern #2)
* **Exposure Vector:** Chat prompt input field during multi-provider feature request
* **Affected Secret(s):** OpenRouter API Key (`sk-or-v1-01e...91b9`)
* **Rotation Status:** Pending Operator Rotation in openrouter.ai/keys (Date: 2026-09-09)
* **Root Cause & Recurrence Pattern:**
  Third consecutive occurrence of the conversational credential transfer anti-pattern. While instructing the agent to add OpenRouter integration and provide documentation, the operator pasted the active OpenRouter API key directly into the chat prompt text. This underscores that developers default to prompt-based credential transit unless physical/systemic barriers prevent chat-based entry.
* **Impact & Exposure:**
  OpenRouter API key was recorded in agent conversation history and session transcripts. The key is an active API token with access to OpenRouter chat and embedding endpoints.
* **Remediation & Action Items:**
  1. **Immediate Revocation**: Mandated immediate revocation and regeneration of the OpenRouter key on `openrouter.ai/keys`.
  2. **Audit Prior Keys**: Verified rotation status for Gemini (`aistudio.google.com`) and Hugging Face (`huggingface.co/settings/tokens`).
  3. **Target Environment Provisioning**: Injected OpenRouter configuration directly into `deploy/.env` (`0600`) via secure stdin pipe without echoing to shell history or logs.
* **Mandatory Governance Protocol Rule:**
  > **CARDINAL RULE**: *A key never touches a text field anywhere, including conversations with agents. Keys must be provisioned out-of-band directly to the target environment (`read -s` into `.env`, never via chat).*

---

### SEC-INC-09: Live Production API Bearer Token Emitted in CLI Transcript
* **Timestamp:** 2026-09-12T07:30:00Z
* **Category:** Transcript Credential Leak (Live Production API Token)
* **Exposure Vector:** Direct `curl` command with `Authorization: Bearer vlc_...` emitted into command strings and session transcripts during CHAT-03 verification.
* **Affected Secret(s):** Live production API token (`vlc_qf7...Lojw`)
* **Rotation Status:** Revoked & Rotated (Zero-Exposure Stdin Protocol)
  > *Note on Register Honesty:* Initial closure claim (commit `0352556`) stated rotation had occurred; empirical probe on 2026-09-12 returned HTTP 200, disproving the claim; rotation and empirical verification followed.
* **Root Cause & Recurrence Pattern:**
  While executing live verification commands against the control plane, an operator ran `curl` commands directly embedding the live bearer token header rather than referencing an environment variable, configuration file, or out-of-band stdin injection script. This breached the Cardinal Governance Protocol.
* **Impact & Exposure:**
  The live production token was recorded in the agent session transcript. While access to the remote VM is restricted via loopback iptables and SSH tunneling, conversational transcripts persist in agent logging systems, representing an unauthorized boundary crossing.
* **Remediation & Action Items:**
  1. **Immediate Zero-Exposure Rotation**: Generated replacement cryptographically secure 32-character tokens (`secrets.token_urlsafe(32)`) and rotated `VULCAN_API_TOKENS` in `deploy/.env` (`0600`) on target environments using the zero-exposure stdin pipe protocol (never CLI arguments, flags, or chat text).
  2. **Container Restart**: Cycled `vulcan-backend` container to load new tokens, invalidating the exposed credential.
  3. **Strict Pre-Flight Gate**: Enforced standing rule that no remote commands may run while any unrotated exposed token exists.
* **Empirical Verification Receipts:**
  - **Initial Probe (Pre-Rotation):**
    ```bash
    $ ssh vulcan 'curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer vlc_qf7...Lojw" http://127.0.0.1:8000/api/v1/jobs'
    200
    ```
    *Result:* Confirmed token was live on the target host. Immediate zero-exposure rotation initiated.
  - **Rotation Execution:** Re-keyed `lead.bob` credential in `/home/ubuntu/vulcan/deploy/.env` (`0600`) via zero-exposure in-memory cryptographic generation (`secrets.token_urlsafe(32)`), backed up previous configuration to `.env.bak.<timestamp>`, and recycled container `vulcan-backend`.
  - **Post-Rotation Probe (Revocation Confirmed):**
    ```bash
    $ ssh vulcan 'curl -s -w "\nHTTP_STATUS:%{http_code}\n" -H "Authorization: Bearer vlc_qf7...Lojw" http://127.0.0.1:8000/api/v1/jobs'
    {"error_code":"ERR_VULCAN_UNAUTHENTICATED","message":"Missing or invalid API token."}
    HTTP_STATUS:401
    ```
    *Result:* Conclusive HTTP 401 Unauthorized received. Burned token is dead.
  - **Active Valid Token Probe:**
    ```bash
    $ ssh vulcan 'TOKEN=$(grep "^NEXT_PUBLIC_VULCAN_API_TOKEN=" ~/vulcan/deploy/.env | cut -d= -f2); curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/jobs'
    200
    ```
    *Result:* Legitimate authenticated traffic continues without disruption.
* **Mandatory Governance Protocol Rule:**
  > **CARDINAL RULE**: *A key never touches a text field anywhere, including conversations with agents. Keys must be provisioned out-of-band directly to the target environment (`read -s` into `.env`, never via chat).*

### SEC-INC-10: Residual Token Exposure via Query Parameters in SSE & WebSocket Transports
* **Timestamp:** 2026-09-12T14:30:00Z
* **Category:** Architectural Risk / Transport Protocol Residual
* **Description:** Implementation of `CHAT-22` (Server-Sent Events streaming transport for intent resolution) and WebSocket live execution telemetry allows token authentication via URL query parameters (`?token=...`). This accommodation exists because standard browser `EventSource` and `WebSocket` APIs do not support setting custom `Authorization: Bearer` request headers natively.
* **Impact & Exposure Risk:** Query string parameters are traditionally logged by default in web server and reverse proxy access logs (e.g., Nginx, Envoy, AWS ALB), and can appear in browser histories or TLS termination proxies if log masking is misconfigured.
* **Mitigation & Defense-in-Depth:**
  1. **Log Sanitization Mandate**: Access log formatting rules in Nginx/Envoy must explicitly mask or drop the `token` query parameter (`log_format ... "$request_uri_sanitized"`).
  2. **Loopback Perimeter Lockdown**: Pilot environment operates under loopback lockdown (`127.0.0.1:8000`), reachable exclusively via authenticated SSH port forwarding (`ssh -L`), preventing intermediate proxy exposure.
  3. **Ephemeral Ticket Exchange (Phase 7 Roadmap)**: For multi-operator browser clients post-pilot, replace query-parameter tokens with a short-lived (60s), single-use connection ticket issued via a secure POST handshake (`POST /api/v1/auth/tickets`).
  4. **Header Auth Default**: Standard REST endpoints continue to enforce strict `Authorization: Bearer <token>` header authentication.
* **Residual Status:** Formally Documented & Risk-Accepted for Pilot Scope.

---

## Ongoing Governance Protocol
1. **Zero Plaintext Secrets in Commands:** No command may pass credentials via `-e`, `--password`, or CLI positional arguments. All credentials must be injected via standard input or loaded from container environment.
2. **Pre-Commit Connection String Gate:** All PRs must pass the connection-string regex gate in `scripts/verify-clean-checkout.sh`.
3. **Formal Incident Escalation:** Any newly identified credential exposure must be logged in this register within 2 hours of discovery, with rotation executed within 1 hour.
