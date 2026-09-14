"""
Project Vulcan: PyTest Session Fixtures and Environment Initialization
Configures hermetic test API tokens and disables auth bypass so all tests run with VULCAN_AUTH_DISABLED=0.
"""
import json
import os
import pytest

TEST_TOKENS = {
    "vlc_test_alice": "eng.alice",
    "vlc_test_bob": "lead.bob",
    "vlc_test_admin": "admin.dave",
    "vlc_test_sec": "sec.carol",
    "vlc_test_charlie": "operator.charlie",
    "vlc_test_dave_ci_token": "admin.dave",
    "vlc_test_bob_ci_token": "lead.bob",
    "vlc_test_alice_ci_token": "eng.alice",
    "vlc_test_carol_ci_token": "sec.carol",
    "vlc_test_emma_ci_token": "audit.emma",
    "vlc_test_bot_ci_token": "e2e.bot",
}

# Set default test environment variables BEFORE app import
os.environ.setdefault("VULCAN_AUTH_DISABLED", "0")
os.environ.setdefault("VULCAN_API_TOKENS", json.dumps(TEST_TOKENS))
os.environ.setdefault("NEXT_PUBLIC_VULCAN_API_TOKEN", "vlc_test_alice")
os.environ.setdefault("AGENTOS_MODE", "development")
