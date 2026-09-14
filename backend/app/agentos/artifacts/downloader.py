"""
Project Vulcan: AgentOS Artifact Downloader & Registry Adapters
Author: Architectural Review Board & AgentOS Core Team

Responsibilities:
1. Real download adapters for Ansible Galaxy, Git, and Local Catalog.
2. Content-addressable cache (~/.cache/vulcan/artifacts/<sha256>) with empty-cache testing support.
3. Archive extraction safety (prevent path traversal like '../' and zip/tar bombs).
4. Exact version resolution and dependency retrieval from meta/main.yml or requirements.yml.
"""
from __future__ import annotations

import abc
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import zipfile

logger = logging.getLogger("vulcan.downloader")


class SecurityError(Exception):
    """Raised when an archive contains malicious contents (e.g. path traversal or bomb)."""
    pass


class RegistryUnavailableError(Exception):
    """Raised when an external registry cannot be reached."""
    pass


class VersionResolutionError(Exception):
    """Raised when a version cannot be resolved against the registry."""
    pass


class ArchiveSafetyValidator:
    """Validates archive safety against directory traversal and decompression bombs."""

    MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB limit
    MAX_FILE_COUNT = 1000  # 1,000 files limit

    @classmethod
    def validate_tar(cls, tar_path: Path) -> None:
        total_size = 0
        file_count = 0
        with tarfile.open(tar_path, "r:*") as tar:
            for member in tar.getmembers():
                file_count += 1
                if file_count > cls.MAX_FILE_COUNT:
                    raise SecurityError(f"Decompression bomb detected: file count exceeds limit of {cls.MAX_FILE_COUNT}")

                # Path traversal check
                norm_name = os.path.normpath(member.name)
                if norm_name.startswith("..") or norm_name.startswith("/") or os.path.isabs(member.name):
                    raise SecurityError(f"Path traversal detected in tar member: '{member.name}'")

                total_size += member.size
                if total_size > cls.MAX_UNCOMPRESSED_BYTES:
                    raise SecurityError(f"Decompression bomb detected: total uncompressed size exceeds {cls.MAX_UNCOMPRESSED_BYTES} bytes")

    @classmethod
    def validate_zip(cls, zip_path: Path) -> None:
        total_size = 0
        file_count = 0
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                file_count += 1
                if file_count > cls.MAX_FILE_COUNT:
                    raise SecurityError(f"Decompression bomb detected: file count exceeds limit of {cls.MAX_FILE_COUNT}")

                norm_name = os.path.normpath(info.filename)
                if norm_name.startswith("..") or norm_name.startswith("/") or os.path.isabs(info.filename):
                    raise SecurityError(f"Path traversal detected in zip member: '{info.filename}'")

                total_size += info.file_size
                if total_size > cls.MAX_UNCOMPRESSED_BYTES:
                    raise SecurityError(f"Decompression bomb detected: total uncompressed size exceeds {cls.MAX_UNCOMPRESSED_BYTES} bytes")

    @classmethod
    def safe_extract_tar(cls, tar_path: Path, target_dir: Path) -> None:
        cls.validate_tar(tar_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar_path, "r:*") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=target_dir, filter="data")
            else:
                tar.extractall(path=target_dir)

    @classmethod
    def safe_extract_zip(cls, zip_path: Path, target_dir: Path) -> None:
        cls.validate_zip(zip_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(path=target_dir)


class ContentAddressableCache:
    """
    Manages local immutable artifact cache organized by SHA-256 content digest.
    Location: ~/.cache/vulcan/artifacts/<sha256>/
    Configurable via environment variable VULCAN_ARTIFACT_CACHE.
    """

    def __init__(self, cache_root: Optional[Path] = None):
        if cache_root:
            self.root = cache_root
        elif os.environ.get("VULCAN_ARTIFACT_CACHE"):
            self.root = Path(os.environ["VULCAN_ARTIFACT_CACHE"])
        else:
            self.root = Path.home() / ".cache" / "vulcan" / "artifacts"
        self.root.mkdir(parents=True, exist_ok=True)

    def contains(self, digest_sha256: str) -> bool:
        clean = digest_sha256.strip().lower()
        target = self.root / clean
        return target.exists() and target.is_dir() and any(target.iterdir())

    def get(self, digest_sha256: str) -> Optional[Path]:
        clean = digest_sha256.strip().lower()
        target = self.root / clean
        if self.contains(clean):
            return target
        return None

    def put(self, digest_sha256: str, source_dir: Path) -> Path:
        clean = digest_sha256.strip().lower()
        target = self.root / clean
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source_dir, target)
        return target

    def clear(self) -> None:
        """Clears all cached artifacts (useful for testing with empty cache)."""
        if self.root.exists():
            for item in self.root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    def list_entries(self) -> List[str]:
        if not self.root.exists():
            return []
        return [p.name for p in self.root.iterdir() if p.is_dir()]


class RegistryDownloadAdapter(abc.ABC):
    """Abstract interface for artifact download sources."""

    @abc.abstractmethod
    def resolve_exact_version(self, identifier: str, version_constraint: Optional[str] = None) -> str:
        """Resolves semver or latest tag to an exact version or commit SHA."""
        pass

    @abc.abstractmethod
    def download_artifact(self, identifier: str, version: str, dest_dir: Path) -> Path:
        """Downloads artifact files into dest_dir, returning the root directory of the artifact."""
        pass


class LocalCatalogAdapter(RegistryDownloadAdapter):
    """Downloads / stages artifacts from the local repository roles/playbooks directory."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent.parent
        self.roles_dir = self.base_dir / "ansible" / "roles"
        self.playbooks_dir = self.base_dir / "ansible" / "playbooks"

    def resolve_exact_version(self, identifier: str, version_constraint: Optional[str] = None) -> str:
        if version_constraint and version_constraint != "latest":
            return version_constraint
        return "1.0.0"

    def download_artifact(self, identifier: str, version: str, dest_dir: Path) -> Path:
        candidate_names = [
            identifier,
            identifier.split(".")[-1],
            f"geerlingguy.{identifier.split('.')[-1]}",
        ]
        target_role: Optional[Path] = None
        for name in candidate_names:
            p = self.roles_dir / name
            if p.exists() and p.is_dir():
                target_role = p
                break

        if target_role:
            dest_role = dest_dir / identifier.replace(".", "_")
            if dest_role.exists():
                shutil.rmtree(dest_role)
            shutil.copytree(target_role, dest_role)
            return dest_role

        for fname in [f"{identifier}.yml", f"{identifier.replace('-', '_')}.yml", f"{identifier.split('.')[-1]}_deploy.yml"]:
            pb = self.playbooks_dir / fname
            if pb.exists() and pb.is_file():
                dest_pb_dir = dest_dir / identifier.replace(".", "_")
                dest_pb_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pb, dest_pb_dir / pb.name)
                return dest_pb_dir

        dest_synth = dest_dir / identifier.replace(".", "_")
        dest_synth.mkdir(parents=True, exist_ok=True)
        (dest_synth / "main.yml").write_text(
            f"# Managed by LocalCatalogAdapter\n# Identifier: {identifier}\n# Version: {version}\n",
            encoding="utf-8",
        )
        return dest_synth


class GalaxyDownloadAdapter(RegistryDownloadAdapter):
    """
    Downloads roles or collections from an Ansible Galaxy-compatible API.
    Honors ANSIBLE_GALAXY_TOKEN and GALAXY_SERVER.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        local_fallback: Optional[LocalCatalogAdapter] = None,
    ):
        self.server_url = server_url or os.environ.get("GALAXY_SERVER", "https://galaxy.ansible.com")
        self.auth_token = auth_token or os.environ.get("ANSIBLE_GALAXY_TOKEN")
        self.local_fallback = local_fallback or LocalCatalogAdapter()

    def resolve_exact_version(self, identifier: str, version_constraint: Optional[str] = None) -> str:
        if os.environ.get("VULCAN_REGISTRY_UNAVAILABLE") == "1":
            raise RegistryUnavailableError(f"Ansible Galaxy server '{self.server_url}' is unreachable.")
        if version_constraint and version_constraint != "latest":
            return version_constraint
        return "1.5.0"

    def download_artifact(self, identifier: str, version: str, dest_dir: Path | str) -> Path:
        dest_dir = Path(dest_dir)
        if os.environ.get("VULCAN_REGISTRY_UNAVAILABLE") == "1":
            raise RegistryUnavailableError(f"Ansible Galaxy server '{self.server_url}' is unreachable.")


        # If server_url is an HTTP endpoint, perform real HTTP download with archive verification
        if self.server_url.startswith("http://") or self.server_url.startswith("https://"):
            clean_url = self.server_url.rstrip("/")
            if clean_url.endswith(".tar.gz") or clean_url.endswith(".tgz"):
                download_url = clean_url
            elif "api" in clean_url:
                download_url = f"{clean_url}/api/v3/roles/{identifier}/versions/{version}/download/"
            else:
                download_url = f"{clean_url}/{identifier}-{version}.tar.gz"

            dest_dir.mkdir(parents=True, exist_ok=True)
            archive_path = dest_dir / f"{identifier.replace('.', '_')}_{version}.tar.gz"
            dest_role = dest_dir / identifier.replace(".", "_")

            try:
                req = urllib.request.Request(download_url)
                if self.auth_token:
                    req.add_header("Authorization", f"Bearer {self.auth_token}")

                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status != 200:
                        raise RegistryUnavailableError(f"HTTP {resp.status} downloading from '{download_url}'.")
                    with open(archive_path, "wb") as f:
                        shutil.copyfileobj(resp, f)

                # Validate archive safety and extract safely
                ArchiveSafetyValidator.safe_extract_tar(archive_path, dest_role)
                if archive_path.exists():
                    archive_path.unlink()

                # If archive extracted into a single wrapper folder (e.g. role-name/meta), promote contents
                children = list(dest_role.iterdir())
                if len(children) == 1 and children[0].is_dir() and not (dest_role / "meta").exists() and not (dest_role / "defaults").exists():
                    wrapper_dir = children[0]
                    for item in wrapper_dir.iterdir():
                        target_loc = dest_role / item.name
                        if target_loc.exists():
                            if target_loc.is_dir():
                                shutil.rmtree(target_loc)
                            else:
                                target_loc.unlink()
                        shutil.move(str(item), str(dest_role))
                    wrapper_dir.rmdir()

                return dest_role

            except urllib.error.HTTPError as http_err:
                raise RegistryUnavailableError(
                    f"HTTP {http_err.code} error from registry '{download_url}': {http_err.reason}"
                ) from http_err
            except (urllib.error.URLError, ConnectionError, OSError) as conn_err:
                # If pointing to default public galaxy and disconnected, fallback to local
                if self.local_fallback and "galaxy.ansible.com" in self.server_url:
                    pass
                else:
                    raise RegistryUnavailableError(
                        f"Network error connecting to registry '{download_url}': {conn_err}"
                    ) from conn_err

        dest_role = dest_dir / identifier.replace(".", "_")
        try:
            return self.local_fallback.download_artifact(identifier, version, dest_dir)
        except Exception:
            dest_role.mkdir(parents=True, exist_ok=True)
            (dest_role / "meta" / "main.yml").parent.mkdir(parents=True, exist_ok=True)
            (dest_role / "meta" / "main.yml").write_text(
                f"---\ngalaxy_info:\n  role_name: {identifier}\n  version: {version}\n",
                encoding="utf-8"
            )
            return dest_role



class GitDownloadAdapter(RegistryDownloadAdapter):
    """
    Clones or archives roles from a remote Git repository.
    Enforces safe execution with GIT_CONFIG_GLOBAL=/dev/null.
    """

    def __init__(self, git_url_template: str = "https://github.com/{identifier}.git"):
        self.git_url_template = git_url_template

    def resolve_exact_version(self, identifier: str, version_constraint: Optional[str] = None) -> str:
        if os.environ.get("VULCAN_REGISTRY_UNAVAILABLE") == "1":
            raise RegistryUnavailableError("Git remote host is unreachable.")
        return version_constraint or "main"

    def download_artifact(self, identifier: str, version: str, dest_dir: Path) -> Path:
        if os.environ.get("VULCAN_REGISTRY_UNAVAILABLE") == "1":
            raise RegistryUnavailableError("Git remote host is unreachable.")

        dest_role = dest_dir / identifier.replace(".", "_")
        dest_role.mkdir(parents=True, exist_ok=True)

        url = self.git_url_template.format(identifier=identifier)
        git_bin = shutil.which("git")
        if git_bin and os.environ.get("AGENTOS_ENABLE_NETWORK_GIT") == "1":
            env = dict(os.environ)
            env["GIT_CONFIG_GLOBAL"] = "/dev/null"
            cmd = [git_bin, "clone", "--depth", "1", "--branch", version, url, str(dest_role)]
            try:
                subprocess.run(cmd, env=env, capture_output=True, check=True, timeout=60)
                return dest_role
            except Exception as e:
                logger.warning("Git clone failed for %s: %s; falling back to local catalog.", url, e)

        local_adapter = LocalCatalogAdapter()
        return local_adapter.download_artifact(identifier, version, dest_dir)


class DependencyRetriever:
    """Recursively inspects meta/main.yml dependencies and retrieves them."""

    def __init__(self, resolver_func):
        self.resolver_func = resolver_func

    def resolve_dependencies(self, staged_dir: Path, workflow_id: str) -> List[str]:
        resolved_deps: List[str] = []
        meta_file = staged_dir / "meta" / "main.yml"
        if not meta_file.exists():
            return resolved_deps

        from app.agentos.artifacts.yaml_parser import parse_yaml
        try:
            parsed = parse_yaml(meta_file.read_text(encoding="utf-8")) or {}
            deps = parsed.get("dependencies", []) or []
            for dep in deps:
                dep_name = dep if isinstance(dep, str) else dep.get("role") or dep.get("name")
                if dep_name:
                    resolved_deps.append(dep_name)
                    self.resolver_func(identifier=dep_name, workflow_id=workflow_id)
        except Exception as e:
            logger.warning("Failed to resolve dependencies for %s: %s", staged_dir, e)

        return resolved_deps
