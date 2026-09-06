# VULCAN — STEP 1 SECURITY HARDENING RUNBOOK

**Scope:** close the four exposures confirmed on 2026-09-06 — public unauthenticated control plane, hardcoded/burned credentials, identity-less execute endpoint, ungated push-to-prod deploy.
**Out of scope (documented residuals, closed later):** TLS/domain termination, OIDC/SAML identity, multi-factor, K8s migration.
**Execution rule:** complete each phase's verification before starting the next. If any verify fails, stop and fix — do not proceed on assumption.

---

## Phase 0 — Break-glass preparation (5 min, do not skip)

| # | Action | Verify |
|---|---|---|
| 0.1 | Confirm you can log into the **OCI Console** (this is your only recovery path if SSH breaks — never test firewall changes without it) | Console login works |
| 0.2 | Snapshot current state on the VM: `sudo iptables-save > ~/iptables-backup.txt`, `cp deploy/docker-compose.yml ~/compose-backup.yml`, `docker compose -f deploy/docker-compose.yml config > ~/compose-config-backup.txt` | Files exist |
| 0.3 | Keep one SSH session open for the entire runbook | — |

---

## Phase 1 — Exposure audit (verify, don't assume — 15 min)

**Context:** the prior "closed 9000/9001/2222" claim only deleted INPUT rules. Docker-published ports bypass INPUT. Audit what is *actually* reachable.

| # | Command (on VM unless noted) | Looking for |
|---|---|---|
| 1.1 | `sudo ss -tlnp \| grep -E ':(22\|3000\|8000\|9000\|9001\|2222\|5432\|6379)'` | Every host-bound port and its owning process |
| 1.2 | `docker compose -f deploy/docker-compose.yml config \| grep -B2 -A4 'ports:'` | **Every published port.** 5432/6379/9000/9001/2222 must have NO `ports:` entry — backend reaches them over the compose network by service name |
| 1.3 | `sudo iptables -L DOCKER -n --line-numbers && sudo iptables -t nat -nL PREROUTING \| grep -E '9000\|2222\|5432\|6379'` | Residual Docker DNAT rules for internal services |
| 1.4 | **From your laptop** (bypass any proxy: `curl --noproxy '*'`, and use `nc -vz -w3 141.148.195.233 <port>` for each): 22, 3000, 8000, 9000, 9001, 2222, 5432, 6379 | Ground truth on external reachability. Record results — this table is the baseline every later phase is measured against |
| 1.5 | OCI Console → Networking → your VCN → Security Lists (and NSGs) | Ingress rules above iptables. Expect: 22 open. Any `0.0.0.0/0` on 3000/8000 → decision 2.0. Any rule for 9000/9001/2222/5432/6379 → delete |

**Exit criterion:** a written table of `port → externally reachable? → owning service`. Anything reachable that shouldn't be gets fixed in Phase 2.

---

## Phase 2 — Network lockdown (30–45 min)

**Decision 2.0 — how do humans reach :8000/:3000?**

| | Option A — tunnel (recommended for pilot) | Option B — public + auth |
|---|---|---|
| Compose binding | `127.0.0.1:8000:8000`, `127.0.0.1:3000:3000` | keep `8000:8000`, `3000:3000` |
| Access | `ssh -L 8000:localhost:8000 -L 3000:localhost:3000 ubuntu@141.148.195.233` (or Tailscale) | direct URL |
| Requires | Phase 4 still (API key) for defense-in-depth | Phase 4 **mandatory** + DOCKER-USER allowlist to your IP + written risk acceptance for plaintext HTTP bearer tokens |
| Health checks in CI | must run **on the VM** via SSH | can stay public (healthz stays exempt) |

| # | Action | Verify |
|---|---|---|
| 2.1 | Edit `deploy/docker-compose.yml`: **remove every `ports:` entry for postgres, redis, minio, sandbox.** Apply per Decision 2.0 for backend/frontend. `docker compose up -d` | Phase 1.4 probes re-run: 9000/9001/2222/5432/6379 → unreachable externally |
| 2.2 | Belt-and-suspenders (survives future compose drift): `sudo iptables -I DOCKER-USER -i eth0 -p tcp -m multiport --dports 5432,6379,9000,9001,2222 -j DROP` | `sudo iptables -L DOCKER-USER -n` shows the DROP |
| 2.3 | Persist rules: `sudo apt-get install -y iptables-persistent && sudo netfilter-persistent save` | `sudo iptables -L DOCKER -n` / reboot test optional |
| 2.4 | OCI Security List: ingress = **22 from your IP/32 only** (+ anything Option B requires). Delete every other 0.0.0.0/0 ingress | Phase 1.4 probes from laptop; also from a phone-hotspot/other network if practical |
| 2.5 | Update `scripts/deploy-server.sh` health checks to run locally on the VM (`curl -s localhost:8000/healthz` / `curl -s localhost:3000/curation`) — not against the public IP | Push a trivial commit; pipeline deploys green |
| 2.6 | Re-run the full external probe set from Phase 1.4 | **Exit criterion:** only 22 (+ Option B ports) reachable; everything else closed/filtered |

**Rollback:** `~/iptables-backup.txt` restore, `~/compose-backup.yml` restore, OCI console edit.

---

## Phase 3 — Secrets extraction & rotation (45–60 min)

**Context:** MinIO credentials appeared in a command transcript and possibly git history — they are burned. Rotation is mandatory, not optional.

| # | Action | Verify |
|---|---|---|
| 3.1 | Create `deploy/.env` (`chmod 600`, **gitignored**): all real values. Commit `deploy/.env.example` with placeholders only | `git status` clean; `cat .env.example` has zero real values |
| 3.2 | Compose → `${VAR}` substitution everywhere (`MINIO_ROOT_USER/PASSWORD`, `POSTGRES_PASSWORD`, `VULCAN_API_TOKENS`, etc.); backend `config.py` reads via `os.environ` — no literals | `grep -riE '(password\|secret\|token)[":= ]+[A-Za-z0-9_]{8,}' deploy/docker-compose.yml` → only `${...}` references |
| 3.3 | **Rotate MinIO:** generate new `MINIO_ROOT_USER/MINIO_ROOT_PASSWORD` (`openssl rand -hex 16`), update `.env`, `docker compose up -d minio`, update backend env. Fallback: if MinIO rejects new root creds on the existing volume, wipe the `vulcan-minio` volume (pilot data is disposable) or use `mc admin user` | Re-run the internal multipart smoke test from the walkthrough — passes with new creds |
| 3.4 | **Rotate Postgres:** `docker exec vulcan-postgres psql -U <super> -c "ALTER USER vulcan WITH PASSWORD '<new>';"`, update `.env`, restart backend | `healthz` OK + one job read |
| 3.5 | **Redis:** add `requirepass` (env + redis config) even though it's internal now — cheap | Backend reconnects |
| 3.6 | **Rotate the sandbox SSH keypair:** new `ssh-keygen -t ed25519`, replace the authorized key on `vulcan-sandbox` (bake into image or mount), update `ansible/inventory/keys`, restart | The `os-sandbox-ping` API flow still returns `SUCCESS` |
| 3.7 | **Git history audit:** `git log -p -- deploy/docker-compose.yml \| grep -iE 'secret\|password'`. Old secrets in history are burned forever — **rotation (above) is the fix**. History scrubbing (`git filter-repo` + force-push + redeploy) is optional and only worth it if the repo will ever be shared | Audit result documented in the risk register |
| 3.8 | `.gitignore`: `.env`, `*.key`, `deploy/.env`, `data/`. `git rm --cached` any offender already tracked | `git status` clean, no keys tracked |
| 3.9 | Confirm the GitHub Actions deploy key is a **dedicated** key (a repo secret), not your personal admin key | Check the secret name/origin in the workflow file |

---

## Phase 4 — API authentication & identity (60–90 min)

**Design decisions (pilot-honest):**
- Identity comes from a **server-side token→user map**, never from a client header — `X-Vulcan-User` is ignored (trivially spoofable). Real SSO is Phase 4 proper.
- Fail-closed: no token configured → mutating routes return 503, never open.
- `/healthz` stays exempt (probes). Disable `/docs` in Option B (`docs_url=None` when `VULCAN_ENV=prod`) — Swagger on the public internet is recon material.

**`backend/app/api/auth.py` (new file):**

```python
"""API token authentication — Step-1 hardening.
Identity derives from the server-side token map. Client-supplied identity
headers are never trusted. Fails closed when unconfigured."""
import json, os, secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/healthz", "/health", "/api/v1/health", "/docs", "/openapi.json", "/redoc"}


def load_token_map() -> dict[str, str]:
    raw = os.getenv("VULCAN_API_TOKENS")          # '{"<token>": "lead.bob", "<token>": "eng.alice"}'
    if raw:
        return json.loads(raw)
    single, user = os.getenv("VULCAN_API_TOKEN"), os.getenv("VULCAN_API_USER", "system.admin")
    return {single: user} if single else {}


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token_map: dict[str, str], allow_disabled: bool = False):
        super().__init__(app)
        self._tokens = {k: v for k, v in token_map.items() if k}
        self._allow_disabled = allow_disabled      # local dev only, explicit opt-in

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        if not self._tokens:
            if self._allow_disabled:
                request.state.user_id = "local.dev"
                return await call_next(request)
            return JSONResponse(status_code=503, content={
                "error_code": "ERR_VULCAN_AUTH_NOT_CONFIGURED",
                "message": "API token authentication not configured; refusing unauthenticated access."})

        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") \
            else request.headers.get("x-vulcan-api-key", "")
        user_id = next((u for t, u in self._tokens.items() if secrets.compare_digest(token, t)), None)
        if user_id is None:
            return JSONResponse(status_code=401, content={
                "error_code": "ERR_VULCAN_UNAUTHENTICATED",
                "message": "Missing or invalid API token."})
        request.state.user_id = user_id            # identity from server-side map ONLY
        return await call_next(request)
```

**`backend/app/api/server.py` wiring:**

```python
from app.api.auth import APIKeyMiddleware, load_token_map

app.add_middleware(APIKeyMiddleware,
                   token_map=load_token_map(),
                   allow_disabled=os.getenv("VULCAN_AUTH_DISABLED", "") == "1")  # never set on the VM
```

**Close Gap 2 — the execute endpoint (`routes.py`):** add `WORKFLOW_DISPATCH` to the `Permission` enum (grant to `APPROVING_LEAD` + `PLATFORM_ADMIN`), then:

```python
@router.post("/jobs/{correlation_id}/execute")
def execute_job(correlation_id: str, request: Request):
    actor = request.state.user_id                      # from token map, not the client
    if not policy_manager.check_user_permission(actor, Permission.WORKFLOW_DISPATCH):
        raise HTTPException(status_code=403, detail={
            "error_code": "ERR_VULCAN_RBAC",
            "message": f"User [{actor}] lacks permission [workflow:dispatch]."})
    job = _job(correlation_id)
    container.audit.record(job, "EXECUTION_TRIGGERED", {"actor": actor})   # synchronous, before dispatch
    ...  # existing execution path
```

**Frontend (`lib/api.ts`):** attach `Authorization: Bearer ${process.env.NEXT_PUBLIC_VULCAN_API_TOKEN}` to every request, and surface 401 as an explicit auth-error state. *(Caveat to log in the risk register: a NEXT_PUBLIC token ships in the browser bundle — acceptable for a single-operator pilot, closed by same-origin proxy or login flow later.)*

**Tests to add (suite must fail without the fix):** 401 without token · 401 with bad token · `eng.alice` token → execute 403 · `lead.bob` token → 200 **and** an `EXECUTION_TRIGGERED` audit row exists. Add a matching probe to `verify-matrix-claims.py`.

**Exit criterion:** external unauthenticated curl to any API route → 401; the flagship flow (Phase 6) works with tokens.

---

## Phase 5 — Deploy pipeline gating (30 min)

Push-to-main currently deploys with **zero test gate**. In the Actions workflow:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }        # stable in CI even though venv runs 3.14 (D8)
      - run: pip install -r backend/requirements.txt
      - run: cd backend && python -m pytest tests -q
      - run: cd .. && python scripts/verify-matrix-claims.py --hermetic
      - uses: gitleaks/gitleaks-action@v3       # secrets never re-enter the repo
  deploy:
    needs: test                                  # nothing deploys unless green
    if: github.ref == 'refs/heads/main'
    # existing deploy steps
```

**Exit criterion:** a deliberately broken test commit blocks deployment; a green commit deploys.

---

## Phase 6 — Verification & sign-off

| # | Check (external unless noted) | Expected |
|---|---|---|
| 6.1 | `nc -vz -w3 141.148.195.233 {22,3000,8000,9000,9001,2222,5432,6379}` | Only 22 (+ Option B ports). All others closed/filtered |
| 6.2 | `curl -i http://<host>/api/v1/jobs` (no token) | **401** `ERR_VULCAN_UNAUTHENTICATED` |
| 6.3 | Same with valid token | 200 |
| 6.4 | `curl -X POST .../jobs/<id>/execute` with `eng.alice` token | **403** `ERR_VULCAN_RBAC` |
| 6.5 | Compose literal-secret grep (3.2) | Only `${...}` refs |
| 6.6 | `git log -p` secret audit result documented | Risk register entry with rotation proof |
| 6.7 | `pytest` + `verify-matrix-claims.py --hermetic` | All green, including new auth probes |
| 6.8 | **Flagship demo (Gap 3):** `sec-system-hardening` (HIGH) → `PENDING_APPROVAL` → self-approve attempt → 403 → `lead.bob` approves → real SSH execution on sandbox → `SUCCESS`, and the Merkle ledger shows the full chain including `EXECUTION_TRIGGERED` | Captured as `docs/WALKTHROUGH_FLAGSHIP_GOVERNANCE.md` — this is your first true phase-gate evidence artifact |

**Residual risks to record (owner: platform_sre):** plaintext HTTP bearer tokens (closes with TLS/domain) · token in frontend bundle (closes with auth flow) · single shared tokens, no rotation schedule (closes with OIDC) · floating-branch execution (already filed, Git-SHA worktrees pending).
