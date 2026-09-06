#!/usr/bin/env python3
"""
Project Vulcan: Registry Crawler & Candidate Catalog Seeder (D7.3)
Crawls public Terraform Registry and Ansible Galaxy APIs, normalizes schemas,
quarantines into CANDIDATE status, generates deterministic 1536-dim embeddings,
and caches corpus to data/corpus/ for benchmarking and pgvector ingestion.
"""
import argparse
import asyncio
import json
import logging
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.adapters.postgres_catalog_repository import compute_hash_embedding
from app.adapters.registry_crawler import RegistryCrawlerAgent
from app.domain.entities import CatalogItem, CurationStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vulcan.crawl_registries")

CORPUS_DIR = BASE_DIR / "data" / "corpus"


def synthesize_synthetic_candidates(base_items: List[CatalogItem], target_count: int) -> List[CatalogItem]:
    """
    Synthesizes candidate items from base patterns to reach benchmark corpus sizes (1k, 5k, 10k).
    Maintains realistic banking infrastructure taxonomy (AWS, Azure, GCP, K8s, Vault, Postgres, F5).
    """
    cloud_providers = ["aws", "azure", "gcp", "k8s", "vmware", "oci"]
    services = ["vpc", "subnet", "security-group", "rds", "aurora", "s3", "iam", "eks", "gke", "aks", "redis", "kafka", "alb", "nlb", "ingress", "cert-manager", "vault", "consul", "istio", "postgres"]
    environments = ["prod", "uat", "dev", "stage", "infra", "edge", "core"]
    actions = ["deploy", "provision", "scale", "backup", "restore", "harden", "rotate", "audit", "patch", "isolate"]

    synthetic: List[CatalogItem] = list(base_items)
    idx = len(synthetic)

    import hashlib
    while len(synthetic) < target_count:
        cp = cloud_providers[idx % len(cloud_providers)]
        svc = services[(idx // len(cloud_providers)) % len(services)]
        env = environments[(idx // (len(cloud_providers) * len(services))) % len(environments)]
        act = actions[(idx // (len(cloud_providers) * len(services) * len(environments))) % len(actions)]

        ident = f"candidate.{cp}.{svc}-{act}-{idx}".lower()
        name = f"[Candidate] {cp.upper()} {svc.title()} {act.title()} ({env.upper()})"
        desc = f"Enterprise candidate automation module for {act} of {cp} {svc} in {env} tier."
        sha = hashlib.sha1(f"synth-{ident}-{idx}".encode()).hexdigest()

        item = CatalogItem(
            id=f"synth-{idx:05d}",
            identifier=ident,
            name=name,
            engine=base_items[idx % len(base_items)].engine if base_items else CatalogItem.__dataclass_fields__["engine"].default,
            git_repo=f"https://github.com/pnc-candidate/{cp}-{svc}-{act}",
            git_commit_sha=sha,
            playbook_or_module_path=f"modules/{cp}_{svc}_{act}",
            risk_tier=base_items[idx % len(base_items)].risk_tier if base_items else CatalogItem.__dataclass_fields__["risk_tier"].default,
            requires_maker_checker=True,
            requires_chg=True,
            input_schema={
                "type": "object",
                "properties": {
                    "cluster_name": {"type": "string", "has_default": False},
                    "replicas": {"type": "integer", "has_default": True, "suggested_default": 3},
                    "enabled": {"type": "boolean", "has_default": True, "suggested_default": True}
                }
            },
            category="infrastructure",
            description=desc,
            tags=[cp, svc, act, env, "candidate", "synthetic"],
            curation_status=CurationStatus.CANDIDATE,
            provenance={
                "source_registry": "synthetic_corpus",
                "synthetic": True,
                "license": "Apache-2.0",
                "license_compliant": True,
            }
        )
        synthetic.append(item)
        idx += 1

    return synthetic


async def main():
    parser = argparse.ArgumentParser(description="Vulcan Registry Crawler & Corpus Generator")
    parser.add_argument("--tf-count", type=int, default=30, help="Number of Terraform modules to crawl")
    parser.add_argument("--galaxy-count", type=int, default=30, help="Number of Ansible Galaxy roles to crawl")
    parser.add_argument("--target-size", type=int, default=1000, help="Target corpus size for benchmark")
    parser.add_argument("--seed-db", action="store_true", help="Seed results directly into PostgreSQL pgvector")
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL connection string")
    args = parser.parse_args()

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Initializing RegistryCrawlerAgent...")
    agent = RegistryCrawlerAgent()

    logger.info("Crawling public registries (TF: %d, Galaxy: %d)...", args.tf_count, args.galaxy_count)
    crawled = await agent.crawl_registries(tf_count=args.tf_count, galaxy_count=args.galaxy_count)
    logger.info("Successfully crawled %d public candidates from upstream registries.", len(crawled))

    if not crawled:
        # Load local candidate store if offline
        crawled = list(agent.store._candidates.values())
        logger.info("Loaded %d candidates from local candidate store.", len(crawled))

    # Scale to target size
    full_corpus = synthesize_synthetic_candidates(crawled, max(args.target_size, len(crawled)))
    logger.info("Synthesized target corpus of %d candidates.", len(full_corpus))

    # Export corpus to JSON
    corpus_file = CORPUS_DIR / f"candidates_{len(full_corpus)}.json"
    serializable = []
    for item in full_corpus:
        text = f"{item.name} {item.description} {item.identifier} {' '.join(item.tags)}"
        emb = compute_hash_embedding(text)
        serializable.append({
            "id": item.id,
            "identifier": item.identifier,
            "name": item.name,
            "engine": item.engine.value if hasattr(item.engine, "value") else str(item.engine),
            "git_repo": item.git_repo,
            "git_commit_sha": item.git_commit_sha,
            "playbook_or_module_path": item.playbook_or_module_path,
            "risk_tier": item.risk_tier.value if hasattr(item.risk_tier, "value") else str(item.risk_tier),
            "requires_maker_checker": item.requires_maker_checker,
            "requires_chg": item.requires_chg,
            "input_schema": item.input_schema,
            "rollback_path": item.rollback_path,
            "category": item.category,
            "description": item.description,
            "tags": item.tags,
            "curation_status": item.curation_status.value if hasattr(item.curation_status, "value") else str(item.curation_status),
            "provenance": item.provenance,
            "embedding": emb,
        })

    with open(corpus_file, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    logger.info("Cached corpus of %d candidates to %s", len(full_corpus), corpus_file)

    if args.seed_db:
        from app.adapters.postgres_catalog_repository import PostgresCatalogRepository
        logger.info("Seeding corpus into PostgreSQL pgvector...")
        pg_repo = PostgresCatalogRepository(db_url=args.db_url)
        inserted = 0
        for data in serializable:
            item = CatalogItem(
                id=data["id"],
                identifier=data["identifier"],
                name=data["name"],
                engine=data["engine"],
                git_repo=data["git_repo"],
                git_commit_sha=data["git_commit_sha"],
                playbook_or_module_path=data["playbook_or_module_path"],
                risk_tier=data["risk_tier"],
                requires_maker_checker=data["requires_maker_checker"],
                requires_chg=data["requires_chg"],
                input_schema=data["input_schema"],
                rollback_path=data["rollback_path"],
                category=data["category"],
                description=data["description"],
                tags=data["tags"],
                curation_status=CurationStatus(data["curation_status"]),
                provenance=data["provenance"],
            )
            pg_repo.save(item, embedding=data["embedding"])
            inserted += 1
            if inserted % 200 == 0:
                logger.info("Seeded %d / %d items into PostgreSQL...", inserted, len(serializable))
        logger.info("Seeding complete: %d total catalog items in PostgreSQL.", pg_repo.count())


if __name__ == "__main__":
    asyncio.run(main())
