#!/usr/bin/env python3
"""
Project Vulcan: Software Bill of Materials (SBOM) Generator (INFRA-30)

Generates standards-compliant SPDX 2.3 JSON and CycloneDX 1.5 JSON SBOMs
for both Python backend dependencies and Node.js frontend dependencies.
Works hermetically without requiring third-party network access.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_backend_dependencies(repo_root: Path) -> List[Dict[str, Any]]:
    """Extract Python backend packages from requirements.txt and virtualenv metadata."""
    packages = []
    seen = set()

    req_file = repo_root / "backend" / "requirements.txt"
    direct_deps = set()
    req_packages = []
    if req_file.exists():
        for line in req_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract package name and version if specified
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[.*\])?(?:([><=~!]+)(.*))?$", line)
            if match:
                pkg_name = match.group(1)
                clean_ver = (match.group(3) or "latest").split(",")[0].strip()
                norm_name = pkg_name.lower().replace("_", "-")
                direct_deps.add(norm_name)
                req_packages.append((pkg_name, norm_name, clean_ver))

    # Try virtualenv metadata first for exact resolved versions and licenses
    venv_python = repo_root / "backend" / ".venv"
    dist_map = {}
    try:
        import importlib.metadata as meta
        # If sys.path doesn't include venv site-packages, add it
        if venv_python.exists():
            for p in (venv_python / "lib").glob("python*/site-packages"):
                if str(p) not in sys.path:
                    sys.path.insert(0, str(p))

        for dist in meta.distributions():
            name = dist.metadata.get("Name")
            if not name:
                continue
            norm_name = name.lower().replace("_", "-")
            version = dist.metadata.get("Version", "unknown")
            license_str = dist.metadata.get("License", "NOASSERTION")
            # If license is long text or unknown, simplify
            if license_str and (len(license_str) > 50 or "\n" in license_str):
                license_str = "Custom"
            dist_map[norm_name] = {
                "name": name,
                "version": version,
                "license": license_str or "NOASSERTION",
                "direct": norm_name in direct_deps,
            }
    except Exception:
        pass

    # Determine if dist_map covers direct_deps sufficiently (at least 50%)
    direct_covered = direct_deps.intersection(dist_map.keys())
    if dist_map and len(direct_covered) >= max(1, len(direct_deps) // 2):
        for norm_name, info in sorted(dist_map.items()):
            seen.add(norm_name)
            packages.append({
                "ecosystem": "pypi",
                "name": info["name"],
                "version": info["version"],
                "license": info["license"],
                "direct": info["direct"],
                "purl": f"pkg:pypi/{info['name'].lower()}@{info['version']}",
            })
    else:
        # Fallback or merge: parse requirements.txt directly so requirements are never missing
        for pkg_name, norm_name, clean_ver in req_packages:
            if norm_name not in seen:
                seen.add(norm_name)
                if norm_name in dist_map:
                    info = dist_map[norm_name]
                    packages.append({
                        "ecosystem": "pypi",
                        "name": info["name"],
                        "version": info["version"],
                        "license": info["license"],
                        "direct": True,
                        "purl": f"pkg:pypi/{info['name'].lower()}@{info['version']}",
                    })
                else:
                    packages.append({
                        "ecosystem": "pypi",
                        "name": pkg_name,
                        "version": clean_ver,
                        "license": "NOASSERTION",
                        "direct": True,
                        "purl": f"pkg:pypi/{norm_name}@{clean_ver}",
                    })

    return packages


def get_frontend_dependencies(repo_root: Path) -> List[Dict[str, Any]]:
    """Extract Node.js frontend packages from package-lock.json."""
    packages = []
    lock_file = repo_root / "frontend" / "package-lock.json"
    pkg_json_file = repo_root / "frontend" / "package.json"

    direct_deps = set()
    if pkg_json_file.exists():
        try:
            pdata = json.loads(pkg_json_file.read_text())
            direct_deps.update(pdata.get("dependencies", {}).keys())
            direct_deps.update(pdata.get("devDependencies", {}).keys())
        except Exception:
            pass

    if lock_file.exists():
        try:
            ldata = json.loads(lock_file.read_text())
            pkgs = ldata.get("packages", {})
            seen = set()

            for ppath, pinfo in pkgs.items():
                if not ppath:  # Root package
                    continue
                name = ppath.split("node_modules/")[-1]
                if not name:
                    continue
                version = pinfo.get("version", "unknown")
                # Deduplicate on (name, version) to preserve multi-version transitive closures
                key = (name, version)
                if key in seen:
                    continue
                seen.add(key)

                license_str = pinfo.get("license", "NOASSERTION")
                packages.append({
                    "ecosystem": "npm",
                    "name": name,
                    "version": version,
                    "license": license_str or "NOASSERTION",
                    "direct": name in direct_deps,
                    "purl": f"pkg:npm/{name}@{version}",
                })
        except Exception as e:
            print(f"Warning: Failed to parse package-lock.json: {e}", file=sys.stderr)

    return sorted(packages, key=lambda x: (x["name"], x["version"]))


def generate_spdx_json(
    packages: List[Dict[str, Any]],
    doc_name: str = "Project Vulcan Control Plane",
    doc_namespace_prefix: str = "https://github.com/lavkushry/vulcan/spdx",
) -> Dict[str, Any]:
    """Build a compliant SPDX 2.3 JSON document."""
    doc_uuid = str(uuid.uuid4())
    doc_spdx_id = "SPDXRef-DOCUMENT"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    spdx_packages = []
    relationships = []

    for idx, pkg in enumerate(packages, start=1):
        clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", pkg["name"])
        pkg_id = f"SPDXRef-Package-{pkg['ecosystem']}-{clean_name}-{idx}"

        spdx_packages.append({
            "SPDXID": pkg_id,
            "name": pkg["name"],
            "versionInfo": pkg["version"],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": pkg.get("license", "NOASSERTION"),
            "licenseDeclared": pkg.get("license", "NOASSERTION"),
            "supplier": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": pkg["purl"],
                }
            ],
        })

        relationships.append({
            "spdxElementId": doc_spdx_id,
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": pkg_id,
        })

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": doc_spdx_id,
        "name": doc_name,
        "documentNamespace": f"{doc_namespace_prefix}/{doc_uuid}",
        "creationInfo": {
            "created": now_iso,
            "creators": [
                "Tool: vulcan-sbom-generator-1.0",
                "Organization: Project Vulcan Core Engineering",
            ],
            "licenseListVersion": "3.22",
        },
        "packages": spdx_packages,
        "relationships": relationships,
    }


def generate_cyclonedx_json(
    packages: List[Dict[str, Any]],
    app_name: str = "vulcan-control-plane",
    app_version: str = "1.0.0",
) -> Dict[str, Any]:
    """Build a compliant CycloneDX 1.5 JSON document."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bom_uuid = str(uuid.uuid4())

    components = []
    for pkg in packages:
        comp: Dict[str, Any] = {
            "type": "library",
            "name": pkg["name"],
            "version": pkg["version"],
            "purl": pkg["purl"],
            "scope": "required" if pkg.get("direct") else "optional",
        }
        lic = pkg.get("license")
        if lic and lic != "NOASSERTION":
            comp["licenses"] = [{"license": {"name": str(lic)}}]
        components.append(comp)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{bom_uuid}",
        "version": 1,
        "metadata": {
            "timestamp": now_iso,
            "tools": [
                {
                    "vendor": "Project Vulcan",
                    "name": "vulcan-sbom-generator",
                    "version": "1.0",
                }
            ],
            "component": {
                "type": "application",
                "name": app_name,
                "version": app_version,
                "description": "Enterprise Automation Control Plane for Banking Governance",
            },
        },
        "components": components,
    }


def main():
    parser = argparse.ArgumentParser(description="Project Vulcan SBOM Generator (INFRA-30)")
    parser.add_argument(
        "--output-dir",
        default="sbom",
        help="Directory to save generated SBOM artifacts (default: sbom)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to repository root (default: current working directory)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"─── Project Vulcan SBOM Generator (INFRA-30) ───")
    print(f"Scanning repository at: {repo_root}")

    backend_pkgs = get_backend_dependencies(repo_root)
    frontend_pkgs = get_frontend_dependencies(repo_root)
    all_pkgs = backend_pkgs + frontend_pkgs

    print(f"✓ Backend Python packages: {len(backend_pkgs)}")
    print(f"✓ Frontend npm packages:    {len(frontend_pkgs)}")
    print(f"✓ Total components indexed: {len(all_pkgs)}")

    if not all_pkgs:
        print("🔴 ERROR: No dependencies discovered. Aborting.", file=sys.stderr)
        sys.exit(1)

    # 1. Generate SPDX 2.3 JSON
    spdx_doc = generate_spdx_json(all_pkgs)
    spdx_file = out_dir / "vulcan-sbom.spdx.json"
    spdx_text = json.dumps(spdx_doc, indent=2)
    spdx_file.write_text(spdx_text)
    spdx_sha256 = hashlib.sha256(spdx_text.encode()).hexdigest()
    print(f"✓ Generated SPDX 2.3:       {spdx_file} ({len(spdx_text)} bytes, SHA-256: {spdx_sha256[:16]}...)")

    # 2. Generate CycloneDX 1.5 JSON
    cdx_doc = generate_cyclonedx_json(all_pkgs)
    cdx_file = out_dir / "vulcan-sbom.cyclonedx.json"
    cdx_text = json.dumps(cdx_doc, indent=2)
    cdx_file.write_text(cdx_text)
    cdx_sha256 = hashlib.sha256(cdx_text.encode()).hexdigest()
    print(f"✓ Generated CycloneDX 1.5:  {cdx_file} ({len(cdx_text)} bytes, SHA-256: {cdx_sha256[:16]}...)")

    # 3. Generate summary metadata manifest
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_components": len(all_pkgs),
        "backend_python_count": len(backend_pkgs),
        "frontend_npm_count": len(frontend_pkgs),
        "artifacts": {
            "spdx_json": {
                "file": "vulcan-sbom.spdx.json",
                "bytes": len(spdx_text),
                "sha256": spdx_sha256,
            },
            "cyclonedx_json": {
                "file": "vulcan-sbom.cyclonedx.json",
                "bytes": len(cdx_text),
                "sha256": cdx_sha256,
            },
        },
    }
    manifest_file = out_dir / "sbom-manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2))
    print(f"✓ Generated Manifest:       {manifest_file}")
    print(f"══════════════════════════════════════════════════════════")
    print(f"  SBOM GENERATION SUCCESSFUL: 0 ERRORS")
    print(f"══════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
