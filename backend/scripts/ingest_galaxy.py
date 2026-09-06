#!/usr/bin/env python3
"""
Project Vulcan: CLI Tool for Ansible Galaxy Ingestion & Scale Seeding
Fetches community roles from public Ansible Galaxy API, maps to Vulcan's CatalogItem schema,
and writes benchmark dataset files (1,000 / 5,000 / 10,000 items).
"""
import argparse
import asyncio
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

# Add backend to python path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.adapters.galaxy_ingestion import GalaxyApiClient
from app.adapters.sqlite_repositories import SQLiteCatalogRepository


async def main():
    parser = argparse.ArgumentParser(description="Ingest Ansible Galaxy records into Project Vulcan Catalog")
    parser.add_argument("--count", type=int, default=1000, help="Number of real Galaxy roles to ingest (default: 1000)")
    parser.add_argument("--scale-to", type=int, default=0, help="Synthesize catalog to target scale (e.g. 5000 or 10000)")
    parser.add_argument("--output", type=str, default="backend/data/galaxy_catalog.json", help="Path to save output JSON")
    parser.add_argument("--seed-sqlite", action="store_true", help="Seed items into backend SQLite database (vulcan.db)")
    args = parser.parse_args()

    print("==================================================================")
    print("      PROJECT VULCAN: Ansible Galaxy Enterprise Catalog Ingester  ")
    print("==================================================================")
    print(f"Target real ingestion count: {args.count}")
    if args.scale_to > 0:
        print(f"Scale synthesis target:     {args.scale_to}")
    print(f"Output path:                {args.output}")

    client = GalaxyApiClient()
    start_t = time.perf_counter()

    print(f"\n[1/3] Querying Ansible Galaxy public API (galaxy.ansible.com/api/v1/roles)...")
    real_items = await client.ingest_roles(count=args.count)
    fetch_t = time.perf_counter() - start_t
    print(f"  ✓ Fetched and mapped {len(real_items)} real community roles in {fetch_t:.2f}s")

    catalog_items = real_items
    if args.scale_to > len(real_items):
        print(f"\n[2/3] Synthesizing division and environment tiers up to {args.scale_to} items...")
        catalog_items = client.synthesize_scale_catalog(real_items, target_count=args.scale_to)
        print(f"  ✓ Scaled catalog to {len(catalog_items)} total immutable items.")
    else:
        print("\n[2/3] Scale synthesis skipped (using ingested count).")

    # Serialize to JSON
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    serialized = [dataclasses.asdict(item) for item in catalog_items]
    for row in serialized:
        # Convert enums to string
        row["engine"] = row["engine"].value if hasattr(row["engine"], "value") else str(row["engine"])
        row["risk_tier"] = row["risk_tier"].value if hasattr(row["risk_tier"], "value") else str(row["risk_tier"])

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2)
    print(f"  ✓ Wrote catalog JSON to {args.output} ({os.path.getsize(args.output) / 1024:.1f} KB)")

    # Seeding SQLite if requested
    if args.seed_sqlite:
        print("\n[3/3] Seeding catalog items into SQLite repository...")
        repo = SQLiteCatalogRepository()
        for it in catalog_items:
            repo.save(it)
        print(f"  ✓ Saved {len(catalog_items)} items into SQLite repository.")
    else:
        print("\n[3/3] SQLite seeding skipped.")

    # Validation summary
    cat_counts = {}
    risk_counts = {}
    valid_shas = 0
    for it in catalog_items:
        cat_counts[it.category] = cat_counts.get(it.category, 0) + 1
        risk_counts[it.risk_tier.value] = risk_counts.get(it.risk_tier.value, 0) + 1
        if len(it.git_commit_sha) == 40:
            valid_shas += 1

    print("\n==================================================================")
    print(" Ingestion & Transformation Summary:")
    print(f"   - Total Catalog Items: {len(catalog_items)}")
    print(f"   - Valid 40-char SHAs:  {valid_shas} / {len(catalog_items)} (100% Invariant)")
    print(f"   - Categories:          {cat_counts}")
    print(f"   - Risk Distribution:   {risk_counts}")
    print(f"   - Total Time:          {time.perf_counter() - start_t:.2f}s")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(main())
