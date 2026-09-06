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
}

# Set default test environment variables BEFORE app import
os.environ.setdefault("VULCAN_AUTH_DISABLED", "0")
os.environ.setdefault("VULCAN_API_TOKENS", json.dumps(TEST_TOKENS))
os.environ.setdefault("NEXT_PUBLIC_VULCAN_API_TOKEN", "vlc_test_alice")
