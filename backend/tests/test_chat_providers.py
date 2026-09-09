"""
Project Vulcan: Chat Model Provider Contract Tests (IChatModelProvider)
Verifies:
1. OpenRouterChatProvider initialization, model resolution, and completion formatting.
2. OpenRouterChatProvider mock HTTP protocol contract.
3. OpenRouterChatProvider quota exhaustion handling (INV-AI-01: AIProviderQuotaExhaustedError).
4. get_chat_provider() factory resolution, environment overrides, and fail-closed behavior.
"""
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app.adapters.chat_providers import (
    GeminiChatProvider,
    OpenAIChatProvider,
    OpenRouterChatProvider,
    get_chat_provider,
)
from app.domain.exceptions import AIProviderQuotaExhaustedError
from app.ports.interfaces import ChatCompletionRequest, IChatModelProvider


class TestOpenRouterChatProvider(unittest.TestCase):
    def test_initialization_requires_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                OpenRouterChatProvider(api_key="")

    def test_initialization_success(self):
        provider = OpenRouterChatProvider(api_key="or_test_key_123", model="liquid/lfm-2.5-2.6b:free")
        self.assertEqual(provider.api_key, "or_test_key_123")
        self.assertEqual(provider.model, "liquid/lfm-2.5-2.6b:free")
        self.assertFalse(provider.quota_exhausted)

    def test_complete_structured_mocked(self):
        provider = OpenRouterChatProvider(api_key="or_test_key_123", model="liquid/lfm-2.5-2.6b:free")

        mock_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"vip_ip": "10.0.1.50", "days": 90}),
                        "role": "assistant"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 45,
                "completion_tokens": 18
            }
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        req = ChatCompletionRequest(
            system_prompt="You are a parameter extractor.",
            user_prompt="renew ssl cert on 10.0.1.50 for 90 days",
            grammar_json_schema={"type": "object", "properties": {"vip_ip": {"type": "string"}}}
        )

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = provider.complete_structured(req)
            self.assertEqual(resp.parsed_json, {"vip_ip": "10.0.1.50", "days": 90})
            self.assertEqual(resp.prompt_tokens, 45)
            self.assertEqual(resp.completion_tokens, 18)
            self.assertEqual(resp.model_version, "openrouter/liquid/lfm-2.5-2.6b:free")

    def test_quota_exhaustion_fail_closed(self):
        import urllib.error
        provider = OpenRouterChatProvider(api_key="or_test_key_123")

        err = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(json.dumps({"error": {"message": "Rate limit exceeded upstream"}}).encode())
        )

        req = ChatCompletionRequest(
            system_prompt="System",
            user_prompt="User"
        )

        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(AIProviderQuotaExhaustedError) as ctx:
                provider.complete_structured(req)
            self.assertTrue(provider.quota_exhausted)
            self.assertEqual(ctx.exception.provider, "openrouter")


class TestChatProviderFactory(unittest.TestCase):
    def test_factory_openrouter_explicit(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or_test_key"}):
            provider = get_chat_provider("openrouter")
            self.assertIsInstance(provider, OpenRouterChatProvider)

    def test_factory_openrouter_fail_closed_if_missing_key(self):
        with patch.dict(os.environ, {"VULCAN_CHAT_PROVIDER": "openrouter"}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                get_chat_provider()
            self.assertIn("OPENROUTER_API_KEY is missing", str(ctx.exception))

    def test_factory_auto_detection_openrouter(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or_test_key"}, clear=True):
            provider = get_chat_provider()
            self.assertIsInstance(provider, OpenRouterChatProvider)


if __name__ == "__main__":
    unittest.main()
