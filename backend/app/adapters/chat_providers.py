"""
Project Vulcan: Real Chat Model Provider Adapters (IChatModelProvider Implementations)
Author: Andrej Karpathy (AI Systems Lead)

Provides:
1. OpenAIChatProvider: Real OpenAI GPT-4o / GPT-4o-mini structured decoding.
2. GeminiChatProvider: Real Google Gemini 1.5/2.0 Flash structured decoding.
3. DeterministicFakeChatProvider re-export for testing.
4. get_chat_provider(): Factory with fail-closed configuration enforcement.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, AsyncIterator, Dict, Optional

from app.adapters.fake_chat_adapter import DeterministicFakeChatProvider
from app.domain.exceptions import AIProviderQuotaExhaustedError
from app.ports.interfaces import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    IChatModelProvider,
)

logger = logging.getLogger("vulcan.chat_providers")


class OpenAIChatProvider(IChatModelProvider):
    """
    OpenAI Chat Completion provider with strict JSON schema constrained decoding.
    Uses standard library urllib (zero external pip dependencies).
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or ""
        self.model = model
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured for OpenAIChatProvider.")

    def complete_structured(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        t0 = time.perf_counter()
        url = "https://api.openai.com/v1/chat/completions"

        messages = [{"role": "system", "content": request.system_prompt}]
        for hist in request.conversation_history:
            messages.append(hist)
        messages.append({"role": "user", "content": request.user_prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Grammar-constrained decoding: JSON schema enforcement
        if request.grammar_json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "vulcan_parameter_extraction",
                    "strict": True,
                    "schema": request.grammar_json_schema,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw_resp = json.loads(resp.read().decode("utf-8"))
                choice = raw_resp["choices"][0]["message"]
                content = choice.get("content", "{}")
                usage = raw_resp.get("usage", {})

                parsed: Optional[Dict[str, Any]] = None
                try:
                    parsed = json.loads(content)
                except Exception as pe:
                    logger.warning("Failed to parse JSON from OpenAI response: %s", pe)

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return ChatCompletionResponse(
                    content=content,
                    parsed_json=parsed,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    latency_ms=round(elapsed_ms, 2),
                    model_version=f"openai/{self.model}",
                )
        except Exception as e:
            logger.error("OpenAI Chat Completion request failed: %s", e)
            raise

    async def stream_structured(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        # For non-streaming fallback
        response = self.complete_structured(request)
        tokens = response.content.split(" ")
        for token in tokens:
            yield token + " "


class GeminiChatProvider(IChatModelProvider):
    """
    Google Gemini chat provider with JSON schema constrained decoding.
    Uses standard library urllib (zero external pip dependencies).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or ""
        self.model = model or os.getenv("GEMINI_CHAT_MODEL") or "gemini-flash-latest"
        self.quota_exhausted: bool = False
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured for GeminiChatProvider.")

    def complete_structured(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        t0 = time.perf_counter()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        contents = []
        for hist in request.conversation_history:
            role = "user" if hist.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": hist.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": request.user_prompt}]})

        generation_config: Dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
            "responseMimeType": "application/json",
        }

        if request.grammar_json_schema:
            generation_config["responseSchema"] = request.grammar_json_schema

        payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": contents,
            "generationConfig": generation_config,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        max_retries = 5
        base_delay = 2.0
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw_resp = json.loads(resp.read().decode("utf-8"))
                    candidates = raw_resp.get("candidates", [])
                    content_text = "{}"
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            content_text = parts[0].get("text", "{}")

                    usage = raw_resp.get("usageMetadata", {})
                    parsed: Optional[Dict[str, Any]] = None
                    try:
                        parsed = json.loads(content_text)
                    except Exception as pe:
                        logger.warning("Failed to parse JSON from Gemini response: %s", pe)

                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    return ChatCompletionResponse(
                        content=content_text,
                        parsed_json=parsed,
                        prompt_tokens=usage.get("promptTokenCount", 0),
                        completion_tokens=usage.get("candidatesTokenCount", 0),
                        latency_ms=round(elapsed_ms, 2),
                        model_version=f"gemini/{self.model}",
                    )
            except urllib.error.HTTPError as e:
                err_body = {}
                try:
                    err_body = json.loads(e.read().decode("utf-8"))
                except Exception:
                    pass

                err_info = err_body.get("error", {})
                status_code_str = err_info.get("status", "")
                err_msg = err_info.get("message", "")
                details = err_info.get("details", [])

                is_daily = False
                qid = ""
                rd_sec = 0.0
                for d in details:
                    if d.get("@type", "").endswith("QuotaFailure"):
                        for v in d.get("violations", []):
                            q = v.get("quotaId", "")
                            if "PerDay" in q or "Daily" in q:
                                is_daily = True
                            if q:
                                qid = q
                    elif d.get("@type", "").endswith("RetryInfo"):
                        rd = d.get("retryDelay", "")
                        if rd.endswith("s"):
                            try:
                                rd_sec = float(rd[:-1])
                            except ValueError:
                                pass

                if status_code_str == "RESOURCE_EXHAUSTED" or is_daily or "PerDay" in err_msg or "quota exceeded" in err_msg.lower():
                    logger.error("Gemini Chat API daily quota exhausted: %s", err_msg)
                    self.quota_exhausted = True
                    raise AIProviderQuotaExhaustedError(
                        message=f"Gemini Chat API daily request quota reached (RESOURCE_EXHAUSTED). Free-tier limit reached.",
                        provider="gemini",
                        retry_after_seconds=rd_sec,
                        quota_id=qid or "GenerateContentRequestsPerDayPerProjectPerModel-FreeTier"
                    )

                if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    sleep_time = max(base_delay * (2 ** attempt), rd_sec + 1.0)
                    if e.code == 429:
                        sleep_time = max(sleep_time, 15.0)
                    logger.warning("Gemini Chat API HTTP %d. Retrying in %.1fs (attempt %d/%d)...",
                                   e.code, sleep_time, attempt + 1, max_retries)
                    time.sleep(sleep_time)
                else:
                    logger.error("Gemini Chat Completion request failed permanently: %s", e)
                    raise
            except AIProviderQuotaExhaustedError:
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning("Gemini Chat API network error: %s. Retrying in %.1fs (attempt %d/%d)...",
                                   e, sleep_time, attempt + 1, max_retries)
                    time.sleep(sleep_time)
                else:
                    logger.error("Gemini Chat Completion request failed permanently: %s", e)
                    raise

    async def stream_structured(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        response = self.complete_structured(request)
        tokens = response.content.split(" ")
        for token in tokens:
            yield token + " "


class OpenRouterChatProvider(IChatModelProvider):
    """
    OpenRouter Chat Completion provider with structured decoding.
    Routes to multi-model catalog via https://openrouter.ai/api/v1/chat/completions.
    Uses standard library urllib (zero external pip dependencies).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or ""
        self.model = model or os.getenv("OPENROUTER_CHAT_MODEL") or "liquid/lfm-2.5-2.6b:free"
        self.quota_exhausted: bool = False
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured for OpenRouterChatProvider.")

    def complete_structured(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        t0 = time.perf_counter()
        url = "https://openrouter.ai/api/v1/chat/completions"

        messages = [{"role": "system", "content": request.system_prompt}]
        for hist in request.conversation_history:
            messages.append(hist)
        messages.append({"role": "user", "content": request.user_prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Grammar-constrained decoding: JSON schema or JSON object
        if request.grammar_json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "vulcan_parameter_extraction",
                    "strict": True,
                    "schema": request.grammar_json_schema,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/project-vulcan/vulcan-control-plane",
                "X-Title": "Project Vulcan Control Plane",
            },
            method="POST",
        )

        max_retries = 3
        base_delay = 2.0
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw_resp = json.loads(resp.read().decode("utf-8"))
                    choices = raw_resp.get("choices", [])
                    content = "{}"
                    if choices:
                        choice = choices[0].get("message", {})
                        content = choice.get("content", "{}")

                    usage = raw_resp.get("usage", {})
                    parsed: Optional[Dict[str, Any]] = None
                    try:
                        parsed = json.loads(content)
                    except Exception as pe:
                        logger.warning("Failed to parse JSON from OpenRouter response: %s", pe)

                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    return ChatCompletionResponse(
                        content=content,
                        parsed_json=parsed,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        latency_ms=round(elapsed_ms, 2),
                        model_version=f"openrouter/{self.model}",
                    )
            except urllib.error.HTTPError as e:
                err_body = {}
                try:
                    err_body = json.loads(e.read().decode("utf-8"))
                except Exception:
                    pass

                err_info = err_body.get("error", {})
                err_msg = err_info.get("message", str(e)) if isinstance(err_info, dict) else str(e)

                if e.code == 429 or "rate limit" in err_msg.lower() or "quota" in err_msg.lower():
                    logger.error("OpenRouter Chat API rate limit / quota exhausted: %s", err_msg)
                    self.quota_exhausted = True
                    raise AIProviderQuotaExhaustedError(
                        message=f"OpenRouter Chat API rate limit / quota exhausted: {err_msg}",
                        provider="openrouter",
                        retry_after_seconds=3600.0,
                        quota_id="OpenRouterRateLimit"
                    )

                if e.code in (500, 502, 503, 504) and attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning("OpenRouter Chat API HTTP %d. Retrying in %.1fs (attempt %d/%d)...",
                                   e.code, sleep_time, attempt + 1, max_retries)
                    time.sleep(sleep_time)
                else:
                    logger.error("OpenRouter Chat Completion request failed permanently: %s", e)
                    raise
            except AIProviderQuotaExhaustedError:
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning("OpenRouter Chat API network error: %s. Retrying in %.1fs...", e, sleep_time)
                    time.sleep(sleep_time)
                else:
                    logger.error("OpenRouter Chat Completion request failed permanently: %s", e)
                    raise

    async def stream_structured(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        response = self.complete_structured(request)
        tokens = response.content.split(" ")
        for token in tokens:
            yield token + " "


def get_chat_provider(provider_type: Optional[str] = None) -> IChatModelProvider:
    """
    Factory resolving active chat model provider.
    Fails loudly if real provider is requested but API key is missing.
    """
    choice = (provider_type or os.getenv("VULCAN_CHAT_PROVIDER") or "").strip().lower()

    if choice in ("openai", "gpt-4o", "gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"VULCAN_CHAT_PROVIDER is set to '{choice}', but OPENAI_API_KEY is missing or empty. "
                "Failing closed without fallback (INV-AI-01: Zero silent synthetic degradation)."
            )
        model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        return OpenAIChatProvider(api_key=api_key, model=model)

    elif choice in ("gemini", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-flash-latest"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"VULCAN_CHAT_PROVIDER is set to '{choice}', but GEMINI_API_KEY is missing or empty. "
                "Failing closed without fallback (INV-AI-01: Zero silent synthetic degradation)."
            )
        model = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")
        return GeminiChatProvider(api_key=api_key, model=model)

    elif choice in ("openrouter", "open-router"):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"VULCAN_CHAT_PROVIDER is set to '{choice}', but OPENROUTER_API_KEY is missing or empty. "
                "Failing closed without fallback (INV-AI-01: Zero silent synthetic degradation)."
            )
        model = os.getenv("OPENROUTER_CHAT_MODEL")
        return OpenRouterChatProvider(api_key=api_key, model=model)

    elif choice in ("fake", "deterministic", "ci"):
        return DeterministicFakeChatProvider()

    # Auto-detection
    if os.getenv("OPENAI_API_KEY"):
        logger.info("Auto-selected OpenAIChatProvider via OPENAI_API_KEY.")
        model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        return OpenAIChatProvider(api_key=os.getenv("OPENAI_API_KEY"), model=model)
    elif os.getenv("GEMINI_API_KEY"):
        logger.info("Auto-selected GeminiChatProvider via GEMINI_API_KEY.")
        model = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")
        return GeminiChatProvider(api_key=os.getenv("GEMINI_API_KEY"), model=model)
    elif os.getenv("OPENROUTER_API_KEY"):
        logger.info("Auto-selected OpenRouterChatProvider via OPENROUTER_API_KEY.")
        model = os.getenv("OPENROUTER_CHAT_MODEL")
        return OpenRouterChatProvider(api_key=os.getenv("OPENROUTER_API_KEY"), model=model)

    # Default to hermetic fake for CI / offline development
    logger.info("Defaulted to DeterministicFakeChatProvider (Hermetic CI double).")
    return DeterministicFakeChatProvider()

