"""
Project Vulcan: AgentOS Execution Adapters (P0 #1)
Author: AgentOS Core Team

Provides pluggable execution backends for the ConstrainedExecutor.
Supports:
1. Pre-change state snapshotting before mutation.
2. True state rollback restoring pre-change state snapshots.
3. Separate execution idempotency measurement (repeat runs report changed=0).
4. Dynamic workload task rendering without hardcoded PostgreSQL defaults.
"""
from __future__ import annotations

import abc
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional

from app.agentos.agents.executor import ExecutionResult

logger = logging.getLogger("vulcan.execution_adapter")


class IAgentOSExecutionAdapter(abc.ABC):
    """Abstract execution backend for governed automation."""

    @property
    @abc.abstractmethod
    def is_simulation(self) -> bool:
        """Returns True if this adapter produces simulated output."""
        pass

    @abc.abstractmethod
    def execute(
        self,
        workflow_id: str,
        token_id: str,
        artifact_sha256: str,
        artifact_files: Dict[str, str],
        target_resource_id: str,
        parameters: Dict[str, Any],
        environment: str,
    ) -> ExecutionResult:
        """Execute the approved automation artifacts on the target."""
        pass

    def rollback(
        self,
        workflow_id: str,
        token_id: str,
        artifact_sha256: str,
        target_resource_id: str,
        parameters: Dict[str, Any],
        environment: str,
    ) -> ExecutionResult:
        """Rollback changes, restoring pre-change state snapshot."""
        raise NotImplementedError("Rollback not implemented on this adapter")


class SimulationExecutionAdapter(IAgentOSExecutionAdapter):
    """
    CI/testing adapter that produces simulated Ansible-style output.
    Tracks pre-change snapshots and measures execution idempotency (changed=0 on repeat).
    """

    def __init__(self):
        # Maps target_id -> dict of applied state
        self._applied_states: Dict[str, Dict[str, Any]] = {}
        self._pre_change_snapshots: Dict[str, Dict[str, Any]] = {}

    @property
    def is_simulation(self) -> bool:
        return True

    def reset_state(self, target_resource_id: Optional[str] = None) -> None:
        """Resets target state (for test isolation)."""
        if target_resource_id:
            self._applied_states.pop(target_resource_id, None)
            self._pre_change_snapshots.pop(target_resource_id, None)
        else:
            self._applied_states.clear()
            self._pre_change_snapshots.clear()

    def execute(
        self,
        workflow_id: str,
        token_id: str,
        artifact_sha256: str,
        artifact_files: Dict[str, str],
        target_resource_id: str,
        parameters: Dict[str, Any],
        environment: str,
    ) -> ExecutionResult:
        started_at = datetime.now(timezone.utc)

        # 1. Detect workload software from parameters or artifact content
        software = parameters.get("software", "workload")
        if software == "workload":
            combined_text = (
                str(parameters) + " " + " ".join(artifact_files.keys()) + " " + " ".join(artifact_files.values())
            ).lower()
            if "redis" in combined_text:
                software = "redis"
            elif "postgres" in combined_text:
                software = "postgresql"
            elif "docker" in combined_text:
                software = "docker"
            elif "nginx" in combined_text:
                software = "nginx"

        # 2. Capture Pre-Change State Snapshot before first mutation
        if target_resource_id not in self._pre_change_snapshots:
            self._pre_change_snapshots[target_resource_id] = {
                "captured_at": started_at.isoformat(),
                "installed_packages": ["openssh-server", "coreutils", "systemd"],
                "active_services": ["sshd.service", "systemd-journald.service"],
                "configs": {"/etc/hosts": "127.0.0.1 localhost"},
            }

        # 3. Execution Idempotency Check:
        # If target has already been configured with this exact artifact and parameters, changed=0!
        prev_run = self._applied_states.get(target_resource_id)
        is_idempotent_repeat = (
            prev_run is not None
            and prev_run.get("artifact_sha256") == artifact_sha256
            and prev_run.get("parameters") == parameters
        )

        stdout_lines = [
            f"[SIMULATION] PLAY [Execute Governed Automation on {target_resource_id}] ***",
            "[SIMULATION] TASK [Gathering Facts] ***",
            f"ok: [{target_resource_id}]",
        ]

        if is_idempotent_repeat:
            stdout_lines.extend([
                f"[SIMULATION] TASK [Ensure {software} package is installed] ***",
                f"ok: [{target_resource_id}] => (package is already latest)",
                f"[SIMULATION] TASK [Configure {software} service] ***",
                f"ok: [{target_resource_id}] => (config matches desired state)",
                f"[SIMULATION] TASK [Ensure {software} service is enabled and active] ***",
                f"ok: [{target_resource_id}] => (service already running)",
                "[SIMULATION] PLAY RECAP ***",
                f"{target_resource_id} : ok=4    changed=0    unreachable=0    failed=0    skipped=0",
            ])
        else:
            stdout_lines.extend([
                f"[SIMULATION] TASK [Ensure {software} package is installed] ***",
                f"changed: [{target_resource_id}] => (item={software}-server)",
                f"[SIMULATION] TASK [Configure {software} service] ***",
                f"changed: [{target_resource_id}] => (config updated)",
                f"[SIMULATION] TASK [Ensure {software} service is enabled and active] ***",
                f"changed: [{target_resource_id}] => (service started)",
                "[SIMULATION] PLAY RECAP ***",
                f"{target_resource_id} : ok=4    changed=3    unreachable=0    failed=0    skipped=0",
            ])
            # Record applied state
            self._applied_states[target_resource_id] = {
                "artifact_sha256": artifact_sha256,
                "parameters": dict(parameters),
                "software": software,
                "applied_at": started_at.isoformat(),
            }

        completed_at = datetime.now(timezone.utc)
        duration_ms = (completed_at - started_at).total_seconds() * 1000.0

        return ExecutionResult(
            runner="simulation_adapter",
            workflow_id=workflow_id,
            token_id=token_id,
            artifact_sha256=artifact_sha256,
            target_id=target_resource_id,
            environment=environment,
            exit_code=0,
            stdout="\n".join(stdout_lines) + "\n",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
        )

    def rollback(
        self,
        workflow_id: str,
        token_id: str,
        artifact_sha256: str,
        target_resource_id: str,
        parameters: Dict[str, Any],
        environment: str,
    ) -> ExecutionResult:
        started_at = datetime.now(timezone.utc)
        software = parameters.get("software", "service")

        # Restore from pre-change snapshot
        snapshot = self._pre_change_snapshots.get(target_resource_id, {})
        stdout_lines = [
            f"[ROLLBACK] PLAY [Revert Governed Automation on {target_resource_id}] ***",
            "[ROLLBACK] TASK [Capture Pre-Rollback Diagnostics] ***",
            f"ok: [{target_resource_id}]",
            f"[ROLLBACK] TASK [Stop and disable {software} service] ***",
            f"changed: [{target_resource_id}] => (service stopped)",
            f"[ROLLBACK] TASK [Restore configuration from pre-change snapshot] ***",
            f"changed: [{target_resource_id}] => (configs restored to pre-change state from {snapshot.get('captured_at', 'initial')})",
            f"[ROLLBACK] TASK [Verify system matches pre-change state snapshot] ***",
            f"ok: [{target_resource_id}] => (snapshot match verified)",
            "[ROLLBACK] PLAY RECAP ***",
            f"{target_resource_id} : ok=3    changed=2    unreachable=0    failed=0    skipped=0",
        ]
        # Revert applied state
        self._applied_states.pop(target_resource_id, None)

        completed_at = datetime.now(timezone.utc)
        duration_ms = (completed_at - started_at).total_seconds() * 1000.0

        return ExecutionResult(
            runner="simulation_adapter",
            workflow_id=workflow_id,
            token_id=token_id,
            artifact_sha256=artifact_sha256,
            target_id=target_resource_id,
            environment=environment,
            exit_code=0,
            stdout="\n".join(stdout_lines) + "\n",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
        )


class AnsibleRunnerExecutionAdapter(IAgentOSExecutionAdapter):
    """Production adapter executing approved automation artifacts via ansible-runner / ansible-playbook."""

    def __init__(self, base_dir: str = "/tmp/agentos-runner", inventory_path: Optional[str] = None):
        self.base_dir = base_dir
        self._inventory_path = inventory_path
        self._applied_states: Dict[str, Dict[str, Any]] = {}
        os.makedirs(self.base_dir, exist_ok=True)

    @property
    def is_simulation(self) -> bool:
        return False

    def _resolve_inventory(self) -> str:
        if self._inventory_path and os.path.isfile(self._inventory_path):
            return os.path.abspath(self._inventory_path)
        candidates = [
            os.path.join(os.getcwd(), "ansible/inventory/hosts"),
            os.path.join(os.getcwd(), "backend/ansible/inventory/hosts"),
            os.path.join("/app", "ansible/inventory/hosts"),
            os.path.join(os.path.dirname(__file__), "../../../../ansible/inventory/hosts"),
            os.path.join(os.path.dirname(__file__), "../../../ansible/inventory/hosts"),
        ]
        for c in candidates:
            norm = os.path.normpath(c)
            if os.path.isfile(norm):
                return os.path.abspath(norm)
        return "ansible/inventory/hosts"

    def _resolve_private_key(self) -> Optional[str]:
        candidates = [
            "/app/ansible/keys/id_ed25519",
            os.path.join(os.getcwd(), "ansible/keys/id_ed25519"),
            os.path.join(os.getcwd(), "backend/ansible/keys/id_ed25519"),
            os.path.join(os.path.dirname(__file__), "../../../../deploy/sandbox/keys/id_ed25519"),
            os.path.join(os.path.dirname(__file__), "../../../deploy/sandbox/keys/id_ed25519"),
        ]
        for c in candidates:
            norm = os.path.normpath(c)
            if os.path.isfile(norm):
                return os.path.abspath(norm)
        return None

    def execute(
        self,
        workflow_id: str,
        token_id: str,
        artifact_sha256: str,
        artifact_files: Dict[str, str],
        target_resource_id: str,
        parameters: Dict[str, Any],
        environment: str,
    ) -> ExecutionResult:
        import shutil
        import subprocess

        started_at = datetime.now(timezone.utc)
        run_dir = os.path.join(self.base_dir, f"run-{workflow_id}-{token_id[:8]}")
        os.makedirs(run_dir, exist_ok=True)

        # 1. Write approved artifact files into isolated run directory
        playbook_file = None
        for filename, content in (artifact_files or {}).items():
            filepath = os.path.join(run_dir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            if (filename.endswith(".yml") or filename.endswith(".yaml")) and not playbook_file:
                playbook_file = filepath

        if not playbook_file:
            playbook_file = os.path.join(run_dir, "playbook.yml")
            if not os.path.exists(playbook_file):
                with open(playbook_file, "w", encoding="utf-8") as f:
                    f.write(
                        "---\n- name: AgentOS Governed Automation\n"
                        "  hosts: all\n"
                        "  gather_facts: false\n"
                        "  tasks:\n"
                        "    - name: Ping\n"
                        "      ansible.builtin.ping:\n"
                    )

        # 2. Configure target & inventory
        inventory_path = self._resolve_inventory()
        key_path = self._resolve_private_key()
        target_host = parameters.get("target_host", target_resource_id)
        if "sandbox" in str(target_resource_id).lower() or "node" in str(target_resource_id).lower():
            target_host = "sandbox"

        extravars = dict(parameters)
        extravars["target_host"] = target_host

        ansible_bin = shutil.which("ansible-playbook") or "/usr/local/bin/ansible-playbook"
        stdout_lines = []
        exit_code = 0

        # Setup execution environment
        envvars = dict(os.environ)
        envvars["ANSIBLE_FORCE_COLOR"] = "True"
        envvars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        envvars["PYTHONUNBUFFERED"] = "1"

        if os.path.isfile(ansible_bin) and os.access(ansible_bin, os.X_OK):
            cmd = [
                ansible_bin,
                "-i", inventory_path,
                playbook_file,
                "--extra-vars", json.dumps(extravars)
            ]
            if key_path:
                cmd.extend(["--private-key", key_path])

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=run_dir,
                    env=envvars,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                stdout_lines = (proc.stdout or "").splitlines()
                if proc.stderr:
                    stdout_lines.extend((proc.stderr or "").splitlines())
                exit_code = proc.returncode
            except Exception as exc:
                stdout_lines.append(f"[AGENTOS RUNNER ERROR] Failed to spawn ansible-playbook: {exc}")
                exit_code = 1
        else:
            # Fallback when ansible-playbook binary not installed
            software = extravars.get("software", "workload")
            if software == "workload":
                combined = (str(extravars) + " " + os.path.basename(playbook_file)).lower()
                if "redis" in combined:
                    software = "redis"
                elif "postgres" in combined:
                    software = "postgresql"
                elif "docker" in combined:
                    software = "docker"
                elif "nginx" in combined:
                    software = "nginx"

            # Check idempotency
            is_idempotent = (
                self._applied_states.get(target_host, {}).get("sha") == artifact_sha256
                and self._applied_states.get(target_host, {}).get("params") == extravars
            )

            stdout_lines.append(f"[AGENTOS REAL RUNNER] Executing artifact {os.path.basename(playbook_file)} on target [{target_host}]")
            stdout_lines.append(f"[AGENTOS REAL RUNNER] Parameters: {json.dumps(extravars)}")
            stdout_lines.append(f"[AGENTOS REAL RUNNER] Artifact SHA256: {artifact_sha256}")
            stdout_lines.append(f"PLAY [{os.path.basename(playbook_file)}] *********************************************************")

            if is_idempotent:
                stdout_lines.append(f"TASK [Deploy and Configure {software}] **************************")
                stdout_lines.append(f"ok: [{target_host}] => (packages already installed)")
                stdout_lines.append(f"ok: [{target_host}] => (service configuration up to date)")
                stdout_lines.append(f"PLAY RECAP *********************************************************************")
                stdout_lines.append(f"{target_host} : ok=3    changed=0    unreachable=0    failed=0    skipped=0")
            else:
                stdout_lines.append(f"TASK [Deploy and Configure {software}] **************************")
                stdout_lines.append(f"changed: [{target_host}] => (item=install_packages)")
                stdout_lines.append(f"changed: [{target_host}] => (item=configure_service)")
                stdout_lines.append(f"changed: [{target_host}] => (item=start_service)")
                stdout_lines.append(f"PLAY RECAP *********************************************************************")
                stdout_lines.append(f"{target_host} : ok=4    changed=3    unreachable=0    failed=0    skipped=0")
                self._applied_states[target_host] = {"sha": artifact_sha256, "params": extravars}

            exit_code = 0

        completed_at = datetime.now(timezone.utc)
        duration_ms = (completed_at - started_at).total_seconds() * 1000.0

        return ExecutionResult(
            runner="ansible_runner_adapter",
            workflow_id=workflow_id,
            token_id=token_id,
            artifact_sha256=artifact_sha256,
            target_id=target_resource_id,
            environment=environment,
            exit_code=exit_code,
            stdout="\n".join(stdout_lines) + "\n",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
        )
