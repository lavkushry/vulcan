"""
Project Vulcan: Ansible Galaxy Ingestion & Schema Transformation Adapter
Fetches community roles and collections from public Ansible Galaxy REST APIs (v1 & v3),
transforms records into immutable Vulcan CatalogItem domain entities, and seeds
both in-memory catalogs and persistent repositories for scale benchmarking.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.domain.entities import CatalogItem, ExecutionEngineType, RiskTier

logger = logging.getLogger("vulcan.galaxy_ingestion")

GALAXY_V1_ROLES_URL = "https://galaxy.ansible.com/api/v1/roles/"
GALAXY_V3_COLLECTIONS_URL = "https://galaxy.ansible.com/api/v3/plugin/ansible/content/published/collections/index/"


def infer_category(name: str, description: str, tags: List[str]) -> str:
    """Classify playbook category from metadata semantics."""
    corpus = f"{name} {description} {' '.join(tags)}".lower()
    if any(k in corpus for k in ["postgres", "oracle", "mysql", "database", "redis", "mongo", "db", "sql"]):
        return "database"
    if any(k in corpus for k in ["aws", "azure", "gcp", "cloud", "vpc", "s3", "ec2"]):
        return "cloud"
    if any(k in corpus for k in ["k8s", "kubernetes", "openshift", "containerd", "pod", "helm"]):
        return "kubernetes"
    if any(k in corpus for k in ["f5", "cisco", "switch", "router", "dns", "haproxy", "network", "firewall", "vpn", "bgp"]):
        return "network"
    if any(k in corpus for k in ["security", "cis", "hardening", "vault", "audit", "compliance", "ssh", "ssl", "cert"]):
        return "security"
    if any(k in corpus for k in ["patch", "kernel", "rhel", "ubuntu", "reboot", "sysops", "systemd", "linux"]):
        return "os_patching"
    return "infrastructure"


def infer_risk_tier(category: str, tags: List[str]) -> RiskTier:
    """Infer risk tier and governance requirements."""
    tag_str = " ".join(tags).lower()
    if category in ("database", "security") or any(k in tag_str for k in ["prod", "production", "kernel", "critical", "root"]):
        return RiskTier.HIGH
    if category in ("network", "kubernetes", "cloud") or any(k in tag_str for k in ["service", "deploy", "restart", "upgrade"]):
        return RiskTier.MEDIUM
    return RiskTier.LOW


def ensure_valid_sha(candidate: Optional[str], seed_key: str) -> str:
    """Enforce strict 40-character hex commit SHA invariant."""
    if candidate and re.match(r"^[0-9a-f]{40}$", str(candidate).lower()):
        return str(candidate).lower()
    # Deterministic SHA-1 fallback
    return hashlib.sha1(seed_key.encode("utf-8")).hexdigest()


class GalaxyApiClient:
    """Async client with rate-limiting and backoff for Ansible Galaxy public APIs."""

    def __init__(self, timeout: float = 15.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    def transform_role_record(self, role: Dict[str, Any]) -> CatalogItem:
        """Transforms a Galaxy v1 role record to Vulcan CatalogItem."""
        namespace = role.get("github_user") or role.get("username") or "community"
        name = role.get("name", "unnamed-role")
        identifier = f"galaxy.{namespace}.{name}".lower().replace("_", "-")
        display_name = f"{namespace.capitalize()} {name.replace('_', ' ').replace('-', ' ').title()}"
        description = role.get("description") or f"Ansible Galaxy community role: {namespace}.{name}"
        
        summary = role.get("summary_fields", {})
        tags = summary.get("tags", [])
        category = infer_category(name, description, tags)
        risk = infer_risk_tier(category, tags)
        
        git_user = role.get("github_user") or namespace
        git_repo_name = role.get("github_repo") or f"ansible-role-{name}"
        git_repo = f"https://github.com/{git_user}/{git_repo_name}"
        commit_sha = ensure_valid_sha(role.get("commit"), f"galaxy-role-{identifier}")

        schema = {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "sandbox", "description": "Target hostname in inventory"},
                "check_mode": {"type": "boolean", "default": False, "description": "Execute in dry-run mode"},
            }
        }

        return CatalogItem(
            id=f"cat-galaxy-{hashlib.md5(identifier.encode()).hexdigest()[:8]}",
            identifier=identifier,
            name=display_name,
            engine=ExecutionEngineType.ANSIBLE,
            git_repo=git_repo,
            git_commit_sha=commit_sha,
            playbook_or_module_path=f"ansible/roles/{namespace}.{name}",
            risk_tier=risk,
            requires_maker_checker=(risk == RiskTier.HIGH),
            requires_chg=(risk == RiskTier.HIGH),
            input_schema=schema,
            category=category,
            description=description[:250],
            tags=list(set(tags + [namespace, name, category, "galaxy"]))
        )

    def transform_collection_record(self, col: Dict[str, Any]) -> CatalogItem:
        """Transforms a Galaxy v3 collection record to Vulcan CatalogItem."""
        namespace = col.get("namespace", "community")
        name = col.get("name", "unnamed-collection")
        identifier = f"galaxy.{namespace}.{name}".lower().replace("_", "-")
        display_name = f"{namespace.capitalize()} {name.replace('_', ' ').replace('-', ' ').title()} Collection"
        description = f"Ansible Galaxy published collection: {namespace}.{name}"
        
        tags = [namespace, name, "collection"]
        category = infer_category(name, description, tags)
        risk = infer_risk_tier(category, tags)
        commit_sha = ensure_valid_sha(None, f"galaxy-collection-{identifier}")

        schema = {
            "type": "object",
            "required": ["target_host"],
            "properties": {
                "target_host": {"type": "string", "default": "sandbox", "description": "Target inventory host"},
            }
        }

        return CatalogItem(
            id=f"cat-galaxy-{hashlib.md5(identifier.encode()).hexdigest()[:8]}",
            identifier=identifier,
            name=display_name,
            engine=ExecutionEngineType.ANSIBLE,
            git_repo=f"galaxy://{namespace}/{name}",
            git_commit_sha=commit_sha,
            playbook_or_module_path=f"ansible/collections/{namespace}.{name}",
            risk_tier=risk,
            requires_maker_checker=(risk == RiskTier.HIGH),
            requires_chg=(risk == RiskTier.HIGH),
            input_schema=schema,
            category=category,
            description=description,
            tags=tags
        )

    async def fetch_roles_page(self, client: httpx.AsyncClient, page: int = 1, page_size: int = 100) -> List[Dict[str, Any]]:
        """Fetch one page of Galaxy roles."""
        url = f"{GALAXY_V1_ROLES_URL}?page={page}&page_size={page_size}"
        for attempt in range(self.max_retries):
            try:
                res = await client.get(url, timeout=self.timeout)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("results", [])
                elif res.status_code in (429, 502, 503):
                    await asyncio.sleep(1.0 * (attempt + 1))
            except Exception as e:
                logger.warning(f"Error fetching Galaxy roles page {page}: {e}")
                await asyncio.sleep(1.0 * (attempt + 1))
        return []

    async def ingest_roles(self, count: int = 1000) -> List[CatalogItem]:
        """Ingests N roles from Ansible Galaxy concurrently."""
        items: List[CatalogItem] = []
        page_size = 100
        total_pages = (count + page_size - 1) // page_size

        headers = {"User-Agent": "Project-Vulcan-Control-Plane/1.0 (Scale Benchmark Ingester)"}
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            # Batch fetch in chunks of 5 pages to respect API rates
            chunk_size = 5
            for chunk_start in range(1, total_pages + 1, chunk_size):
                chunk_pages = list(range(chunk_start, min(chunk_start + chunk_size, total_pages + 1)))
                tasks = [self.fetch_roles_page(client, p, page_size) for p in chunk_pages]
                results = await asyncio.gather(*tasks)
                for page_results in results:
                    for r in page_results:
                        try:
                            item = self.transform_role_record(r)
                            items.append(item)
                            if len(items) >= count:
                                return items
                        except Exception as ex:
                            logger.debug(f"Skipping malformed role: {ex}")
                await asyncio.sleep(0.3)
        return items

    def synthesize_scale_catalog(self, base_items: List[CatalogItem], target_count: int = 10000) -> List[CatalogItem]:
        """
        Extrapolates real Galaxy items with enterprise namespaces (e.g. dev, uat, prod divisions)
        to form a realistic 10,000-item benchmark corpus with authentic distribution.
        """
        if len(base_items) >= target_count:
            return base_items[:target_count]

        extended = list(base_items)
        divisions = ["fintech", "payments", "retail", "cloud-sre", "secops", "data-eng", "core-banking", "platform", "infra", "observability"]
        environments = ["prod", "uat", "dev", "dr", "staging"]

        idx = 0
        while len(extended) < target_count:
            base = base_items[idx % len(base_items)]
            div = divisions[(idx // len(base_items)) % len(divisions)]
            env = environments[(idx // (len(base_items) * len(divisions))) % len(environments)]
            
            synth_id = f"cat-galaxy-synth-{len(extended):06d}"
            synth_ident = f"galaxy.{div}.{base.identifier.replace('galaxy.', '')}-{env}"
            synth_name = f"[{div.upper()}-{env.upper()}] {base.name}"
            
            synth_sha = hashlib.sha1(f"synth-{synth_ident}".encode()).hexdigest()
            tags = list(set(base.tags + [div, env, "synthesized"]))
            
            item = CatalogItem(
                id=synth_id,
                identifier=synth_ident,
                name=synth_name,
                engine=base.engine,
                git_repo=base.git_repo,
                git_commit_sha=synth_sha,
                playbook_or_module_path=base.playbook_or_module_path,
                risk_tier=base.risk_tier,
                requires_maker_checker=base.requires_maker_checker,
                requires_chg=base.requires_chg,
                input_schema=base.input_schema,
                category=base.category,
                description=f"{base.description} (Scoped for {div.upper()} {env.upper()})",
                tags=tags
            )
            extended.append(item)
            idx += 1

        return extended
