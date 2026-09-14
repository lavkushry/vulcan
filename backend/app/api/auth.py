"""API token authentication — Step-1 hardening.
Identity derives from the server-side token map. Client-supplied identity
headers are never trusted. Fails closed when unconfigured."""
import json, os, secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {
    "/healthz", "/health", "/api/v1/health", "/docs", "/openapi.json", "/redoc",
    "/ready", "/metrics", "/api/v1/catalog", "/catalog",
    "/api/v1/auth/session", "/api/v1/auth/verify-token", "/api/v1/auth/login",
}


DEV_DEFAULT_TOKENS = {
    "vlc_test_dave_ci_token": "admin.dave",
    "vlc_test_bob_ci_token": "lead.bob",
    "vlc_test_alice_ci_token": "eng.alice",
    "vlc_test_carol_ci_token": "sec.carol",
    "vlc_test_emma_ci_token": "audit.emma",
    "vlc_test_bot_ci_token": "e2e.bot",
    "vlc_test_admin": "admin.dave",
    "vlc_test_alice": "eng.alice",
    "vlc_test_bob": "lead.bob",
    "vlc_test_sec": "sec.carol",
}


def load_token_map() -> dict[str, str]:
    tokens: dict[str, str] = {}
    # Explicit development opt-in: both VULCAN_ALLOW_DEV_TOKENS=true and AGENTOS_MODE=development required.
    # Unconfigured authentication fails closed by default.
    allow_dev = os.getenv("VULCAN_ALLOW_DEV_TOKENS", "").lower() in ("true", "1", "yes")
    agentos_mode = os.getenv("AGENTOS_MODE", "").lower()
    if allow_dev and agentos_mode == "development":
        tokens.update(DEV_DEFAULT_TOKENS)


    raw = os.getenv("VULCAN_API_TOKENS")          # '{"<token>": "lead.bob", "<token>": "eng.alice"}'
    if raw:
        try:
            tokens.update(json.loads(raw))
            return tokens
        except Exception:
            pass
    single, user = os.getenv("VULCAN_API_TOKEN"), os.getenv("VULCAN_API_USER", "system.admin")
    if single:
        tokens[single] = user
    return tokens


def authenticate_token(token: str, token_map: dict[str, str] | None = None) -> str | None:
    """Validates an API token using constant-time comparison against the token map."""
    if not token:
        return None
    tokens = token_map if token_map is not None else load_token_map()
    return next((u for t, u in tokens.items() if secrets.compare_digest(token, t)), None)



class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token_map: dict[str, str], allow_disabled: bool = False):
        super().__init__(app)
        self._tokens = {k: v for k, v in token_map.items() if k}
        self._allow_disabled = allow_disabled      # local dev only, explicit opt-in

    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") \
            else (request.headers.get("x-vulcan-api-key", "") or request.query_params.get("token", ""))
        user_id = authenticate_token(token, self._tokens)

        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            if user_id:
                request.state.user_id = user_id
            return await call_next(request)

        if not self._tokens:
            if self._allow_disabled:
                request.state.user_id = "local.dev"
                return await call_next(request)
            return JSONResponse(status_code=503, content={
                "error_code": "ERR_VULCAN_AUTH_NOT_CONFIGURED",
                "message": "API token authentication not configured; refusing unauthenticated access."})

        if user_id is None:
            return JSONResponse(status_code=401, content={
                "error_code": "ERR_VULCAN_UNAUTHENTICATED",
                "message": "Missing or invalid API token."})
        request.state.user_id = user_id            # identity from server-side map ONLY
        return await call_next(request)
