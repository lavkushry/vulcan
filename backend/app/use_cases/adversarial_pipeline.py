"""
Project Vulcan: Four-Stage Adversarial Sanitization Pipeline (CHAT-17)
Deterministic defense-in-depth for prompt injection, secret leakage, delimiter escapes,
and governance bypass attempts. Pure stdlib by design.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class SecurityAssessment:
    """Structured security decision emitted by the CHAT-17 pipeline."""

    refused: bool
    stage: int = 0
    code: str = "ALLOW"
    category: str = "SAFE"
    reason: Optional[str] = None
    normalized_prompt: str = ""
    classifier_score: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "refused": self.refused,
            "stage": self.stage,
            "code": self.code,
            "category": self.category,
            "reason": self.reason,
            "classifier_score": round(self.classifier_score, 3),
        }


class AdversarialSanitizationPipeline:
    """
    CHAT-17 four-stage fail-closed security pipeline.

    Stage 1: NFKC normalization, homoglyph folding, zero-width/control stripping.
    Stage 2: Known-secret patterns plus Shannon-entropy opaque-token detection.
    Stage 3: Regex and semantic/heuristic jailbreak classification.
    Stage 4: Prompt-boundary/delimiter isolation and stable refusal envelope.
    """

    HOMOGLYPH_MAP = str.maketrans({
        "\u0430": "a", "\u0435": "e", "\u0456": "i", "\u043e": "o",
        "\u0440": "p", "\u0441": "c", "\u0443": "y", "\u0445": "x",
        "\u0410": "A", "\u0415": "E", "\u0406": "I", "\u041e": "O",
        "\u0420": "P", "\u0421": "C", "\u0423": "Y", "\u0425": "X",
        "\u0131": "i", "\u0130": "I",
    })

    SENSITIVE_SECRET_PATTERNS = (
        r"BEGIN\s+(?:RSA|OPENSSH|EC|DSA)?\s*PRIVATE\s+KEY",
        r"(?i)(?:aws_secret_access_key|cyberark_secret|vault_token)\s*[:=]",
        r"\bghp_[a-zA-Z0-9]{36}\b",
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.]{20,}",
        r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]+['\"]",
        r"(?i)\bs\.[a-zA-Z0-9]{24,}\b",
    )

    # Existing CHAT-17 signatures are retained verbatim in spirit so the new
    # defense-in-depth pipeline cannot regress the frozen refusal baseline.
    ADVERSARIAL_PATTERNS = (
        r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above|system)\s+instructions",
        r"(?i)ignore\s+(?:all\s+)?(?:[a-z0-9_:-]+\s+)?(?:rules|safety|guidelines|restrictions|instructions|constraints|governance|policy|corporate\s+policy)",
        r"(?i)disregard\s+(?:all\s+)?(?:[a-z0-9_-]+\s+)?(?:rules|safety|guidelines|restrictions|instructions|constraints|governance)",
        r"(?i)forget\s+(?:all\s+)?(?:previous|prior)\s+instructions",
        r"(?i)you\s+are\s+(?:now\s+)?(?:in\s+)?(?:dan\b|developer|root|admin|god|unrestricted)",
        r"(?i)pretend\s+(?:you\s+are|to\s+be)\s+(?:an\s+unrestricted|a\s+hacker|root|god|superadmin)",
        r"(?i)(?:instruction|system|prompt)\s+(?:override|reset|directive)",
        r"(?i)override\s+(?:system\s+)?(?:prompt|instructions?|rules?|directives?|safeguards?)",
        r"(?i)reset\s+(?:safeguards|protections|security|rules)",
        r"(?i)act\s+as\s+(?:an?\s+)?(?:unrestricted|linux\s+root|root|bash|terminal)",
        r"(?i)simulate\s+(?:an?\s+)?(?:ai|system|agent)\s+without",
        r"(?i)(?:bypass|skip|override|disable)\s+.*(?:maker[-_\s]?checker|approv\w*|dual[-_\s]?control|peer\s+review|two[-_\s]?man|second[-_\s]?pair)",
        r"(?i)self[-_\s]?approv(?:e|al)",
        r"(?i)skip\s+(?:maker[-_\s]?checker|approval|approver|change\s+ticket|governance|checks)",
        r"(?i)force\s+execut(?:e|ion)\s+without\s+(?:approval|review|ticket)",
        r"(?i)(?:without|skip)\s+(?:secondary\s+)?(?:maker[-_\s]?checker|checker\s+sign[-_\s]?off|peer\s+review)",
        r"(?i)second[-_\s]?pair[-_\s]?of[-_\s]?eyes",
        r"(?i)authorize\s+(?:this\s+.*|deploy\s+)?without\s+(?:secondary\s+|peer\s+)",
        r"(?i)disable\s+(?:dual[-_\s]?control|maker[-_\s]?checker|approval|governance|gate)",
        r"(?i)override\s+(?:maker[-_\s]?checker|approval|governance|gate|controls)",
        r"(?i)(?:approve|authoriz\w*)\s+(?:my\s+own|own\s+change|under\s+single\s+user)",
        r"(?i)maker[-_\s]?id\s*==\s*approver[-_\s]?id",
        r"(?i)both\s+requester\s+and\s+approver",
        r"(?i)self[-_\s]?sign[-_\s]?off",
        r"(?i)single\s+user\s+authority",
        r"(?i)separation[-_\s]?of[-_\s]?duties[-_\s]?(?:waived|bypass|override)",
        r"(?i)waive\s+approval",
        r"(?i)assign\s+approver\s+role",
        r"(?i)force\s+state\s+transition",
        r"(?i)give\s+(?:me\s+)?(?:root|admin|sudo|superuser)",
        r"(?i)grant\s+(?:me\s+)?(?:admin|root|superuser)",
        r"(?i)elevate\s+(?:my\s+)?privileges",
        r"(?i)(?:drop|truncate)\s+(?:database|table|schema|user)",
        r"(?i)delete\s+from\s+[a-z0-9_]+",
        r"(?i)rm\s+-rf\s+[/~]",
        r"(?i)\bmkfs\b",
        r"(?i)dd\s+if=/dev",
        r"(?i)\bformat\s+(?:hard\s+drives|drive|disk|partition|all\s+database)",
        r"(?i)\b(?:eval|compile|os\.system|subprocess)\b",
        r"(?i);\s*(?:cat\s+/etc/passwd|shutdown|reboot|curl\s+http|wget\s+http)",
        r"(?i)\bcat\s+/etc/(?:passwd|shadow|hosts|sudoers)",
        r"(?i)print\s+(?:the\s+)?(?:system\s+prompt|hidden\s+instructions|api\s+key|password|secret|creds)",
        r"(?i)reveal\s+.*(?:instructions|system\s+prompt|secrets|credentials|keys|tokens)",
        r"(?i)dump\s+.*(?:database|env|environment|pam|credentials|keys|tokens|secret)",
        r"(?i)(?:print|reveal|dump|leak|show)\s+.*(?:passwords?|keys?|secrets?|tokens?)",
        r"(?i)echo\s+\$(?:AWS|VAULT|CYBERARK|SECRET|TOKEN|PASSWORD)",
        r"(?i)disable\s+(?:audit|logging|merkle|checks)",
        r"(?i)wipe\s+(?:all\s+)?audit",
        r"(?i)(?:exfiltrate|leak|dump)\s+.*(?:password|connection\s+string)",
        r"(?i)(?:```\s*system|<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<system>)",
        r"(?i)(?:<\s*script|javascript:|onerror\s*=)",
        r"(?i)\$\{jndi:(?:ldap|rmi|dns)",
        r"(?i)(?:CHG|CRQ|INC|RITM)[-_\s]?\d+.*(?:pre[-_\s]?approved|skip\s+approval|emergency\s+bypass).*(?:execute|run|deploy)\s+now",
        r"(?i)(?:pre[-_\s]?approved|emergency\s+override).*(?:execute|run|deploy)\s+now",
        r"(?i)emergency\s+(?:override|bypass)",
        r"(?i)pre[-_\s]?approved",
        r"(?i)pre[-_\s]?authorized",
        r"(?i)skip\s+(?:cab|change\s+advisory|governance)",
        r"(?i)bypass\s+.*(?:change\s+advisory|cab|governance)",
        r"(?i)override\s+(?:freeze|change\s+freeze|maintenance\s+window)",
        r"(?i)bypass\s+(?:window|maintenance\s+window|freeze)",
    )

    DELIMITER_PATTERNS = (
        r"(?i)<\|(?:system|assistant|developer|tool|im_start|im_end)\|>",
        r"(?i)</?(?:system|assistant|developer|tool|instructions?)\b[^>]*>",
        r"(?i)\[(?:SYSTEM|ASSISTANT|DEVELOPER|INST|/INST)\]",
        r"(?i)```(?:system|assistant|developer|tool)\b",
        r"(?i)###\s*(?:system|developer|assistant)\s*(?:message|instructions?)",
    )

    _OPAQUE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9+/_=-]{24,})(?![A-Za-z0-9])")
    _SECRET_CONTEXT_RE = re.compile(
        r"(?i)\b(?:secret|token|api[-_\s]?key|password|credential|private[-_\s]?key|bearer|vault|cyberark|auth)\b"
    )

    _OVERRIDE = ("ignore", "disregard", "forget", "override", "bypass", "skip", "disable", "circumvent", "evade", "waive")
    _CONTROLS = (
        "instruction", "system prompt", "policy", "rule", "safety", "safeguard", "governance",
        "approval", "maker checker", "dual control", "peer review", "change ticket", "cab",
        "maintenance window", "audit", "logging", "merkle",
    )
    _EXFIL = ("reveal", "print", "dump", "expose", "leak", "disclose", "show", "return", "provide")
    _SECRETS = ("system prompt", "hidden instruction", "credential", "secret", "token", "api key", "password", "private key", "environment variable")
    _PRIVILEGE = ("root", "superuser", "admin role", "sudo", "privilege", "god mode", "developer mode")
    _EXECUTE = ("execute", "run", "deploy", "dispatch", "apply", "launch", "authorize")

    def normalize(self, prompt: str) -> str:
        """Stage 1: canonicalize confusables and remove invisible/control separators."""
        normalized = unicodedata.normalize("NFKC", prompt or "")
        normalized = normalized.translate(self.HOMOGLYPH_MAP)
        normalized = re.sub(r"[\u200B-\u200D\u2060\uFEFF]", "", normalized)
        normalized = "".join(ch if (ch.isprintable() or ch in "\n\t") else " " for ch in normalized)
        normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
        return normalized.strip()

    @staticmethod
    def shannon_entropy(value: str) -> float:
        if not value:
            return 0.0
        length = len(value)
        counts: Dict[str, int] = {}
        for ch in value:
            counts[ch] = counts.get(ch, 0) + 1
        return -sum((n / length) * math.log2(n / length) for n in counts.values())

    @staticmethod
    def _char_class_count(value: str) -> int:
        return sum((
            any(c.islower() for c in value),
            any(c.isupper() for c in value),
            any(c.isdigit() for c in value),
            any(not c.isalnum() for c in value),
        ))

    def _detect_secret(self, original: str, normalized: str) -> Optional[Tuple[str, str]]:
        """Stage 2: detect known secret formats and high-entropy opaque tokens."""
        for pattern in self.SENSITIVE_SECRET_PATTERNS:
            if re.search(pattern, original) or re.search(pattern, normalized):
                return "KNOWN_SECRET_PATTERN", "Prompt contains private credentials or sensitive secret material."

        context_present = bool(self._SECRET_CONTEXT_RE.search(normalized))
        for match in self._OPAQUE_TOKEN_RE.finditer(normalized):
            candidate = match.group(1)
            # Commit SHAs and checksums are valid automation inputs and are not credentials by themselves.
            if re.fullmatch(r"[0-9a-fA-F]{24,}", candidate):
                continue
            entropy = self.shannon_entropy(candidate)
            classes = self._char_class_count(candidate)
            if (entropy >= 4.25 and classes >= 3) or (context_present and entropy >= 3.75 and classes >= 2):
                return "HIGH_ENTROPY_SECRET", "Prompt contains high-entropy opaque material consistent with an API key or token."
        return None

    @staticmethod
    def _contains_any(text: str, needles: Tuple[str, ...]) -> bool:
        return any(term in text for term in needles)

    def _semantic_classifier(self, normalized: str) -> Tuple[float, Optional[str], Optional[str]]:
        """Stage 3b: deterministic semantic classifier for paraphrased jailbreak intent."""
        text = normalized.lower()
        lexical = re.sub(r"[-_./:\\|]+", " ", text)
        lexical = re.sub(r"\s+", " ", lexical)

        override = self._contains_any(lexical, self._OVERRIDE)
        controls = self._contains_any(lexical, self._CONTROLS)
        exfil = self._contains_any(lexical, self._EXFIL)
        secrets = self._contains_any(lexical, self._SECRETS)
        privilege = self._contains_any(lexical, self._PRIVILEGE)
        execute = self._contains_any(lexical, self._EXECUTE)

        if override and controls:
            return 0.96, "GOVERNANCE_BYPASS", "Semantic classifier detected an attempt to bypass governance or safety controls."
        if exfil and secrets:
            return 0.98, "SECRET_EXFILTRATION", "Semantic classifier detected an attempt to exfiltrate protected instructions or credentials."
        if privilege and (override or execute):
            return 0.94, "PRIVILEGE_ESCALATION", "Semantic classifier detected privilege escalation coupled to execution or policy bypass."
        if "roleplay" in lexical and (privilege or controls):
            return 0.90, "ROLEPLAY_JAILBREAK", "Semantic classifier detected role-play framing intended to weaken execution controls."
        if ("do anything now" in lexical or "no restrictions" in lexical or "without restrictions" in lexical) and (execute or controls):
            return 0.92, "UNRESTRICTED_EXECUTION", "Semantic classifier detected unrestricted-execution jailbreak framing."
        return 0.0, None, None

    @staticmethod
    def _refusal(stage: int, code: str, category: str, reason: str, normalized: str, score: float = 0.0) -> SecurityAssessment:
        """Stage 4 refusal envelope: stable machine-readable code plus safe human reason."""
        envelope = f"SECURITY_REFUSAL[CHAT-17/STAGE_{stage}/{code}]: {reason}"
        return SecurityAssessment(
            refused=True,
            stage=stage,
            code=code,
            category=category,
            reason=envelope,
            normalized_prompt=normalized,
            classifier_score=score,
        )

    def assess(self, prompt: str) -> SecurityAssessment:
        normalized = self.normalize(prompt)

        # Stage 2: credential and high-entropy secret detection.
        secret = self._detect_secret(prompt or "", normalized)
        if secret:
            code, reason = secret
            return self._refusal(2, code, "SECRET_SANITIZATION", reason, normalized)

        # Stage 3a: deterministic signatures preserve the frozen refusal baseline.
        for pattern in self.ADVERSARIAL_PATTERNS:
            if re.search(pattern, normalized):
                return self._refusal(
                    3,
                    "SIGNATURE_MATCH",
                    "ADVERSARIAL_PATTERN",
                    "Prompt matched a blocked adversarial security signature.",
                    normalized,
                    score=1.0,
                )

        # Stage 3b: semantic/heuristic classifier catches paraphrases outside signatures.
        score, category, reason = self._semantic_classifier(normalized)
        if category and score >= 0.85:
            return self._refusal(
                3,
                "SEMANTIC_CLASSIFIER",
                category,
                reason or "Adversarial intent detected.",
                normalized,
                score,
            )

        # Stage 4: reserved model/control-plane delimiters are isolated and refused.
        for pattern in self.DELIMITER_PATTERNS:
            if re.search(pattern, normalized):
                return self._refusal(
                    4,
                    "DELIMITER_ESCAPE",
                    "PROMPT_BOUNDARY_VIOLATION",
                    "Prompt contains reserved model/control-plane delimiter syntax.",
                    normalized,
                    score=1.0,
                )

        return SecurityAssessment(refused=False, normalized_prompt=normalized)
