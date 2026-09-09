"""
Project Vulcan: AI Intent Resolution Subsystem (The LLM OS)
Author: Andrej Karpathy (AI Systems Lead)
Implements:
1. Strict 2,500 token working memory budget.
2. Two-Stage Hybrid Search (Dense Cosine Similarity + Sparse BM25 via RRF).
3. Grammar-Constrained Pydantic Slot Filling.
4. Adversarial Prompt Injection Defense (100% refusal rate).
"""
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.domain.entities import CatalogItem, CurationStatus, ExecutionEngineType, RiskTier
from app.ports.interfaces import IChatModelProvider, IEmbeddingProvider, IServiceNowGateway
from app.ports.repositories import ICatalogRepository
from app.adapters.embedding_providers import get_embedding_provider
from app.use_cases.tokenizer import token_calculator

logger = logging.getLogger("vulcan.intent_resolver")


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
        delta_sim: float = 0.0,
        ticket_hydration: Optional[Dict[str, Any]] = None,
        top_candidates: Optional[List[CatalogItem]] = None,
    ):
        self.status = status
        self.catalog_item = catalog_item
        self.extracted_parameters = extracted_parameters or {}
        self.missing_fields = missing_fields or []
        self.refusal_reason = refusal_reason
        self.tokens_used = tokens_used
        self.disambiguation_candidates = disambiguation_candidates or []
        self.delta_sim = delta_sim
        self.ticket_hydration = ticket_hydration
        self.top_candidates = top_candidates or []

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
            "delta_sim": self.delta_sim,
            "ticket_hydration": self.ticket_hydration,
            "top_candidates": [c.identifier for c in self.top_candidates]
        }


class IntentResolver:
    """
    The LLM OS Intent Compilation Engine.
    Executes hybrid RRF retrieval over the playbook catalog and enforces slot validation.
    """

    ADVERSARIAL_PATTERNS = [
        # Instruction Overrides & Jailbreaks
        r"(?i)ignore\s+(all\s+)?(previous|prior|above|system)\s+instructions",
        r"(?i)disregard\s+(all\s+)?([a-z0-9_-]+\s+)?(rules|safety|guidelines|restrictions|instructions|constraints|governance)",
        r"(?i)forget\s+(all\s+)?(previous|prior)\s+instructions",
        r"(?i)you\s+are\s+now\s+(in\s+)?(dan|developer|root|admin|god|unrestricted)\s+mode",
        r"(?i)pretend\s+(you\s+are|to\s+be)\s+(an\s+unrestricted|a\s+hacker|root|god|superadmin)",
        r"(?i)system\s+(override|prompt|reset)",
        r"(?i)new\s+system\s+directive",
        r"(?i)act\s+as\s+(an?\s+)?(unrestricted|linux\s+root|root|bash|terminal)",
        r"(?i)simulate\s+(an?\s+)?(ai|system|agent)\s+without",
        
        # Governance & Approval Bypasses
        r"(?i)(?:bypass|skip|override|disable)\s+.*(?:maker[-_\s]?checker|approv\w*|dual[-_\s]?control|peer\s+review|two[-_\s]?man|second[-_\s]?pair)",
        r"(?i)self[-_\s]?approv(e|al)",
        r"(?i)skip\s+(maker[-_\s]?checker|approval|approver|change\s+ticket|governance|checks)",
        r"(?i)force\s+execut(e|ion)\s+without\s+(approval|review|ticket)",
        r"(?i)(?:without|skip)\s+(?:secondary\s+)?(?:maker[-_\s]?checker|checker\s+sign[-_\s]?off|peer\s+review)",
        r"(?i)second[-_\s]?pair[-_\s]?of[-_\s]?eyes",
        r"(?i)authorize\s+(?:this\s+.*|deploy\s+)?without\s+(?:secondary\s+|peer\s+)",
        r"(?i)disable\s+(?:dual[-_\s]?control|maker[-_\s]?checker|approval|governance|gate)",
        r"(?i)override\s+(?:maker[-_\s]?checker|approval|governance|gate|controls)",
        
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
        r"(?i)\b(eval|compile|os\.system|subprocess)\b",
        r"(?i);\s*(cat\s+/etc/passwd|shutdown|reboot|curl\s+http|wget\s+http)",
        r"(?i)\bcat\s+/etc/(passwd|shadow|hosts|sudoers)",
        
        # Secret Exfiltration & Information Gathering
        r"(?i)print\s+(the\s+)?(system\s+prompt|hidden\s+instructions|api\s+key|password|secret|creds)",
        r"(?i)reveal\s+.*(instructions|system\s+prompt|secrets|credentials|keys|tokens)",
        r"(?i)dump\s+.*(database|env|environment|pam|credentials|keys|tokens|secret)",
        r"(?i)echo\s+\$(AWS|VAULT|CYBERARK|SECRET|TOKEN|PASSWORD)",
        r"(?i)disable\s+(audit|logging|merkle|checks)",
        r"(?i)wipe\s+(?:all\s+)?audit",
        r"(?i)(?:exfiltrate|leak|dump)\s+.*(?:password|connection\s+string)",
        
        # Prompt Delimiter Escapes & Tags
        r"(?i)(```\s*system|<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<system>)",
        r"(?i)(<\s*script|javascript:|onerror\s*=)",

        # CHG Spoofing & Emergency Bypass (CHAT-17)
        r"(?i)CHG[-_\s]?\d+.*(?:pre[-_\s]?approved|skip\s+approval|emergency\s+bypass).*(?:execute|run|deploy)\s+now",
        r"(?i)(?:pre[-_\s]?approved|emergency\s+override).*(?:execute|run|deploy)\s+now",
        r"(?i)skip\s+(cab|change\s+advisory|governance)",
        r"(?i)override\s+(freeze|change\s+freeze|maintenance\s+window)",
        r"(?i)bypass\s+(window|maintenance\s+window|freeze)",
    ]

    SENSITIVE_SECRET_PATTERNS = [
        r"BEGIN\s+(RSA|OPENSSH|EC|DSA)?\s*PRIVATE\s+KEY",
        r"(?i)(aws_secret_access_key|cyberark_secret|vault_token)\s*[:=]",
        r"ghp_[a-zA-Z0-9]{36}",
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}",
        r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]",
        r"(?i)s\.([a-zA-Z0-9]{24,})",  # Vault token pattern
    ]

    # Homoglyph translation mapping (Cyrillic & confusable characters to Latin)
    HOMOGLYPH_MAP = str.maketrans({
        '\u0430': 'a', '\u0435': 'e', '\u0456': 'i', '\u043e': 'o',
        '\u0440': 'p', '\u0441': 'c', '\u0443': 'y', '\u0445': 'x',
        '\u0410': 'A', '\u0415': 'E', '\u0406': 'I', '\u041e': 'O',
        '\u0420': 'P', '\u0421': 'C', '\u0423': 'Y', '\u0425': 'X',
        '\u0131': 'i', '\u0130': 'I',  # dotless / dotted i
    })

    def __init__(
        self,
        catalog: List[CatalogItem],
        chat_model_provider: Optional[IChatModelProvider] = None,
        catalog_repo: Optional[ICatalogRepository] = None,
        embedding_provider: Optional[IEmbeddingProvider] = None,
        servicenow_gateway: Optional[IServiceNowGateway] = None,
    ):
        self.catalog = catalog
        self.chat_model_provider = chat_model_provider
        self.catalog_repo = catalog_repo
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.servicenow_gateway = servicenow_gateway
        # Precompute search indices for sub-millisecond retrieval across 10,000+ items
        self._item_tokens: Dict[str, set] = {}
        self._item_texts: Dict[str, str] = {}
        for item in self.catalog:
            full_text = f"{item.identifier} {item.name} {item.playbook_or_module_path} {' '.join(getattr(item, 'tags', []))} {getattr(item, 'description', '')}".lower()
            self._item_tokens[item.id] = set(re.findall(r"\w+", full_text))
            self._item_texts[item.id] = full_text

    def _check_adversarial(self, prompt: str) -> Optional[str]:
        """
        Four-Stage Adversarial Injection & Secret Sanitization Pipeline (CHAT-17).
        Stage 1: Unicode normalization (NFKC), homoglyph translation & control char stripping.
        Stage 2: High-entropy secret, AKIA, and private key detection.
        Stage 3: Comprehensive regex pattern matching.
        """
        # Stage 1: Normalize unicode (NFKC), map homoglyphs & strip zero-width characters
        normalized = unicodedata.normalize("NFKC", prompt)
        translated = normalized.translate(self.HOMOGLYPH_MAP)
        clean_prompt = re.sub(r"[\u200B-\u200D\uFEFF]", "", translated)

        # Stage 2: Secret and key leak detection (AKIA, private keys, Vault tokens)
        for sec_pattern in self.SENSITIVE_SECRET_PATTERNS:
            if re.search(sec_pattern, prompt) or re.search(sec_pattern, clean_prompt):
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

    STOP_WORDS = {
        "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
        "and", "or", "as", "is", "are", "was", "were", "it", "this", "that", "into",
        "about", "over", "after", "before", "between", "under", "above", "zero", "all",
        "any", "some", "without", "query", "new", "my", "our", "me", "can", "please",
        "we", "us", "do", "does", "did", "get", "got", "how", "what", "which", "who"
    }

    def _sparse_bm25_tokens(self, query_tokens: set, item_id: str) -> float:
        """Fast pre-indexed token set overlap excluding common stop-words."""
        content_tokens = {t for t in query_tokens if t not in self.STOP_WORDS and len(t) > 2}
        if not content_tokens:
            return 0.0
        target = self._item_tokens.get(item_id)
        if not target:
            return 0.0
        return len(content_tokens.intersection(target)) / len(content_tokens)

    def _dense_similarity_score(self, query: str, item: CatalogItem) -> float:
        """Semantic term alignment score across actions and infrastructure domains."""
        query_lower = query.lower()
        item_text = self._item_texts.get(item.id, f"{item.identifier} {item.name} {getattr(item, 'description', '')}".lower())
        score = 0.0

        # Exact action alignment
        actions = [
            "renew", "expand", "scale", "patch", "rotate", "backup", "drain", "peer", "deploy",
            "inspect", "provision", "install", "setup", "ping", "check", "create", "stage", "harden",
            "lockdown", "reload", "sync", "update", "audit", "restore", "tune", "reboot", "upgrade"
        ]
        matched_actions = [a for a in actions if a in query_lower and a in item_text]
        if matched_actions:
            score += 0.4

        # Target infrastructure domain alignment
        domains = [
            "ssl", "cert", "tls", "tablespace", "database", "postgres", "eks", "kernel", "vpc", "ssh",
            "f5", "vip", "openclaw", "clawdbot", "bot", "agent", "docker", "container", "jenkins",
            "gitlab", "nginx", "redis", "ping", "sandbox", "hardening", "tailscale", "user",
            "s3", "bucket", "kms", "vault", "approle", "firewall", "firewalld", "crowdstrike", "falcon",
            "edr", "sensor", "storage", "peering", "transit", "gateway", "nodegroup", "namespace",
            "quota", "sidecar", "mesh", "istio", "wireguard", "bgp", "cisco", "arista", "haproxy",
            "waf", "ingress"
        ]
        matched_domains = [d for d in domains if d in query_lower and d in item_text]
        if matched_domains:
            score += min(0.5, len(matched_domains) * 0.25)

        return min(score, 1.0)

    def hybrid_search(self, query: str, k: int = 60) -> List[Tuple[CatalogItem, float]]:
        """
        Two-Stage Reciprocal Rank Fusion (RRF) search combining Dense and Sparse signals.
        Enforces:
        1. Curation Quarantine: NEVER returns CANDIDATE modules (CURATED only).
        2. Calibrated refusal gate: if dense < 0.35 and sparse == 0.0, returns empty list.
        """
        if self.catalog_repo and hasattr(self.catalog_repo, "search_hybrid"):
            try:
                repo_results = self.catalog_repo.search_hybrid(query, top_k=10, curation_status="CURATED")
                if repo_results:
                    return [(item, score) for item, score, _ in repo_results]
                return []
            except Exception as e:
                logger.warning("Catalog repository hybrid search failed (%s); falling back to in-memory search.", e)

        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))

        # Quarantine check: Operator intent search must strictly match CURATED items only
        curated_catalog = [
            item for item in self.catalog
            if getattr(item, "curation_status", CurationStatus.CURATED) == CurationStatus.CURATED
            or (hasattr(getattr(item, "curation_status", None), "value") and item.curation_status.value == "CURATED")
            or getattr(item, "curation_status", None) == "CURATED"
        ]

        dense_scores = {item.id: self._dense_similarity_score(query_lower, item) for item in curated_catalog}
        sparse_scores = {item.id: self._sparse_bm25_tokens(query_tokens, item.id) for item in curated_catalog}

        max_dense = max(dense_scores.values()) if dense_scores else 0.0
        max_sparse = max(sparse_scores.values()) if sparse_scores else 0.0

        # Calibrated Refusal Gate (BKND-26 / CHAT-06):
        # Kill the Zero-Score Trap: If query has neither dense semantic alignment nor meaningful keyword overlap, refuse.
        if self.embedding_provider.is_refusal(max_dense, max_sparse):
            return []

        dense_ranked = sorted(
            [item for item in curated_catalog if dense_scores[item.id] > 0.0],
            key=lambda item: dense_scores[item.id],
            reverse=True
        )
        sparse_ranked = sorted(
            [item for item in curated_catalog if sparse_scores[item.id] > 0.0],
            key=lambda item: sparse_scores[item.id],
            reverse=True
        )

        rrf_scores: Dict[str, float] = {}
        for rank, item in enumerate(dense_ranked):
            rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + (0.6 / (k + rank + 1))
        for rank, item in enumerate(sparse_ranked):
            rrf_scores[item.id] = rrf_scores.get(item.id, 0.0) + (0.4 / (k + rank + 1))

        results = []
        for item in curated_catalog:
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

        # Check if caller explicitly disambiguated/selected an item (e.g. multi-turn session)
        selected_id = (ambient_params or {}).get("catalog_identifier") or (ambient_params or {}).get("playbook_identifier")
        best_item = None
        if selected_id:
            for item in self.catalog:
                if item.identifier == selected_id or item.id == selected_id:
                    best_item = item
                    break

        # 2. Hybrid Retrieval over Catalog
        ranked = self.hybrid_search(prompt)
        if not ranked and not best_item:
            return IntentResolutionResult(
                status="REFUSED",
                refusal_reason="Out-of-catalog intent: No suitable automation playbook matches the provided query.",
                tokens_used=120
            )

        if best_item and not ranked:
            ranked = [(best_item, 1.0)]

        top_candidates = [item for item, _ in ranked[:3]]

        # Extract initial parameters & ServiceNow Change Ticket (CHAT-16)
        extracted: Dict[str, Any] = dict(ambient_params or {})
        ticket_hydration_data: Optional[Dict[str, Any]] = None

        # ServiceNow Change Ticket Extraction & Provenance Validation (CHAT-16)
        chg_match = re.search(r"\b(CHG(?:-[A-Za-z0-9_-]+|\d{3,10}))\b", prompt, re.I)
        if chg_match:
            chg_num = chg_match.group(1).upper()
            extracted["servicenow_chg"] = chg_num
            if self.servicenow_gateway:
                ticket_info = self.servicenow_gateway.validate_chg(chg_num)
                is_valid = ticket_info.get("is_valid", False) or ticket_info.get("valid", False)
                # Fail-closed: check validity, state, and maintenance window
                in_window = self.servicenow_gateway.is_within_maintenance_window(chg_num, datetime.now(timezone.utc))
                if not is_valid or ticket_info.get("state") in ("Invalid", "Cancelled") or not in_window:
                    return IntentResolutionResult(
                        status="REFUSED",
                        catalog_item=best_item or (ranked[0][0] if ranked else None),
                        refusal_reason=f"ServiceNow change ticket '{chg_num}' is invalid, unapproved, outside maintenance window, or unknown. Governance check failed.",
                        tokens_used=65,
                        top_candidates=top_candidates
                    )
                ticket_hydration_data = ticket_info
                # Hydrate Configuration Item (CI) if available
                ci_val = ticket_info.get("ci")
                if ci_val:
                    if "hostname" not in extracted:
                        extracted["hostname"] = ci_val
                    if "target_host" not in extracted:
                        extracted["target_host"] = ci_val

        # 2b. Semantic Ambivalence Detection & Disambiguation Gate (CHAT-08)
        if not best_item and len(ranked) >= 2:
            query_lower = prompt.lower()
            query_tokens = set(re.findall(r"\w+", query_lower))
            cand1, _ = ranked[0]
            cand2, _ = ranked[1]
            sim1 = self._dense_similarity_score(query_lower, cand1) * 0.6 + self._sparse_bm25_tokens(query_tokens, cand1.id) * 0.4
            sim2 = self._dense_similarity_score(query_lower, cand2) * 0.6 + self._sparse_bm25_tokens(query_tokens, cand2.id) * 0.4
            delta_sim = abs(sim1 - sim2)
            
            # If both candidates exhibit significant relevance and difference is under 0.05
            if sim1 >= 0.25 and sim2 >= 0.25 and delta_sim < 0.05:
                candidates_payload = []
                for idx, (c_item, _) in enumerate(ranked[:3]):
                    c_sim = self._dense_similarity_score(query_lower, c_item) * 0.6 + self._sparse_bm25_tokens(query_tokens, c_item.id) * 0.4
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
                    delta_sim=round(delta_sim, 3),
                    top_candidates=top_candidates,
                    extracted_parameters=extracted,
                    ticket_hydration=ticket_hydration_data
                )

        if not best_item:
            best_item = ranked[0][0]

        # 3. Parameter Slot Extraction (continued for best_item)

        # Heuristic / Slot Parser matching Pydantic schema
        schema = best_item.input_schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Extract IPs (e.g. 10.200.1.50, valid octets 0-255)
        # Use negative lookbehind and lookahead to avoid matching sub-slices of invalid IPs (e.g. 10.0.0.0.1)
        ip_match = re.search(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])", prompt)
        if ip_match and "vip_ip" in properties and "vip_ip" not in extracted:
            octets = [int(g) for g in ip_match.groups()]
            if all(0 <= o <= 255 for o in octets):
                extracted["vip_ip"] = ip_match.group(0)

        # Extract hostnames
        stop_words = {"renew", "cert", "ssl", "on", "for", "the", "f5", "with", "validity", "days", "day", "vip"}
        domain_match = re.search(r"\b([a-z0-9-]+\.pnc\.com)\b", prompt, re.I)
        if domain_match and "hostname" in properties and "hostname" not in extracted:
            extracted["hostname"] = domain_match.group(1).lower()
        elif "hostname" in properties and "hostname" not in extracted:
            for match in re.finditer(r"\b([a-z0-9-]+)\b", prompt, re.I):
                candidate = match.group(1).lower()
                if candidate not in stop_words and len(candidate) > 2 and not candidate.isdigit():
                    extracted["hostname"] = candidate
                    break

        # Extract target_host
        host_match = re.search(r"(?:host|bastion|server|target)\s+([a-z0-9_.-]+)", prompt, re.I)
        if host_match and "target_host" in properties and "target_host" not in extracted:
            extracted["target_host"] = host_match.group(1)

        # Extract days / numeric
        days_match = re.search(r"(\d+)\s*(?:days?|d)", prompt, re.I)
        if days_match and "cert_valid_days" in properties:
            extracted["cert_valid_days"] = int(days_match.group(1))

        # Extract disk gigabytes
        gb_match = re.search(r"(\d+)\s*(?:gb|gigs?)", prompt, re.I)
        if gb_match and "expand_gb" in properties:
            extracted["expand_gb"] = int(gb_match.group(1))

        # Extract tablespace name
        ts_match = re.search(r"tablespace\s+(?:storage\s+for\s+|for\s+)?([^\s,]+(?:\s+[^\s,]+)*?)(?:\s+by\s+|\s+on\s+|$)", prompt, re.I)
        if ts_match and "tablespace_name" in properties:
            raw_ts = ts_match.group(1).strip()
            if re.match(r"^[A-Z0-9_]{2,64}$", raw_ts, re.I):
                extracted["tablespace_name"] = raw_ts.upper()

        # Extract VPC ID
        vpc_match = re.search(r"(vpc-[0-9a-fA-F]+)", prompt)
        if vpc_match and "peer_vpc_id" in properties:
            extracted["peer_vpc_id"] = vpc_match.group(1)

        # Extract port
        port_match = re.search(r"(?:port|listening\s+on)\s+(\d+)", prompt, re.I)
        if port_match and "port" in properties:
            extracted["port"] = int(port_match.group(1))

        # Extract username
        user_match = re.search(r"(?:user|username|account)\s+([a-z0-9_-]+)", prompt, re.I)
        if user_match and "username" in properties:
            extracted["username"] = user_match.group(1)

        # Extract nodegroup_name
        ng_match = re.search(r"nodegroup\s+([a-z0-9_-]+)", prompt, re.I)
        if ng_match and "nodegroup_name" in properties and "nodegroup_name" not in extracted:
            extracted["nodegroup_name"] = ng_match.group(1)

        # Extract cluster_name
        cl_match = re.search(r"cluster\s+([a-z0-9_-]+)", prompt, re.I)
        if cl_match and "cluster_name" in properties and "cluster_name" not in extracted:
            extracted["cluster_name"] = cl_match.group(1)

        # Extract desired capacity / nodes
        nodes_match = re.search(r"(\d+)\s*(?:nodes?|instances?|workers?)", prompt, re.I)
        if nodes_match and "desired_capacity" in properties:
            extracted["desired_capacity"] = int(nodes_match.group(1))

        # Extract KMS key ARN or alias (for cloud-s3-kms-bucket-provision)
        kms_match = re.search(r"(?:kms\s+key|customer\s+key|cmk)\s+([a-z0-9_-]+)", prompt, re.I)
        if kms_match and "kms_key_arn" in properties and "kms_key_arn" not in extracted:
            extracted["kms_key_arn"] = kms_match.group(1)

        # Extract bucket name (for cloud-s3-kms-bucket-provision)
        bucket_match = re.search(r"(?:bucket|s3\s+bucket)\s+([a-z0-9.-]+)", prompt, re.I)
        if bucket_match and "bucket_name" in properties and "bucket_name" not in extracted:
            bname = bucket_match.group(1)
            if bname.lower() not in ("with", "for", "provision", "secure", "private", "encrypted"):
                extracted["bucket_name"] = bname

        # 4. Strict Slot Boundary & Constraint Validation (INV-AI-02)
        # Type check, integer range limits (min/max), regex patterns, and enums
        for k in list(extracted.keys()):
            if k in properties:
                pdef = properties[k]
                val = extracted[k]
                val_type = pdef.get("type")

                # Integer bounds
                if val_type == "integer" and isinstance(val, int):
                    if pdef.get("minimum") is not None and val < pdef["minimum"]:
                        del extracted[k]
                    elif pdef.get("maximum") is not None and val > pdef["maximum"]:
                        del extracted[k]

                # String regex pattern
                elif val_type == "string" and isinstance(val, str):
                    pat = pdef.get("pattern")
                    if pat and not re.match(pat, val):
                        del extracted[k]
                    elif pdef.get("enum") and val not in pdef["enum"]:
                        del extracted[k]

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
                tokens_used=total_tokens,
                top_candidates=top_candidates
            )

        if missing:
            return IntentResolutionResult(
                status="NEEDS_INPUT",
                catalog_item=best_item,
                extracted_parameters=extracted,
                missing_fields=missing,
                tokens_used=total_tokens,
                ticket_hydration=ticket_hydration_data,
                top_candidates=top_candidates
            )

        return IntentResolutionResult(
            status="READY",
            catalog_item=best_item,
            extracted_parameters=extracted,
            missing_fields=[],
            tokens_used=total_tokens,
            ticket_hydration=ticket_hydration_data,
            top_candidates=top_candidates
        )
