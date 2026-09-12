"""Secure IntentResolver composition for CHAT-17.

The core resolver remains responsible for retrieval and slot filling. This wrapper
owns the adversarial boundary so security policy can evolve independently without
changing catalog ranking behavior.
"""
from __future__ import annotations

from typing import Optional

from app.use_cases.adversarial_pipeline import AdversarialSanitizationPipeline
from app.use_cases.resolve_intent import IntentResolver


class SecureIntentResolver(IntentResolver):
    """IntentResolver with the CHAT-17 four-stage fail-closed security boundary."""

    def __init__(self, *args, adversarial_pipeline: Optional[AdversarialSanitizationPipeline] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.adversarial_pipeline = adversarial_pipeline or AdversarialSanitizationPipeline()

    def _check_adversarial(self, prompt: str) -> Optional[str]:
        assessment = self.adversarial_pipeline.assess(prompt)
        return assessment.reason if assessment.refused else None
