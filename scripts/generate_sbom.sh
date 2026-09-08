#!/usr/bin/env bash
# ==============================================================================
# Project Vulcan: Automated Software Bill of Materials (SBOM) Gate (INFRA-30)
#
# Generates standards-compliant SPDX 2.3 and CycloneDX 1.5 JSON SBOMs covering
# both Python backend and Node.js frontend dependencies.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${1:-$REPO_ROOT/sbom}"

echo "===================================================================="
echo "  PROJECT VULCAN: SOFTWARE BILL OF MATERIALS (SBOM) GATE (INFRA-30)"
echo "===================================================================="
echo "Repository Root: $REPO_ROOT"
echo "Output Directory: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

# 1. Run canonical Python SBOM generator
python3 "$SCRIPT_DIR/generate_sbom.py" --repo-root "$REPO_ROOT" --output-dir "$OUTPUT_DIR"

# 2. Check for optional Syft binary (e.g. in CI or advanced security runner)
if command -v syft &>/dev/null; then
    echo ""
    echo "─── Syft CLI Detected: Generating Container / Filesystem SBOM ───"
    syft dir:"$REPO_ROOT" -o spdx-json="$OUTPUT_DIR/vulcan-syft.spdx.json" -o cyclonedx-json="$OUTPUT_DIR/vulcan-syft.cyclonedx.json" -q || true
    if [ -f "$OUTPUT_DIR/vulcan-syft.spdx.json" ]; then
        echo "✓ Syft SPDX 2.3 generated:       $OUTPUT_DIR/vulcan-syft.spdx.json"
    fi
    if [ -f "$OUTPUT_DIR/vulcan-syft.cyclonedx.json" ]; then
        echo "✓ Syft CycloneDX 1.5 generated:  $OUTPUT_DIR/vulcan-syft.cyclonedx.json"
    fi
fi

# 3. Validation Gate: Assert canonical SBOM artifacts exist and are valid JSON
echo ""
echo "─── Validating Generated SBOM Artifact Integrity ───"

for f in "$OUTPUT_DIR/vulcan-sbom.spdx.json" "$OUTPUT_DIR/vulcan-sbom.cyclonedx.json" "$OUTPUT_DIR/sbom-manifest.json"; do
    if [ ! -f "$f" ]; then
        echo "🔴 GATE FAILURE: Expected SBOM artifact missing: $f"
        exit 1
    fi
    if [ ! -s "$f" ]; then
        echo "🔴 GATE FAILURE: SBOM artifact is empty: $f"
        exit 1
    fi
    # Validate JSON syntax
    python3 -c "import json, sys; json.load(open('$f'))" || {
        echo "🔴 GATE FAILURE: Invalid JSON in $f"
        exit 1
    }
done

echo "✓ All SBOM artifacts validated (SPDX 2.3 JSON + CycloneDX 1.5 JSON + Manifest)."
echo "===================================================================="
echo "  SBOM GATE VERIFICATION SUCCESSFUL (INFRA-30)"
echo "===================================================================="
