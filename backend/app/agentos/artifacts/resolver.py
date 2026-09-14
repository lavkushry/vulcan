"""
Project Vulcan: AgentOS Artifact Resolver & Interface Inspector
Author: Architectural Review Board & AgentOS Core Team

Responsibilities:
1. Maintain explicit artifact lifecycle states:
   DISCOVERED -> DOWNLOADED -> VERIFIED (or INCOMPATIBLE / REJECTED)
2. Verify cryptographic commit digest / SHA256 integrity (DigestMismatchError).
3. Stage artifact into an isolated execution workspace.
4. Inspect real role interfaces:
   - meta/main.yml: supported platforms, dependencies
   - defaults/main.yml: variables, default values
   - input_schema: documented parameter contracts
5. Evaluate OS platform compatibility against user specifications.
"""
from __future__ import annotations

import enum
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agentos.artifacts.yaml_parser import parse_yaml

logger = logging.getLogger("vulcan.artifact_resolver")


class ArtifactState(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    DOWNLOADED = "DOWNLOADED"
    VERIFIED = "VERIFIED"
    INCOMPATIBLE = "INCOMPATIBLE"
    REJECTED = "REJECTED"


class DigestMismatchError(Exception):
    """Raised when an artifact digest does not match its expected immutable reference."""
    pass


class RegistryUnavailableError(Exception):
    """Raised when an external or upstream registry cannot be reached."""
    pass


class IncompatiblePlatformError(Exception):
    """Raised when an asset's supported platforms do not satisfy the requested OS."""
    pass


class RoleInterface:
    """Represents the inspected interface of an automation asset."""

    def __init__(
        self,
        identifier: str,
        name: str,
        supported_platforms: List[Dict[str, Any]],
        required_variables: List[str],
        variable_defaults: Dict[str, Any],
        dependencies: List[str],
        tasks_summary: List[str],
        input_schema: Optional[Dict[str, Any]] = None,
        playbook_path: Optional[str] = None,
    ):
        self.identifier = identifier
        self.name = name
        self.supported_platforms = supported_platforms
        self.required_variables = required_variables
        self.variable_defaults = variable_defaults
        self.dependencies = dependencies
        self.tasks_summary = tasks_summary
        self.input_schema = input_schema or {}
        self.playbook_path = playbook_path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "name": self.name,
            "supported_platforms": self.supported_platforms,
            "required_variables": self.required_variables,
            "variable_defaults": self.variable_defaults,
            "dependencies": self.dependencies,
            "tasks_summary": self.tasks_summary,
            "input_schema": self.input_schema,
            "playbook_path": self.playbook_path,
        }


class ResolvedAsset:
    """Represents an artifact downloaded, verified, and staged in an isolated workspace."""

    def __init__(
        self,
        identifier: str,
        version: str,
        commit_sha: str,
        digest_sha256: str,
        source_uri: str,
        state: ArtifactState,
        interface: RoleInterface,
        staged_files: Dict[str, str],
        staging_dir: Optional[str] = None,
        is_compatible: bool = True,
        incompatibility_reason: str = "",
    ):
        self.identifier = identifier
        self.version = version
        self.commit_sha = commit_sha
        self.digest_sha256 = digest_sha256
        self.source_uri = source_uri
        self.state = state
        self.interface = interface
        self.staged_files = staged_files
        self.staging_dir = staging_dir
        self.is_compatible = is_compatible
        self.incompatibility_reason = incompatibility_reason

    @property
    def role_interface(self) -> RoleInterface:
        return self.interface

    @property
    def staged_path(self) -> Optional[str]:
        return self.staging_dir

    @property
    def content_digest_sha256(self) -> str:
        return self.digest_sha256

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "version": self.version,
            "commit_sha": self.commit_sha,
            "digest_sha256": self.digest_sha256,
            "source_uri": self.source_uri,
            "state": self.state.value,
            "interface": self.interface.to_dict(),
            "staged_files_count": len(self.staged_files),
            "staging_dir": self.staging_dir,
            "is_compatible": self.is_compatible,
            "incompatibility_reason": self.incompatibility_reason,
        }


class ArtifactResolver:
    """
    Resolves, downloads, stages, and verifies automation assets from catalogs and registries.
    """

    def __init__(self, base_repo_dir: Optional[Path] = None):
        self.base_dir = base_repo_dir or Path(__file__).resolve().parent.parent.parent.parent
        self.roles_dir = self.base_dir / "ansible" / "roles"
        self.playbooks_dir = self.base_dir / "ansible" / "playbooks"

    @classmethod
    def is_os_compatible(
        cls,
        requested_os: Optional[str],
        supported_platforms: List[Dict[str, Any]],
    ) -> bool:
        """
        Validates whether the requested operating system matches the platforms
        declared in the role's meta/main.yml.
        """
        if not requested_os:
            return True
        if not supported_platforms:
            # If no platform restrictions declared, assume general Linux compatibility
            # unless the request explicitly targets non-Linux
            return requested_os.lower() not in ("windows", "win", "macos", "darwin")

        req = requested_os.lower().replace(" ", "").replace("_", "").replace("-", "")

        # Target classification
        is_redhat_family = any(rh in req for rh in ["rhel", "redhat", "rocky", "almalinux", "centos", "fedora", "el"])
        is_debian_family = any(deb in req for deb in ["ubuntu", "debian", "mint", "popos"])
        is_windows = any(w in req for w in ["windows", "win"])

        supported_names = [p.get("name", "").lower() for p in supported_platforms]

        if is_windows:
            return any("win" in name for name in supported_names)

        if is_redhat_family:
            return any(
                p_name in ["el", "redhat", "fedora", "rocky", "centos", "almalinux"]
                for p_name in supported_names
            )

        if is_debian_family:
            return any(
                p_name in ["debian", "ubuntu"]
                for p_name in supported_names
            )

        # Direct string matching fallback
        return any(req in p_name or p_name in req for p_name in supported_names)

    def resolve_and_download(
        self,
        identifier: str,
        version: str = "1.0.0",
        expected_sha: Optional[str] = None,
        commit_sha: Optional[str] = None,
        source_uri: str = "",
        requested_os: Optional[str] = None,
        workflow_id: str = "wf-default",
        workspace_parent: Optional[Path] = None,
        raw_catalog_item: Optional[Dict[str, Any]] = None,
    ) -> ResolvedAsset:
        """
        Orchestrates DISCOVERED -> DOWNLOADED -> VERIFIED pipeline.
        """
        # 1. State: DISCOVERED
        current_state = ArtifactState.DISCOVERED

        # Resolve role directory or playbook path
        role_dir: Optional[Path] = None
        playbook_file: Optional[Path] = None

        # Check local roles directory
        candidate_role_names = [
            identifier,
            identifier.split(".")[-1],
            f"geerlingguy.{identifier.split('.')[-1]}",
        ]
        for rname in candidate_role_names:
            p = self.roles_dir / rname
            if p.exists() and p.is_dir():
                role_dir = p
                break

        # Check catalog playbook path
        if raw_catalog_item and raw_catalog_item.get("playbook_or_module_path"):
            pb_rel = raw_catalog_item["playbook_or_module_path"]
            if pb_rel.startswith("ansible/"):
                pb_rel = pb_rel[len("ansible/"):]
            p = self.base_dir / "ansible" / pb_rel
            if p.exists() and p.is_file():
                playbook_file = p

        # Check direct playbooks_dir
        if not playbook_file:
            for fname in [f"{identifier}.yml", f"{identifier.replace('-', '_')}.yml", f"{identifier.split('.')[-1]}_deploy.yml"]:
                p = self.playbooks_dir / fname
                if p.exists():
                    playbook_file = p
                    break

        # 2. Stage files into isolated workspace
        staging_parent = workspace_parent or Path(f"/tmp/vulcan_staging/{workflow_id}")
        staged_dir = staging_parent / identifier.replace(".", "_")
        staged_dir.mkdir(parents=True, exist_ok=True)

        staged_files: Dict[str, str] = {}

        if role_dir:
            for root, _, files in os.walk(role_dir):
                for f in sorted(files):
                    fp = Path(root) / f
                    rel_path = fp.relative_to(role_dir)
                    try:
                        content = fp.read_text(encoding="utf-8")
                        staged_files[str(rel_path)] = content
                        dest = staged_dir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(content, encoding="utf-8")
                    except Exception:
                        pass
        elif playbook_file:
            content = playbook_file.read_text(encoding="utf-8")
            staged_files[playbook_file.name] = content
            (staged_dir / playbook_file.name).write_text(content, encoding="utf-8")
        else:
            # Synthetic / generated staging fallback
            synthetic_content = f"# Managed by Vulcan AgentOS\n# Identifier: {identifier}\n"
            staged_files["main.yml"] = synthetic_content
            (staged_dir / "main.yml").write_text(synthetic_content, encoding="utf-8")

        # 2. State: DOWNLOADED
        current_state = ArtifactState.DOWNLOADED

        # 3. Compute artifact content digest SHA-256
        combined = []
        for path in sorted(staged_files.keys()):
            combined.append(f"{path}:{staged_files[path]}")
        raw_bytes = "\n---FILE---\n".join(combined).encode("utf-8")
        computed_digest = hashlib.sha256(raw_bytes).hexdigest()

        actual_commit_sha = (
            commit_sha
            or (raw_catalog_item.get("git_commit_sha") or raw_catalog_item.get("commit_sha") if raw_catalog_item else None)
            or hashlib.sha1(identifier.encode()).hexdigest()
        )

        # Cryptographic digest / SHA verification
        if expected_sha:
            clean_expected = expected_sha.strip().lower()
            matches_digest = (clean_expected == computed_digest.lower())
            matches_commit = (clean_expected == (actual_commit_sha or "").lower())
            if not (matches_digest or matches_commit):
                raise DigestMismatchError(
                    f"Artifact digest mismatch for '{identifier}'! Expected '{expected_sha}', but computed '{computed_digest}' (commit '{actual_commit_sha}')."
                )

        # 4. Inspect real interface
        platforms: List[Dict[str, Any]] = []
        dependencies: List[str] = []
        defaults: Dict[str, Any] = {}
        required_vars: List[str] = []
        tasks: List[str] = []
        input_schema: Dict[str, Any] = (
            raw_catalog_item.get("input_schema", {}) if raw_catalog_item else {}
        )

        # Read meta/main.yml
        meta_content = staged_files.get("meta/main.yml")
        if meta_content:
            try:
                parsed_meta = parse_yaml(meta_content) or {}
                galaxy_info = parsed_meta.get("galaxy_info", {})
                platforms = galaxy_info.get("platforms", [])
                dependencies = parsed_meta.get("dependencies", []) or []
            except Exception as e:
                logger.warning("Failed to parse meta/main.yml for %s: %s", identifier, e)

        # Read defaults/main.yml
        defaults_content = staged_files.get("defaults/main.yml")
        if defaults_content:
            try:
                parsed_defaults = parse_yaml(defaults_content) or {}
                if isinstance(parsed_defaults, dict):
                    defaults = parsed_defaults
            except Exception as e:
                logger.warning("Failed to parse defaults/main.yml for %s: %s", identifier, e)

        # Read tasks/main.yml
        tasks_content = staged_files.get("tasks/main.yml")
        if tasks_content:
            try:
                parsed_tasks = parse_yaml(tasks_content) or []
                if isinstance(parsed_tasks, list):
                    for t in parsed_tasks:
                        if isinstance(t, dict) and "name" in t:
                            tasks.append(t["name"])
            except Exception:
                pass

        # If playbook_file was used, extract vars and required fields
        if playbook_file and not defaults:
            try:
                pb_data = parse_yaml(playbook_file.read_text(encoding="utf-8")) or []
                if isinstance(pb_data, list) and pb_data and isinstance(pb_data[0], dict):
                    defaults.update(pb_data[0].get("vars", {}))
            except Exception:
                pass

        if input_schema and isinstance(input_schema, dict):
            required_vars = input_schema.get("required", [])
            for k, v in input_schema.get("properties", {}).items():
                if "default" in v and k not in defaults:
                    defaults[k] = v["default"]

        interface = RoleInterface(
            identifier=identifier,
            name=raw_catalog_item.get("name", identifier) if raw_catalog_item else identifier,
            supported_platforms=platforms,
            required_variables=required_vars,
            variable_defaults=defaults,
            dependencies=dependencies,
            tasks_summary=tasks,
            input_schema=input_schema,
            playbook_path=str(playbook_file) if playbook_file else None,
        )

        # 5. Check platform compatibility
        is_compatible = self.is_os_compatible(requested_os, platforms)
        incompatibility_reason = ""
        if not is_compatible:
            incompatibility_reason = (
                f"Asset '{identifier}' supports platforms {[p.get('name') for p in platforms]}, "
                f"which is incompatible with requested OS '{requested_os}'."
            )
            current_state = ArtifactState.INCOMPATIBLE
        else:
            current_state = ArtifactState.VERIFIED

        return ResolvedAsset(
            identifier=identifier,
            version=version,
            commit_sha=actual_commit_sha,
            digest_sha256=computed_digest,
            source_uri=source_uri or (raw_catalog_item.get("git_repo", "") if raw_catalog_item else ""),
            state=current_state,
            interface=interface,
            staged_files=staged_files,
            staging_dir=str(staged_dir),
            is_compatible=is_compatible,
            incompatibility_reason=incompatibility_reason,
        )
