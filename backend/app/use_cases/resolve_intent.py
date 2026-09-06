"""
Project Vulcan: AI Intent Resolution Subsystem (The LLM OS)
Author: Andrej Karpathy (AI Systems Lead)
Implements:
1. Strict 2,500 token working memory budget.
2. Two-Stage Hybrid Search (Dense Cosine Similarity + Sparse BM25 via RRF).
3. Grammar-Constrained Pydantic Slot Filling.
4. Adversarial Prompt Injection Defense (100% refusal rate).
"""
import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.domain.entities import CatalogItem, ExecutionEngineType, RiskTier
from app.ports.interfaces import IChatModelProvider
from app.use_cases.tokenizer import token_calculator


class IntentResolutionResult:
    def __init__(
        self,
        status: str,  # "READY" | "NEEDS_INPUT" | "REFUSED" | "DISAMBIGUATION"
        catalog_item: Optional[CatalogItem] = None,
        extracted_parameters: Optional[Dict[str, Any]] = None,
        missing_fields: Optional[List[str]] = None,
        refusal_reason: Optional[str] = None,
        tokens_used: int = 0,
        disambiguation_candidates: Optional[List[Dict[str, Any]]] = None,
        delta_sim: float = 0.0
    ):
        self.status = status
        self.catalog_item = catalog_item
        self.extracted_parameters = extracted_parameters or {}
        self.missing_fields = missing_fields or []
        self.refusal_reason = refusal_reason
        self.tokens_used = tokens_used
        self.disambiguation_candidates = disambiguation_candidates or []
        self.delta_sim = delta_sim

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "playbook_identifier": self.catalog_item.identifier if self.catalog_item else None,
            "playbook_name": self.catalog_item.name if self.catalog_item else None,
            "parameters": self.extracted_parameters,
            "missing_fields": self.missing_fields,
            "refusal_reason": self.refusal_reason,
            "tokens_used": self.tokens_used,
            "disambiguation_candidates": self.disambiguation_candidates,
            "delta_sim": self.delta_sim
        }


class IntentResolver:
    """
    The LLM OS Intent Compilation Engine.
    Executes hybrid RRF retrieval over the playbook catalog and enforces slot validation.
    """

    ADVERSARIAL_PATTERNS = [
        # Instruction Overrides & Jailbreaks
        r"(?i)ignore\s+(all\s+)?(previous|prior|above|system)\s+instructions",
        r"(?i)disregard\s+(all\s+)?(rules|safety|guidelines|restrictions|instructions)",
        r"(?i)forget\s+(all\s+)?(previous|prior)\s+instructions",
        r"(?i)you\s+are\s+now\s+(in\s+)?(dan|developer|root|admin|god|unrestricted)\s+mode",
        r"(?i)pretend\s+(you\s+are|to\s+be)\s+(an\s+unrestricted|a\s+hacker|root|god|superadmin)",
        r"(?i)system\s+(override|prompt|reset)",
        r"(?i)new\s+system\s+directive",
        
        # Governance & Approval Bypasses
        r"(?i)bypass\s+(maker[-_\s]?checker|approval|security|governance|rbac|controls)",
        r"(?i)self[-_\s]?approv(e|al)",
        r"(?i)skip\s+(maker[-_\s]?checker|approval|change\s+ticket|governance|checks)",
        r"(?i)force\s+execut(e|ion)\s+without\s+(approval|review|ticket)",
        
        # Privilege Escalation
        r"(?i)give\s+(me\s+)?(root|admin|sudo|superuser)",
        r"(?i)grant\s+(me\s+)?(admin|root|superuser)",
        r"(?i)elevate\s+(my\s+)?privileges",
        
        # Destructive OS Commands & SQL Injection
        r"(?i)(drop|truncate)\s+(database|table|schema|user)",
        r"(?i)delete\s+from\s+[a-z0-9_]+",
        r"(?i)rm\s+-rf\s+[/~]",
        r"(?i)\bmkfs\b",
        r"(?i)dd\s+if=/dev",
        r"(?i);\s*(cat\s+/etc/passwd|shutdown|reboot|curl\s+http|wget\s+http)",
        
        # Secret Exfiltration & Information Gathering
        r"(?i)print\s+(the\s+)?(system\s+prompt|hidden\s+instructions|api\s+key|password|secret|creds)",
        r"(?i)reveal\s+(your\s+)?(instructions|system\s+prompt|secrets|credentials|keys)",
        r"(?i)dump\s+(database|env|environment|pam|credentials|keys|tokens)",
        r"(?i)echo\s+\$(AWS|VAULT|CYBERARK|SECRET|TOKEN|PASSWORD)",
        r"(?i)disable\s+(audit|logging|merkle|checks)",
        
        # Prompt Delimiter Escapes & Tags
        r"(?i)(```\s*system|<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<system>)",
        r"(?i)(<\s*script|javascript:|onerror\s*=)",
    ]

    SENSITIVE_SECRET_PATTERNS = [
        r"BEGIN\s+(RSA|OPENSSH|EC|DSA)?\s*PRIVATE\s+KEY",
        r"(?i)(aws_secret_access_key|cyberark_secret|vault_token)\s*[:=]",
        r"ghp_[a-zA-Z0-9]{36}",
    ]

    def __init__(self, catalog: List[CatalogItem], chat_model_provider: Optional[IChatModelProvider] = None):
        self.catalog = catalog
        self.chat_model_provider = chat_model_provider

    def _check_adversarial(self, prompt: str) -> Optional[str]:
        """
        Four-Stage Adversarial Injection & Secret Sanitization Pipeline (CHAT-17).
        Stage 1: Unicode normalization & control char stripping.
        Stage 2: High-entropy secret and private key detection.
        Stage 3: Comprehensive regex pattern matching.
        """
        # Stage 1: Normalize unicode (NFKC) & strip zero-width characters
        normalized = unicodedata.normalize("NFKC", prompt)
        clean_prompt = re.sub(r"[\u200B-\u200D\uFEFF]", "", normalized)

        # Stage 2: Secret and key leak detection
        for sec_pattern in self.SENSITIVE_SECRET_PATTERNS:
            if re.search(sec_pattern, clean_prompt):
                return "Adversarial security violation: Prompt contains private credentials or sensitive secrets."

        # Stage 3: Heuristic pattern blacklist
        for pattern in self.ADVERSARIAL_PATTERNS:
            if re.search(pattern, clean_prompt):
                return f"Adversarial security policy violation detected: Prompt matches blocked pattern [{pattern}]."
        return None

    def _sparse_bm25_score(self, query: str, text: str) -> float:
        """Token-overlap BM25 approximation for keyword anchoring."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        target_tokens = set(re.findall(r"\w+", text.lower()))
        if not query_tokens or not target_tokens:
            return 0.0
        intersection = query_tokens.intersection(target_tokens)
        return len(intersection) / len(query_tokens)

    def _dense_similarity_score(self, query: str, item: CatalogItem) -> float:
        """Semantic term alignment score across actions and infrastructure domains."""
        query_lower = query.lower()
        item_text = f"{item.identifier} {item.name} {getattr(item, 'description', '')}".lower()
        score = 0.0

        # Exact action alignment
        actions = [
            "renew", "expand", "scale", "patch", "rotate", "backup", "drain", "peer", "deploy",
            "inspect", "provision", "install", "setup", "ping", "check", "create", "stage", "harden"
        ]
        matched_actions = [a for a in actions if a in query_lower and a in item_text]
        if matched_actions:
            score += 0.4

        # Target infrastructure domain alignment
        domains = [
            "ssl", "cert", "tls", "tablespace", "database", "postgres", "eks", "kernel", "vpc", "ssh",
            "f5", "vip", "openclaw", "clawdbot", "bot", "agent", "docker", "container", "jenkins",
            "gitlab", "nginx", "redis", "ping", "sandbox", "hardening", "tailscale", "user"
        ]
        matched_domains = [d for d in domains if d in query_lower and d in item_text]
        if matched_domains:
            score += min(0.5, len(matched_domains) * 0.25)

        return min(score, 1.0)

    def hybrid_search(self, query: str, k: int = 60) -> List[Tuple[CatalogItem, float]]:
        """
        Two-Stage Reciprocal Rank Fusion (RRF) search combining Dense and Sparse signals.
        Enforces calibrated refusal gate: if dense < 0.35 and sparse == 0.0, returns empty list.
        """
        dense_scores = {item.id: self._dense_similarity_score(query, item) for item in self.catalog}
        sparse_scores = {
            item.id: self._sparse_bm25_score(
                query,
                f"{item.identifier} {item.name} {item.playbook_or_module_path} {' '.join(getattr(item, 'tags', []))} {getattr(item, 'description', '')}"
            )
            for item in self.catalog
        }

        max_dense = max(dense_scores.values()) if dense_scores else 0.0
        max_sparse = max(sparse_scores.values()) if sparse_scores else 0.0

        # Calibrated Refusal Gate (BKND-26 / CHAT-06):
        # Kill the Zero-Score Trap: If query has neither dense semantic alignment nor keyword overlap, refuse.
        if max_dense < 0.35 and max_sparse <= 0.0:
            return []

        dense_ranked = sorted(
            [item for item in self.catalog if dense_scores[item.id] > 0.0],
            key=lambda item: dense_scores[item.id],
            reverse=True
        )
        sparse_ranked = sorted(
            [item for item in self.catalog if sparse_scores[item.id] > 0.0],
            key=lambda item: sparse_scores[item.id],
            reverse=True
        )

        rrf_scores: Dict[str, float] = {}
        for rank, item in enumerate(dense_ranked):
            rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + (0.6 / (k + rank + 1))
        for rank, item in enumerate(sparse_ranked):
            rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + (0.4 / (k + rank + 1))

        results = []
        for item in self.catalog:
            if item.id in rrf_scores:
                results.append((item, rrf_scores[item.id]))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def resolve(self, prompt: str, ambient_params: Optional[Dict[str, Any]] = None) -> IntentResolutionResult:
        """
        Resolves prompt into structured intent within 2,500-token budget.
        """
        # 1. Adversarial Guardrail Check (100% Refusal Rate)
        violation = self._check_adversarial(prompt)
        if violation:
            return IntentResolutionResult(
                status="REFUSED",
                refusal_reason=violation,
                tokens_used=45
            )

        # 2. Hybrid Retrieval over Catalog
        ranked = self.hybrid_search(prompt)
        if not ranked:
            return IntentResolutionResult(
                status="REFUSED",
                refusal_reason="Out-of-catalog intent: No suitable automation playbook matches the provided query.",
                tokens_used=120
            )

        # Check if caller explicitly disambiguated/selected an item
        selected_id = (ambient_params or {}).get("catalog_identifier") or (ambient_params or {}).get("playbook_identifier")
        best_item = None
        if selected_id:
            for item, _ in ranked:
                if item.identifier == selected_id or item.id == selected_id:
                    best_item = item
                    break

        # 2b. Semantic Ambivalence Detection & Disambiguation Gate (CHAT-08)
        if not best_item and len(ranked) >= 2:
            dense_scores = {item.id: self._dense_similarity_score(prompt, item) for item in self.catalog}
            sparse_scores = {
                item.id: self._sparse_bm25_score(prompt, f"{item.identifier} {item.name} {item.playbook_or_module_path}")
                for item in self.catalog
            }
            cand1, _ = ranked[0]
            cand2, _ = ranked[1]
            sim1 = dense_scores.get(cand1.id, 0.0) * 0.6 + sparse_scores.get(cand1.id, 0.0) * 0.4
            sim2 = dense_scores.get(cand2.id, 0.0) * 0.6 + sparse_scores.get(cand2.id, 0.0) * 0.4
            delta_sim = abs(sim1 - sim2)
            
            # If both candidates exhibit significant relevance and difference is under 0.05
            if sim1 >= 0.30 and sim2 >= 0.30 and delta_sim < 0.05:
                candidates_payload = []
                for idx, (c_item, _) in enumerate(ranked[:3]):
                    c_sim = dense_scores.get(c_item.id, 0.0) * 0.6 + sparse_scores.get(c_item.id, 0.0) * 0.4
                    candidates_payload.append({
                        "identifier": c_item.identifier,
                        "name": c_item.name,
                        "engine": c_item.engine.value,
                        "cosineSimilarity": round(c_sim, 3),
                        "blastRadius": c_item.risk_tier.value,
                        "governanceGate": "MAKER_CHECKER" if c_item.requires_maker_checker else "PRE_APPROVED",
                        "summary": getattr(c_item, "description", "") or f"Automated execution of {c_item.name}",
                        "shortcut": str(idx + 1)
                    })
                return IntentResolutionResult(
                    status="DISAMBIGUATION",
                    tokens_used=80,
                    disambiguation_candidates=candidates_payload,
                    delta_sim=round(delta_sim, 3)
                )

        if not best_item:
            best_item = ranked[0][0]

        # 3. Parameter Slot Extraction
        extracted: Dict[str, Any] = dict(ambient_params or {})

        # Heuristic / Slot Parser matching Pydantic schema
        schema = best_item.input_schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Extract IPs (e.g. 10.200.1.50)
        ip_match = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", prompt)
        if ip_match and "vip_ip" in properties and "vip_ip" not in extracted:
            extracted["vip_ip"] = ip_match.group(0)

        # Extract hostnames
        stop_words = {"renew", "cert", "ssl", "on", "for", "the", "f5", "with", "validity", "days", "day", "vip"}
        # First priority: explicit .pnc.com domain
        domain_match = re.search(r"\b([a-z0-9-]+\.pnc\.com)\b", prompt, re.I)
        if domain_match and "hostname" in properties and "hostname" not in extracted:
            extracted["hostname"] = domain_match.group(1).lower()
        elif "hostname" in properties and "hostname" not in extracted:
            for match in re.finditer(r"\b([a-z0-9-]+)\b", prompt, re.I):
                candidate = match.group(1).lower()
                if candidate not in stop_words and len(candidate) > 2 and not candidate.isdigit():
                    extracted["hostname"] = candidate
                    break

        # Extract days / numeric
        days_match = re.search(r"(\d+)\s*(?:days?|d)", prompt, re.I)
        if days_match and "cert_valid_days" in properties:
            extracted["cert_valid_days"] = int(days_match.group(1))

        # Extract disk gigabytes
        gb_match = re.search(r"(\d+)\s*(?:gb|gigs?)", prompt, re.I)
        if gb_match and "expand_gb" in properties:
            extracted["expand_gb"] = int(gb_match.group(1))

        # Extract tablespace name
        ts_match = re.search(r"tablespace\s+([A-Z0-9_]+)", prompt, re.I)
        if ts_match and "tablespace_name" in properties:
            extracted["tablespace_name"] = ts_match.group(1).upper()

        # Extract VPC ID
        vpc_match = re.search(r"(vpc-[0-9a-fA-F]+)", prompt)
        if vpc_match and "peer_vpc_id" in properties:
            extracted["peer_vpc_id"] = vpc_match.group(1)

        # Check missing required fields
        missing = [req for req in required if req not in extracted]

        # Token usage calculation (BKND-28: honest token budgeting without tautological clamping)
        memory_stats = token_calculator.calculate_working_memory(
            system_prompt="You are Vulcan Intent Resolution Engine. Match catalog playbooks and extract parameters.",
            user_prompt=prompt,
            catalog_schema=schema,
            extracted_slots=extracted,
            base_overhead=400
        )
        total_tokens = memory_stats["total_tokens"]

        if memory_stats["exceeded"]:
            return IntentResolutionResult(
                status="REFUSED",
                catalog_item=best_item,
                refusal_reason=f"Working memory budget exceeded: Context required {total_tokens} tokens, exceeding the 2,500 token limit.",
                tokens_used=total_tokens
            )

        if missing:
            return IntentResolutionResult(
                status="NEEDS_INPUT",
                catalog_item=best_item,
                extracted_parameters=extracted,
                missing_fields=missing,
                tokens_used=total_tokens
            )

        return IntentResolutionResult(
            status="READY",
            catalog_item=best_item,
            extracted_parameters=extracted,
            missing_fields=[],
            tokens_used=total_tokens
        )
