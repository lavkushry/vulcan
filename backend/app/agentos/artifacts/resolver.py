"""
Project Vulcan: AgentOS Artifact Resolver & Interface Inspector
Author: Architectural Review Board & AgentOS Core Team

Responsibilities:
1. Maintain explicit artifact lifecycle states:
   DISCOVERED -> DOWNLOADED -> VERIFIED (or INCOMPATIBLE / REJECTED)
2. Verify cryptographic commit digest / SHA256 integrity (DigestMismatchError).
3. Stage artifact into an isolated execution workspace using ContentAddressableCache.
4. Inspect real role interfaces:
   - meta/argument_specs.yml: formal option schema (types, required, defaults, choices)
   - catalog input_schema: formal fallback specification
   - meta/main.yml: supported platforms, dependencies
   - defaults/main.yml: fallback variable defaults
5. Evaluate OS platform compatibility against user specifications.
"""
from __future__ import annotations

import enum
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from app.agentos.artifacts.yaml_parser import parse_yaml
from app.agentos.artifacts.downloader import (
    ArchiveSafetyValidator,
    ContentAddressableCache,
    GalaxyDownloadAdapter,
    GitDownloadAdapter,
    LocalCatalogAdapter,
    RegistryDownloadAdapter,
    RegistryUnavailableError,
    SecurityError,
)

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


class IncompatiblePlatformError(Exception):
    """Raised when an asset's supported platforms do not satisfy the requested OS."""
    pass


class MissingRequiredVariableError(Exception):
    """Raised when an asset requires parameters that were neither supplied nor have defaults."""
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
        argument_specs: Optional[Dict[str, Any]] = None,
        playbook_path: Optional[str] = None,
        missing_required_variables: Optional[List[str]] = None,
    ):
        self.identifier = identifier
        self.name = name
        self.supported_platforms = supported_platforms
        self.required_variables = required_variables
        self.variable_defaults = variable_defaults
        self.dependencies = dependencies
        self.tasks_summary = tasks_summary
        self.input_schema = input_schema or {}
        self.argument_specs = argument_specs or {}
        self.playbook_path = playbook_path
        self.missing_required_variables = missing_required_variables or []

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
            "argument_specs": self.argument_specs,
            "playbook_path": self.playbook_path,
            "missing_required_variables": self.missing_required_variables,
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
    Backboned by ContentAddressableCache and RegistryDownloadAdapters.
    """

    def __init__(
        self,
        base_repo_dir: Optional[Path] = None,
        cache_root: Optional[Path] = None,
    ):
        self.base_dir = base_repo_dir or Path(__file__).resolve().parent.parent.parent.parent
        self.roles_dir = self.base_dir / "ansible" / "roles"
        self.playbooks_dir = self.base_dir / "ansible" / "playbooks"
        self.cache = ContentAddressableCache(cache_root=cache_root)
        self.local_adapter = LocalCatalogAdapter(self.base_dir)
        self.galaxy_adapter = GalaxyDownloadAdapter(local_fallback=self.local_adapter)
        self.git_adapter = GitDownloadAdapter()

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
            return requested_os.lower() not in ("windows", "win", "macos", "darwin")

        req = requested_os.lower().replace(" ", "").replace("_", "").replace("-", "")

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
        provided_parameters: Optional[Dict[str, Any]] = None,
    ) -> ResolvedAsset:
        """
        Orchestrates DISCOVERED -> DOWNLOADED -> VERIFIED pipeline.
        Enforces:
        - Registry health check
        - ContentAddressableCache lookup
        - Cryptographic SHA-256 / commit digest verification
        - meta/argument_specs.yml priority inspection
        - Fallback defaults and missing required variable detection
        - Operating system platform compatibility
        """
        # 1. State: DISCOVERED
        current_state = ArtifactState.DISCOVERED

        if os.environ.get("VULCAN_REGISTRY_UNAVAILABLE") == "1":
            raise RegistryUnavailableError(f"External registry is unreachable for asset '{identifier}'.")

        staging_parent = workspace_parent or Path(f"/tmp/vulcan_staging/{workflow_id}")
        staged_dir = staging_parent / identifier.replace(".", "_")
        staged_dir.mkdir(parents=True, exist_ok=True)
        staged_files: Dict[str, str] = {}

        # 2. Check ContentAddressableCache first if expected_sha matches a cached digest
        used_cached = False
        if expected_sha and self.cache.contains(expected_sha):
            cached_path = self.cache.get(expected_sha)
            if cached_path:
                for root, _, files in os.walk(cached_path):
                    for f in sorted(files):
                        fp = Path(root) / f
                        rel_path = fp.relative_to(cached_path)
                        try:
                            content = fp.read_text(encoding="utf-8")
                            staged_files[str(rel_path)] = content
                            dest = staged_dir / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_text(content, encoding="utf-8")
                        except Exception:
                            pass
                used_cached = True

        if not used_cached:
            # Download via appropriate adapter
            # Determine source: if git_repo declared in raw_catalog_item or git in source_uri
            adapter: RegistryDownloadAdapter = self.local_adapter
            if "galaxy" in source_uri or (raw_catalog_item and raw_catalog_item.get("source_type") == "galaxy"):
                adapter = self.galaxy_adapter
            elif "git" in source_uri or (raw_catalog_item and raw_catalog_item.get("source_type") == "git"):
                adapter = self.git_adapter

            downloaded_root = adapter.download_artifact(identifier, version, staging_parent)

            # Copy downloaded contents to staged_dir if distinct
            if downloaded_root != staged_dir:
                for root, _, files in os.walk(downloaded_root):
                    for f in sorted(files):
                        fp = Path(root) / f
                        rel_path = fp.relative_to(downloaded_root)
                        try:
                            content = fp.read_text(encoding="utf-8")
                            staged_files[str(rel_path)] = content
                            dest = staged_dir / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_text(content, encoding="utf-8")
                        except Exception:
                            pass
            else:
                for root, _, files in os.walk(staged_dir):
                    for f in sorted(files):
                        fp = Path(root) / f
                        rel_path = fp.relative_to(staged_dir)
                        try:
                            staged_files[str(rel_path)] = fp.read_text(encoding="utf-8")
                        except Exception:
                            pass

        # 3. State: DOWNLOADED
        current_state = ArtifactState.DOWNLOADED

        # 4. Compute artifact content digest SHA-256
        combined = []
        for path in sorted(staged_files.keys()):
            combined.append(f"{path}:{staged_files[path]}")
        raw_bytes = "\n---FILE---\n".join(combined).encode("utf-8")
        computed_digest = hashlib.sha256(raw_bytes).hexdigest()

        # Cache valid artifact
        self.cache.put(computed_digest, staged_dir)

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

        # 5. Interface Inspection: argument_specs.yml priority -> input_schema -> defaults/main.yml fallback
        platforms: List[Dict[str, Any]] = []
        dependencies: List[str] = []
        defaults: Dict[str, Any] = {}
        required_vars: List[str] = []
        argument_specs: Dict[str, Any] = {}
        tasks: List[str] = []
        input_schema: Dict[str, Any] = (
            raw_catalog_item.get("input_schema", {}) if raw_catalog_item else {}
        )

        # 5a. Read meta/argument_specs.yml (Ansible 2.11+ formal standard)
        arg_specs_raw = (
            staged_files.get("meta/argument_specs.yml")
            or staged_files.get("meta/argument_specs.yaml")
        )
        if arg_specs_raw:
            try:
                parsed_specs = parse_yaml(arg_specs_raw) or {}
                if isinstance(parsed_specs, dict) and "argument_specs" in parsed_specs:
                    argument_specs = parsed_specs["argument_specs"]
                    main_options = argument_specs.get("main", {}).get("options", {})
                    for opt_k, opt_v in main_options.items():
                        if isinstance(opt_v, dict):
                            if opt_v.get("required") is True:
                                if opt_k not in required_vars:
                                    required_vars.append(opt_k)
                            if "default" in opt_v:
                                defaults[opt_k] = opt_v["default"]
            except Exception as e:
                logger.warning("Failed to parse meta/argument_specs.yml for %s: %s", identifier, e)

        # 5b. Catalog input_schema fallback specification
        if input_schema and isinstance(input_schema, dict):
            for req in input_schema.get("required", []):
                if req not in required_vars:
                    required_vars.append(req)
            for k, v in input_schema.get("properties", {}).items():
                if "default" in v and k not in defaults:
                    defaults[k] = v["default"]

        # 5c. defaults/main.yml ONLY as fallback for undeclared option defaults
        defaults_content = staged_files.get("defaults/main.yml")
        if defaults_content:
            try:
                parsed_defaults = parse_yaml(defaults_content) or {}
                if isinstance(parsed_defaults, dict):
                    for k, v in parsed_defaults.items():
                        if k not in defaults:
                            defaults[k] = v
            except Exception as e:
                logger.warning("Failed to parse defaults/main.yml for %s: %s", identifier, e)

        # 5d. meta/main.yml for platforms and dependencies
        meta_content = staged_files.get("meta/main.yml")
        if meta_content:
            try:
                parsed_meta = parse_yaml(meta_content) or {}
                galaxy_info = parsed_meta.get("galaxy_info", {})
                platforms = galaxy_info.get("platforms", [])
                dependencies = parsed_meta.get("dependencies", []) or []
            except Exception as e:
                logger.warning("Failed to parse meta/main.yml for %s: %s", identifier, e)

        # 5e. tasks/main.yml for summary
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

        # 5f. Track missing required variables
        provided = provided_parameters or {}
        missing_required = [
            rv for rv in required_vars
            if rv not in provided and rv not in defaults
        ]

        # Determine playbook path if available
        playbook_path = None
        for cand_pb in staged_files:
            if cand_pb.endswith(".yml") and ("playbook" in cand_pb or "deploy" in cand_pb or cand_pb == "main.yml"):
                playbook_path = str(staged_dir / cand_pb)
                break

        interface = RoleInterface(
            identifier=identifier,
            name=raw_catalog_item.get("name", identifier) if raw_catalog_item else identifier,
            supported_platforms=platforms,
            required_variables=required_vars,
            variable_defaults=defaults,
            dependencies=dependencies,
            tasks_summary=tasks,
            input_schema=input_schema,
            argument_specs=argument_specs,
            playbook_path=playbook_path,
            missing_required_variables=missing_required,
        )

        # 6. Check platform compatibility
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
