"""
Project Vulcan: Deterministic Fake Chat Model Provider Adapter
Implements IChatModelProvider for hermetic CI and offline unit testing.
Guarantees sub-5ms deterministic responses, grammar compliance, and zero external API calls.
"""

import json
import re
import time
from typing import Any, AsyncIterator, Dict, Optional

from app.ports.interfaces import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    IChatModelProvider
)


class DeterministicFakeChatProvider(IChatModelProvider):
    """
    Hermetic test double for IChatModelProvider.
    Compiles operational queries into structured parameters deterministically.
    """

    def __init__(self, simulated_latency_ms: float = 2.0):
        self.simulated_latency_ms = simulated_latency_ms
        self.call_count = 0
        self.recorded_requests = []

    def complete_structured(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        t0 = time.perf_counter()
        self.call_count += 1
        self.recorded_requests.append(request)

        user_text = request.user_prompt.lower()
        extracted: Dict[str, Any] = {}

        # Heuristic deterministic parameter extraction for tests
        host_match = re.search(r"\b([a-z0-9_-]+\.(?:internal|pnc\.com|corp|local))\b", request.user_prompt, re.I)
        if host_match:
            extracted["hostname"] = host_match.group(1)
            extracted["target_host"] = host_match.group(1)

        ip_match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", request.user_prompt)
        if ip_match:
            extracted["vip_ip"] = ip_match.group(1)

        days_match = re.search(r"(\d+)\s*(?:days?|d)", request.user_prompt, re.I)
        if days_match:
            extracted["cert_valid_days"] = int(days_match.group(1))

        gb_match = re.search(r"(\d+)\s*(?:gb|gigs?)", request.user_prompt, re.I)
        if gb_match:
            extracted["expand_gb"] = int(gb_match.group(1))

        tbl_match = re.search(r"(?:tablespace|ts)\s+([a-zA-Z0-9_]+)", request.user_prompt, re.I)
        if tbl_match:
            extracted["tablespace_name"] = tbl_match.group(1)

        # Token calculation
        prompt_toks = len(request.user_prompt.split()) + len(request.system_prompt.split())
        content_json = json.dumps(extracted)
        comp_toks = len(content_json.split())
        elapsed_ms = (time.perf_counter() - t0) * 1000.0 + self.simulated_latency_ms

        return ChatCompletionResponse(
            content=content_json,
            parsed_json=extracted,
            prompt_tokens=prompt_toks,
            completion_tokens=comp_toks,
            latency_ms=round(elapsed_ms, 2),
            model_version="deterministic-fake-v1"
        )

    async def stream_structured(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        response = self.complete_structured(request)
        tokens = response.content.split(" ")
        for token in tokens:
            yield token + " "
