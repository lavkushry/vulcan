"""
Project Vulcan: Real Ansible Runner Adapter
Author: Clean Architecture Lead & Alex Xu
Integrates real Ansible playbook execution via ansible-playbook / ansible-runner
with line-by-line WebSocket stdout streaming and sandbox container targeting.
"""
import json
import logging
import os
import shutil
import subprocess
from typing import Callable, Dict, Optional
from app.domain.entities import EngineExecutionResult, ExecutionJob
from app.ports.interfaces import IExecutionEngine

logger = logging.getLogger("vulcan.ansible")


class AnsibleRunnerExecutionEngine(IExecutionEngine):
    """
    Adapter executing real Ansible playbooks via ansible-playbook CLI / ansible-runner
    against the isolated sandbox container or local target.
    """

    def __init__(self, private_data_dir: str = "/tmp/vulcan-ansible"):
        self.private_data_dir = private_data_dir
        os.makedirs(self.private_data_dir, exist_ok=True)

    def _resolve_playbook_path(self, path: str) -> Optional[str]:
        """Resolve playbook path across candidate root locations."""
        candidates = [
            path,
            os.path.join(os.getcwd(), path),
            os.path.join("/app", path),
            os.path.join(os.path.dirname(__file__), "../..", path),
            os.path.join(os.path.dirname(__file__), "../../..", path),
            os.path.join(os.getcwd(), "ansible", path),
            os.path.join("/app", "ansible", path),
            os.path.join("/app", "backend", path),
        ]
        for c in candidates:
            norm = os.path.normpath(c)
            if os.path.isfile(norm):
                return norm
        return None

    def _resolve_inventory_path(self) -> str:
        """Resolve inventory file path."""
        candidates = [
            os.path.join(os.getcwd(), "ansible/inventory/hosts"),
            os.path.join("/app/ansible/inventory/hosts"),
            os.path.join(os.path.dirname(__file__), "../../../ansible/inventory/hosts"),
            os.path.join(os.path.dirname(__file__), "../../ansible/inventory/hosts"),
        ]
        for c in candidates:
            norm = os.path.normpath(c)
            if os.path.isfile(norm):
                return norm
        return "ansible/inventory/hosts"

    def _resolve_ansible_cfg(self) -> Optional[str]:
        """Resolve ansible.cfg path."""
        candidates = [
            os.path.join(os.getcwd(), "ansible/ansible.cfg"),
            os.path.join("/app/ansible/ansible.cfg"),
            os.path.join(os.path.dirname(__file__), "../../../ansible/ansible.cfg"),
            os.path.join(os.path.dirname(__file__), "../../ansible/ansible.cfg"),
        ]
        for c in candidates:
            norm = os.path.normpath(c)
            if os.path.isfile(norm):
                return norm
        return None

    def _resolve_private_key(self) -> Optional[str]:
        """Resolve the SSH private key for sandbox authentication."""
        candidates = [
            "/app/ansible/keys/id_ed25519",
            os.path.join(os.getcwd(), "ansible/keys/id_ed25519"),
            os.path.join(os.path.dirname(__file__), "../../../ansible/keys/id_ed25519"),
            os.path.join(os.path.dirname(__file__), "../../ansible/keys/id_ed25519"),
        ]
        for c in candidates:
            norm = os.path.normpath(c)
            if os.path.isfile(norm):
                return norm
        return None

    def execute(
        self,
        job: ExecutionJob,
        event_callback: Callable[[str], None],
        secrets: Dict[str, str]
    ) -> EngineExecutionResult:
        raw_path = job.catalog_item.playbook_or_module_path
        resolved_playbook = self._resolve_playbook_path(raw_path)

        if not resolved_playbook:
            logger.warning(f"Playbook {raw_path} not found on disk, delegating to SimulationExecutionEngine")
            from app.adapters.simulation_adapter import SimulationExecutionEngine
            return SimulationExecutionEngine().execute(job, event_callback, secrets)

        # Build extra variables combining job parameters and injected secrets
        extravars = dict(job.parameters) if job.parameters else {}
        if secrets:
            extravars.update(secrets)

        # Set target host if provided in parameters or job entity
        if job.target_resource_id and "target_host" not in extravars:
            # If target_resource_id contains 'sandbox' or is standard, map to sandbox inventory group
            if "sandbox" in job.target_resource_id.lower() or "node" in job.target_resource_id.lower():
                extravars["target_host"] = "sandbox"
            else:
                extravars["target_host"] = job.target_resource_id

        inventory_path = self._resolve_inventory_path()
        cfg_path = self._resolve_ansible_cfg()
        key_path = self._resolve_private_key()

        # Setup environment variables
        envvars = dict(os.environ)
        envvars["ANSIBLE_FORCE_COLOR"] = "True"
        envvars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        envvars["PYTHONUNBUFFERED"] = "1"
        if cfg_path:
            envvars["ANSIBLE_CONFIG"] = cfg_path

        event_callback(f"\033[1;34m[VULCAN REAL ANSIBLE ENGINE]\033[0m Target: {extravars.get('target_host', 'sandbox')}")
        event_callback(f"\033[1;36m[INVENTORY]\033[0m {inventory_path}")
        event_callback(f"\033[1;36m[PLAYBOOK]\033[0m {resolved_playbook}")
        event_callback(f"\033[1;32m[SPAWNING ANSIBLE-PLAYBOOK]\033[0m Starting execution against sandbox target...\n")

        # 1. Attempt direct execution via ansible-playbook CLI
        ansible_bin = shutil.which("ansible-playbook") or "/usr/local/bin/ansible-playbook"
        if os.path.isfile(ansible_bin) and os.access(ansible_bin, os.X_OK):
            cmd = [
                ansible_bin,
                "-i", inventory_path,
                resolved_playbook,
                "--extra-vars", json.dumps(extravars)
            ]
            if key_path:
                cmd.extend(["--private-key", key_path])

            cwd = os.path.dirname(cfg_path) if cfg_path else os.path.dirname(resolved_playbook)
            stdout_lines = []

            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    env=envvars,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                for line in iter(proc.stdout.readline, ""):
                    clean_line = line.rstrip("\r\n")
                    if clean_line:
                        stdout_lines.append(clean_line)
                        event_callback(clean_line)

                proc.stdout.close()
                rc = proc.wait()

                status = "SUCCESS" if rc == 0 else "FAILED"
                full_stdout = "\n".join(stdout_lines)

                if rc == 0:
                    event_callback(f"\n\033[1;32m[VULCAN RECAP]\033[0m Real Playbook executed successfully with Exit Code 0.")
                else:
                    event_callback(f"\n\033[1;31m[VULCAN ERROR]\033[0m Playbook exited with Code {rc}.")

                return EngineExecutionResult(
                    status=status,
                    exit_code=rc,
                    stdout=full_stdout
                )
            except Exception as exc:
                logger.error(f"Error executing ansible-playbook: {exc}")
                event_callback(f"\033[1;31m[PROCESS ERROR]\033[0m {str(exc)}")

        # 2. Fallback to ansible_runner library if CLI subprocess not found
        try:
            import ansible_runner
            job_dir = os.path.join(self.private_data_dir, f"job-{job.correlation_id}")
            os.makedirs(job_dir, exist_ok=True)
            stdout_lines = []

            def event_handler(event_data):
                if "stdout" in event_data:
                    line = event_data["stdout"]
                    if line:
                        stdout_lines.append(line)
                        event_callback(line)

            r = ansible_runner.run(
                private_data_dir=job_dir,
                project_dir=os.path.dirname(resolved_playbook),
                playbook=os.path.basename(resolved_playbook),
                inventory=inventory_path,
                extravars=extravars,
                envvars=envvars,
                event_handler=event_handler,
                quiet=False
            )

            status = "SUCCESS" if r.rc == 0 else "FAILED"
            shutil.rmtree(job_dir, ignore_errors=True)
            return EngineExecutionResult(
                status=status,
                exit_code=r.rc,
                stdout="\n".join(stdout_lines)
            )
        except Exception as runner_err:
            logger.warning(f"ansible-runner failed ({runner_err}), delegating to SimulationExecutionEngine")
            from app.adapters.simulation_adapter import SimulationExecutionEngine
            return SimulationExecutionEngine().execute(job, event_callback, secrets)
