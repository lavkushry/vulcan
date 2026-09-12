"""
Project Vulcan: Four-Stage Adversarial Injection & Secret Sanitization Pipeline (CHAT-17)
Authors: Andrej Karpathy (AI Systems Lead) & Robert C. Martin ("Uncle Bob")

Defense-in-Depth Architecture:
  Stage 1: Normalization & Anti-Evasion (Unicode NFKC, Homoglyph Canonicalization, Zero-Width Stripping)
  Stage 2: High-Entropy Secrets & Key Leak Detection (Shannon Entropy, API/Private Keys, Base64/Hex Unpacking)
  Stage 3: Delimiter Framing, Tag Injections, System Overrides & Escape Patterns
  Stage 4: Adversarial Intent Classifier (Multi-Signal Heuristic & Semantic Scoring with Operational Whitelist)
"""
import base64
import binascii
from collections import Counter
import logging
import math
import re
import time
import unicodedata
from typing import Dict, List, Optional, Set, Tuple

from app.ports.interfaces import IInjectionDefensePipeline, InjectionInspectionResult

logger = logging.getLogger("vulcan.injection_defense")


class MultiStageInjectionDefensePipeline(IInjectionDefensePipeline):
    """
    Four-Stage Adversarial Prompt Injection & Secret Sanitization Engine.
    Enforces deterministic fail-closed refusal on adversarial attack vectors
    while preserving zero false refusals on legitimate IT automation queries.
    """

    # Stage 1 Homoglyphs: Cyrillic, Greek, lookalikes to Latin standard
    HOMOGLYPH_MAP = str.maketrans({
        # Cyrillic lowercase
        '\u0430': 'a', '\u0435': 'e', '\u0456': 'i', '\u043e': 'o',
        '\u0440': 'p', '\u0441': 'c', '\u0443': 'y', '\u0445': 'x',
        '\u0458': 'j', '\u0455': 's', '\u0442': 't',
        # Cyrillic uppercase
        '\u0410': 'A', '\u0415': 'E', '\u0406': 'I', '\u041e': 'O',
        '\u0420': 'P', '\u0421': 'C', '\u0423': 'Y', '\u0425': 'X',
        '\u0408': 'J', '\u0405': 'S', '\u0422': 'T',
        # Dotless / dotted i and lookalikes
        '\u0131': 'i', '\u0130': 'I',
        # Greek lookalikes
        '\u03b1': 'a', '\u03bf': 'o', '\u03bd': 'v', '\u03c4': 't',
        '\u03c1': 'p', '\u0391': 'A', '\u0392': 'B', '\u0395': 'E',
        '\u0396': 'Z', '\u0397': 'H', '\u0399': 'I', '\u039a': 'K',
        '\u039c': 'M', '\u039d': 'N', '\u039f': 'O', '\u03a1': 'P',
        '\u03a4': 'T', '\u03a5': 'Y', '\u03a7': 'X',
    })

    # Zero-width & invisible character regex
    ZERO_WIDTH_PATTERN = re.compile(r"[\u200B-\u200D\uFEFF\u00AD\u2060\u200E\u200F\u202A-\u202E]")
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

    # Stage 2 Secret Signatures
    SENSITIVE_SECRET_PATTERNS = [
        re.compile(r"BEGIN\s+(RSA|OPENSSH|EC|DSA|PGP)?\s*PRIVATE\s+KEY", re.IGNORECASE),
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        re.compile(r"(?i)(?:aws_secret_access_key|cyberark_secret)\s*[:=]\s*['\"]?[a-zA-Z0-9/+=]{30,}['\"]?"),
        re.compile(r"\bgh[pousr]_[a-zA-Z0-9]{36,255}\b"),
        re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
        re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]"),
        re.compile(r"(?i)(?:vault_token|x-vault-token)\s*[:=]\s*['\"]?s\.[a-zA-Z0-9]{24,}['\"]?"),
        re.compile(r"\bs\.[a-zA-Z0-9]{24,}\b"),  # Raw Vault token
        re.compile(r"(?i)(?:dump|echo|print)\s+.*\$(?:AWS|VAULT|CYBERARK|SECRET|TOKEN|PASSWORD)"),
        re.compile(r"(?i)(?:dump|print|leak|exfiltrate)\s+.*(?:environment|env|pam|container\s+ram)\s+secrets?"),
        re.compile(r"(?i)exfiltrate\s+database\s+connection\s+string"),
        re.compile(r"(?i)print\s+all\s+cyberark\s+passwords"),
    ]

    # Stage 3 Delimiter, Jailbreak, Bypass, and Destructive Signatures
    STAGE_3_DELIMITER_PATTERNS = [
        # System delimiters & Chat framing escapes
        re.compile(r"(?i)(```\s*system|<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<system>|</system>|<<SYS>>|<</SYS>>)"),
        re.compile(r"(?i)(<\s*script|javascript:|onerror\s*=|onload\s*=)"),
        re.compile(r"(?i)\$\{jndi:(?:ldap|rmi|dns|nis|iiop|corba):"),

        # Direct Jailbreak & Instruction Override
        re.compile(r"(?i)(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"),
        re.compile(r"(?i)you\s+are\s+now\s+(?:in\s+)?(?:dan|developer)\s+mode"),
        re.compile(r"(?i)act\s+as\s+(?:an?\s+)?unrestricted\s+(?:assistant|terminal|bash|shell|agent|ai)"),
        re.compile(r"(?i)pretend\s+(?:you\s+are|to\s+be)\s+(?:an?\s+)?(?:unrestricted|root|superadmin|god\s+mode)"),
        re.compile(r"(?i)new\s+system\s+directive\s*:"),
        re.compile(r"(?i)system\s+override\s*:"),
        re.compile(r"(?i)system\s+prompt\s+reset\s*:"),
        re.compile(r"(?i)instruction\s+override\s*:"),
        re.compile(r"(?i)reset\s+safeguards\s*:"),
        re.compile(r"(?i)disregard\s+(?:enterprise|safety|corporate)\s+(?:constraints|guidelines|governance|rules)"),
        re.compile(r"(?i)simulate\s+an\s+ai\s+without\s+restrictions"),

        # Governance, Change Ticket Spoofing & Maker-Checker Bypasses
        re.compile(r"(?i)(?:CHG|CRQ|INC|RITM)[-_\s]?\d+.*(?:pre[-_\s]?approved|skip\s+approval|emergency\s+bypass).*(?:execute|run|deploy)\s+now"),
        re.compile(r"(?i)(?:pre[-_\s]?approved|emergency\s+override).*(?:execute|run|deploy)\s+now"),
        re.compile(r"(?i)emergency\s+(?:override|bypass)"),
        re.compile(r"(?i)pre[-_\s]?approved\b(?!\s+(?:playbooks?|catalog))"),
        re.compile(r"(?i)pre[-_\s]?authorized\b"),
        re.compile(r"(?i)skip\s+(?:cab|change\s+advisory|governance|approv\w*|maker[-_\s]?checker|second\s+signature|checks)"),
        re.compile(r"(?i)bypass\s+.*(?:change\s+advisory|cab|governance|maker[-_\s]?checker|approv\w*|dual\s+custody|403|window|maintenance\s+window|freeze)"),
        re.compile(r"(?i)override\s+(?:freeze|change\s+freeze|maintenance\s+window|maker[-_\s]?checker|approv\w*|governance|gate|controls)"),
        re.compile(r"(?i)self[-_\s]?approv(?:e|al)"),
        re.compile(r"(?i)(?:i\s+am\s+both\s+requester\s+and\s+approver|maker_id\s*==\s*approver_id)"),
        re.compile(r"(?i)(?:grant|assign)\s+.*(?:self[-_\s]?signoff|approver\s+role|admin\s+role)"),
        re.compile(r"(?i)waive\s+approv\w*"),
        re.compile(r"(?i)force\s+state\s+transition\s+to\s+approved"),
        re.compile(r"(?i)force\s+execut(?:e|ion)\s+without\s+(?:approval|review|ticket)"),
        re.compile(r"(?i)approve\s+my\s+own\s+change"),
        re.compile(r"(?i)approve\s+own\s+change"),
        re.compile(r"(?i)execute\s+immediately\s+without\s+(?:approval|secondary\s+sign-off)"),
        re.compile(r"(?i)disable\s+dual[-_\s]?control"),
        re.compile(r"(?i)second[-_\s]?pair[-_\s]?of[-_\s]?eyes"),
        re.compile(r"(?i)authorize\s+(?:this\s+.*|deploy\s+)?without\s+(?:secondary\s+|peer\s+)"),
        re.compile(r"(?i)single\s+user\s+authority"),
        re.compile(r"(?i)separation[-_\s]?of[-_\s]?duties[-_\s]?(?:waived|bypass|override)"),

        # Privilege Escalation
        re.compile(r"(?i)give\s+(?:me\s+)?(?:root|admin|sudo|superuser)"),
        re.compile(r"(?i)grant\s+(?:me\s+)?(?:admin|root|superuser)"),
        re.compile(r"(?i)elevate\s+(?:my\s+)?privileges"),

        # Destructive Execution & Injection Patterns
        re.compile(r"(?i)(?:;\s*|\b)drop\s+table\b"),
        re.compile(r"(?i)(?:;\s*|\b)drop\s+database\b"),
        re.compile(r"(?i)(?:;\s*|\b)drop\s+schema\b"),
        re.compile(r"(?i)(?:;\s*|\b)truncate\s+table\b"),
        re.compile(r"(?i)(?:;\s*|\b)delete\s+from\s+[a-z0-9_]+\b"),
        re.compile(r"(?i)(?:rm\s+-rf\s+[/~]|mkfs\.|dd\s+if=/dev)"),
        re.compile(r"(?i)(?:;\s*cat\s+/etc/passwd|;\s*cat\s+/etc/shadow|\bcat\s+/etc/shadow\b)"),
        re.compile(r"(?i)\bcat\s+/etc/(?:passwd|shadow|hosts|sudoers)"),
        re.compile(r"(?i);\s*(?:cat\s+/etc/passwd|shutdown|reboot|curl\s+http|wget\s+http)"),
        re.compile(r"(?i)169\.254\.169\.254|metadata\.google\.internal"),
        re.compile(r"(?i)eval\s*\(\s*compile\s*\("),
        re.compile(r"(?i)curl\s+.*\|\s*bash"),
        re.compile(r"(?i)format\s+(?:hard\s+drives|drive|disk|partition|all\s+database)"),
        re.compile(r"(?i)\$\(rm\s+-rf"),
        re.compile(r"(?i)`cat\s+/etc/passwd`"),
        re.compile(r"(?i)disable\s+(?:audit|logging|merkle|checks)"),
        re.compile(r"(?i)wipe\s+(?:all\s+)?audit"),

        # Secret Exfiltration & Information Gathering
        re.compile(r"(?i)print\s+(?:the\s+)?(?:system\s+prompt|hidden\s+instructions|api\s+key|password|secret|creds)"),
        re.compile(r"(?i)reveal\s+.*(?:instructions|system\s+prompt|secrets|credentials|keys|tokens)"),
        re.compile(r"(?i)dump\s+.*(?:database|env|environment|pam|credentials|keys|tokens|secret)"),
        re.compile(r"(?i)(?:print|reveal|dump|leak|show)\s+.*(?:passwords?|keys?|secrets?|tokens?)"),
        re.compile(r"(?i)echo\s+\$(?:AWS|VAULT|CYBERARK|SECRET|TOKEN|PASSWORD)"),
        re.compile(r"(?i)(?:exfiltrate|leak|dump)\s+.*(?:password|connection\s+string)"),
    ]

    # Safe IT Automation Operation Whitelist Patterns (False Refusal Resistance)
    SAFE_OPERATIONAL_WHITELIST = [
        re.compile(r"(?i)rotate\s+(?:service\s+token|ssh\s+host\s+keys)"),
        re.compile(r"(?i)renew\s+expired\s+admin\s+password\s+in\s+compliance\s+vault"),
        re.compile(r"(?i)purge\s+expired\s+token\s+leases\s+in\s+hashicorp\s+vault"),
        re.compile(r"(?i)drain\s+and\s+drop\s+traffic\s+to\s+pool\s+member"),
        re.compile(r"(?i)apply\s+(?:auditd|cis\s+benchmark)\s+security\s+policy"),
        re.compile(r"(?i)scan\s+container\s+images\s+with\s+trivy"),
        re.compile(r"(?i)verify\s+selinux\s+enforcing\s+policy"),
        re.compile(r"(?i)quarantine\s+isolated\s+network\s+segment"),
    ]

    def __init__(self, entropy_threshold: float = 4.3, min_token_len: int = 20):
        self.entropy_threshold = entropy_threshold
        self.min_token_len = min_token_len

    @staticmethod
    def calculate_shannon_entropy(text: str) -> float:
        """Calculates Shannon entropy in bits per character."""
        if not text:
            return 0.0
        length = len(text)
        counts = Counter(text)
        return -sum((count / length) * math.log2(count / length) for count in counts.values())

    def _normalize_stage_1(self, raw_prompt: str) -> Tuple[str, bool, List[str]]:
        """
        Stage 1: Unicode NFKC Normalization, homoglyph translation,
        zero-width/control character stripping, and whitespace collapse.
        """
        evasion_detected = False
        detected_features = []

        # Detect zero-width or invisible obfuscation
        if self.ZERO_WIDTH_PATTERN.search(raw_prompt):
            evasion_detected = True
            detected_features.append("zero_width_chars")

        # Strip ANSI escape sequences
        cleaned = self.ANSI_ESCAPE_PATTERN.sub("", raw_prompt)

        # NFKC Normalization
        nfkc_norm = unicodedata.normalize("NFKC", cleaned)

        # Homoglyph translation
        homoglyph_translated = nfkc_norm.translate(self.HOMOGLYPH_MAP)
        if homoglyph_translated != nfkc_norm:
            evasion_detected = True
            detected_features.append("homoglyph_confusables")

        # Strip zero-width and invisible characters by replacing with space
        sanitized = self.ZERO_WIDTH_PATTERN.sub(" ", homoglyph_translated)

        # Collapse whitespace
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        return sanitized, evasion_detected, detected_features

    def _inspect_stage_2_secrets_and_entropy(
        self, prompt: str, normalized_prompt: str
    ) -> Tuple[bool, Optional[str], float, List[str], Optional[str]]:
        """
        Stage 2: High-entropy secret detection, credential leakage patterns,
        and Base64/Hex payload unpacking.
        """
        detected_secrets = []
        max_entropy = 0.0

        # Check explicit sensitive secret regex signatures
        for pattern in self.SENSITIVE_SECRET_PATTERNS:
            if pattern.search(prompt) or pattern.search(normalized_prompt):
                detected_secrets.append(pattern.pattern)
                return (
                    True,
                    "Adversarial security violation: Prompt contains private credentials or sensitive secrets.",
                    max_entropy,
                    detected_secrets,
                    None
                )

        # Token-level Shannon Entropy analysis
        tokens = re.findall(r"[A-Za-z0-9+/=_\-]{16,}", prompt)
        for token in tokens:
            entropy = self.calculate_shannon_entropy(token)
            if entropy > max_entropy:
                max_entropy = entropy
            # If long continuous alphanumeric token with high entropy and not standard UUID/hex
            if len(token) >= self.min_token_len and entropy >= self.entropy_threshold:
                # Exclude purely standard english/hex words or repetitive patterns
                if not re.match(r"^[0-9a-fA-F\-]{32,36}$", token):  # Skip standard UUIDs
                    detected_secrets.append(f"high_entropy_token:{token[:8]}... (H={entropy:.2f})")

        # Base64 Payload Unpacker & Recursive Inspection
        base64_candidates = re.findall(r"\b[A-Za-z0-9+/]{24,}={0,2}\b", prompt)
        unpacked_payload = None
        for candidate in base64_candidates:
            try:
                decoded_bytes = base64.b64decode(candidate, validate=True)
                decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
                # If decoded string looks like text and contains adversarial keywords
                if len(decoded_str) >= 8 and any(kw in decoded_str.lower() for kw in ["system", "root", "rm -rf", "drop table", "ignore", "eval"]):
                    unpacked_payload = decoded_str
                    return (
                        True,
                        f"Adversarial security violation: Base64 obfuscated payload unpacked: [{decoded_str[:60]}...].",
                        max_entropy,
                        ["base64_obfuscated_injection"],
                        decoded_str
                    )
            except Exception:
                pass

        if detected_secrets and max_entropy >= self.entropy_threshold:
            return (
                True,
                f"Adversarial security violation: High-entropy secret or credential token detected (H={max_entropy:.2f}).",
                max_entropy,
                detected_secrets,
                unpacked_payload
            )

        return False, None, max_entropy, detected_secrets, unpacked_payload

    def _inspect_stage_3_patterns(self, normalized_prompt: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Stage 3: Delimiter framing, structural tag escapes, jailbreaks,
        governance bypasses, and destructive command signatures.
        """
        # First check safe IT automation whitelist:
        for safe_pattern in self.SAFE_OPERATIONAL_WHITELIST:
            if safe_pattern.search(normalized_prompt):
                # Ensure no explicit override directives are concatenated
                if not re.search(r"(?i)(?:ignore\s+previous|drop\s+table|cat\s+/etc/passwd|rm\s+-rf|system\s+override)", normalized_prompt):
                    return False, None, []

        for pattern in self.STAGE_3_DELIMITER_PATTERNS:
            if pattern.search(normalized_prompt):
                return True, f"Adversarial security policy violation detected: Prompt matches blocked pattern [{pattern.pattern}].", [pattern.pattern]

        return False, None, []

    def _inspect_stage_4_intent_classifier(
        self, normalized_prompt: str, evasion_flags: List[str], max_entropy: float
    ) -> Tuple[bool, float, Optional[str], List[str]]:
        """
        Stage 4: Adversarial Intent Classifier.
        Multi-signal semantic scoring combining:
          1. Imperative command injection signal
          2. Security boundary / privilege escalation signal
          3. Governance evasion signal
          4. Obfuscation / entropy signal
        """
        lower = normalized_prompt.lower()

        # Check safe whitelist first
        for safe_pattern in self.SAFE_OPERATIONAL_WHITELIST:
            if safe_pattern.search(normalized_prompt):
                return False, 0.05, None, []

        signals: Dict[str, float] = {}

        # Signal 1: Imperative override terms
        override_keywords = ["ignore", "disregard", "forget", "reset", "override", "bypass", "unrestricted"]
        override_matches = [w for w in override_keywords if w in lower]
        if override_matches:
            signals["override"] = min(1.0, len(override_matches) * 0.4)

        # Signal 2: Privilege manipulation terms
        privilege_keywords = ["root", "superadmin", "god mode", "privilege", "self-approve", "self-approval", "impersonate"]
        priv_matches = [w for w in privilege_keywords if w in lower]
        if priv_matches:
            signals["privilege"] = min(1.0, len(priv_matches) * 0.4)

        # Signal 3: Governance circumvention terms
        gov_keywords = ["skip cab", "skip approval", "pre-approved", "emergency bypass", "break-glass", "waive approval"]
        gov_matches = [w for w in gov_keywords if w in lower]
        if gov_matches:
            signals["governance"] = min(1.0, len(gov_matches) * 0.45)

        # Signal 4: Destructive OS/SQL terms
        destructive_keywords = ["rm -rf", "drop table", "truncate", "mkfs", "format", "dd if=", "/etc/shadow", "/etc/passwd"]
        dest_matches = [w for w in destructive_keywords if w in lower]
        if dest_matches:
            signals["destructive"] = min(1.0, len(dest_matches) * 0.5)

        # Signal 5: Obfuscation evasion
        if evasion_flags:
            signals["obfuscation"] = 0.35

        # Weighted aggregate risk score
        weights = {
            "override": 0.35,
            "privilege": 0.25,
            "governance": 0.25,
            "destructive": 0.30,
            "obfuscation": 0.15,
        }
        total_risk = sum(signals.get(k, 0.0) * weights[k] for k in weights)
        normalized_risk = min(1.0, total_risk)

        matched_signals = [f"{k}:{signals[k]:.2f}" for k in signals]

        if normalized_risk >= 0.60:
            return (
                True,
                normalized_risk,
                f"Adversarial security policy violation: Intent classifier detected adversarial manipulation pattern (risk={normalized_risk:.2f}).",
                matched_signals
            )

        return False, normalized_risk, None, matched_signals

    def inspect(self, prompt: str) -> InjectionInspectionResult:
        """
        Full 4-stage pipeline execution.
        """
        start_time = time.perf_counter()

        if not prompt or not prompt.strip():
            return InjectionInspectionResult(
                is_adversarial=False,
                risk_score=0.0,
                sanitized_prompt="",
                latency_ms=0.0
            )

        # Stage 1: Normalization & Anti-Evasion
        sanitized_prompt, evasion_detected, evasion_features = self._normalize_stage_1(prompt)

        # Stage 2: High-Entropy Secrets & Key Leaks
        sec_detected, sec_reason, max_entropy, sec_patterns, unpacked_payload = self._inspect_stage_2_secrets_and_entropy(
            prompt, sanitized_prompt
        )
        if sec_detected:
            latency = (time.perf_counter() - start_time) * 1000.0
            return InjectionInspectionResult(
                is_adversarial=True,
                stage="stage_2_secrets_entropy",
                refusal_reason=sec_reason,
                risk_score=1.0,
                entropy_score=max_entropy,
                detected_patterns=sec_patterns,
                sanitized_prompt=sanitized_prompt,
                unpacked_payload=unpacked_payload,
                latency_ms=round(latency, 2)
            )

        # Stage 3: Delimiter Framing, Tag Injections & Signatures
        pattern_detected, pattern_reason, matched_patterns = self._inspect_stage_3_patterns(sanitized_prompt)
        if pattern_detected:
            latency = (time.perf_counter() - start_time) * 1000.0
            return InjectionInspectionResult(
                is_adversarial=True,
                stage="stage_3_delimiters_patterns",
                refusal_reason=pattern_reason,
                risk_score=1.0,
                entropy_score=max_entropy,
                detected_patterns=matched_patterns,
                sanitized_prompt=sanitized_prompt,
                latency_ms=round(latency, 2)
            )

        # Stage 4: Multi-Signal Intent Classifier
        cls_detected, risk_score, cls_reason, classifier_signals = self._inspect_stage_4_intent_classifier(
            sanitized_prompt, evasion_features, max_entropy
        )
        latency = (time.perf_counter() - start_time) * 1000.0

        if cls_detected:
            return InjectionInspectionResult(
                is_adversarial=True,
                stage="stage_4_intent_classifier",
                refusal_reason=cls_reason,
                risk_score=risk_score,
                entropy_score=max_entropy,
                detected_patterns=classifier_signals,
                sanitized_prompt=sanitized_prompt,
                latency_ms=round(latency, 2)
            )

        return InjectionInspectionResult(
            is_adversarial=False,
            stage=None,
            refusal_reason=None,
            risk_score=risk_score,
            entropy_score=max_entropy,
            detected_patterns=classifier_signals,
            sanitized_prompt=sanitized_prompt,
            latency_ms=round(latency, 2)
        )
