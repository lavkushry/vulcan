"""API token authentication — Step-1 hardening.
Identity derives from the server-side token map. Client-supplied identity
headers are never trusted. Fails closed when unconfigured."""
import json, os, secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/healthz", "/health", "/api/v1/health", "/docs", "/openapi.json", "/redoc", "/ready", "/metrics"}


def load_token_map() -> dict[str, str]:
    raw = os.getenv("VULCAN_API_TOKENS")          # '{"<token>": "lead.bob", "<token>": "eng.alice"}'
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
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
