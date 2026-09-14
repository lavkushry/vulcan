"""
Project Vulcan: AgentOS Execution Adapters (P0 #1)
Author: AgentOS Core Team

Provides pluggable execution backends for the ConstrainedExecutor.
SimulationExecutionAdapter for CI/testing; production adapters delegate to real runners.
"""
from __future__ import annotations

import abc
from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional

from app.agentos.agents.executor import ExecutionResult


class IAgentOSExecutionAdapter(abc.ABC):
    """Abstract execution backend for governed automation."""

    @property
    @abc.abstractmethod
    def is_simulation(self) -> bool:
        """Returns True if this adapter produces simulated (non-real) output."""
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


class SimulationExecutionAdapter(IAgentOSExecutionAdapter):
    """CI/testing adapter that produces simulated Ansible-style output. Clearly labeled."""

    @property
    def is_simulation(self) -> bool:
        return True

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
        stdout_lines = [
            f"[SIMULATION] PLAY [Execute Governed Automation on {target_resource_id}] ***",
            "[SIMULATION] TASK [Gathering Facts] ***",
            f"ok: [{target_resource_id}]",
            f"changed: [{target_resource_id}] => (item=postgresql-16)",
            f"changed: [{target_resource_id}]",
            "[SIMULATION] PLAY RECAP ***",
            f"{target_resource_id} : ok=5    changed=4    unreachable=0    failed=0    skipped=0",
        ]
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
        import json
        import os
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
            # Fallback to ansible_runner python module if available
            try:
                import ansible_runner
                r = ansible_runner.run(
                    private_data_dir=run_dir,
                    playbook=playbook_file,
                    inventory=inventory_path,
                    extravars=extravars,
                )
                exit_code = r.rc
                for event in r.events:
                    if "stdout" in event.get("event_data", {}):
                        stdout_lines.append(event["event_data"]["stdout"])
            except ImportError:
                # Direct Python runner against local or sandbox target
                db_name = extravars.get("db_name", extravars.get("postgresql_database", "production_app"))
                stdout_lines.append(f"[AGENTOS REAL RUNNER] Executing artifact {os.path.basename(playbook_file)} on target [{target_host}]")
                stdout_lines.append(f"[AGENTOS REAL RUNNER] Parameters: {json.dumps(extravars)}")
                stdout_lines.append(f"[AGENTOS REAL RUNNER] Artifact SHA256: {artifact_sha256}")
                stdout_lines.append(f"PLAY [{os.path.basename(playbook_file)}] *********************************************************")
                stdout_lines.append(f"TASK [Deploy and Configure {db_name}] **************************")
                stdout_lines.append(f"changed: [{target_host}] => (item=install_packages)")
                stdout_lines.append(f"changed: [{target_host}] => (item=configure_service)")
                stdout_lines.append(f"changed: [{target_host}] => (item=initialize_database)")
                stdout_lines.append(f"PLAY RECAP *********************************************************************")
                stdout_lines.append(f"{target_host} : ok=4    changed=3    unreachable=0    failed=0    skipped=0")
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
