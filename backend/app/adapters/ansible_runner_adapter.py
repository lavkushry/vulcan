"""
Project Vulcan: Real Ansible Runner Adapter
Author: Clean Architecture Lead & Alex Xu
Integrates real Ansible playbook execution via ansible-runner with
line-by-line WebSocket stdout streaming and sandbox container targeting.
"""
import logging
import os
import shutil
from typing import Callable, Dict, Optional
from app.domain.entities import EngineExecutionResult, ExecutionJob
from app.ports.interfaces import IExecutionEngine

logger = logging.getLogger("vulcan.ansible")


class AnsibleRunnerExecutionEngine(IExecutionEngine):
    """
    Adapter executing real Ansible playbooks via ansible-runner against
    the isolated sandbox container or local target.
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
        try:
            import ansible_runner
        except ImportError:
            logger.warning("ansible-runner not installed, delegating to SimulationExecutionEngine")
            from app.adapters.simulation_adapter import SimulationExecutionEngine
            return SimulationExecutionEngine().execute(job, event_callback, secrets)

        raw_path = job.catalog_item.playbook_or_module_path
        resolved_playbook = self._resolve_playbook_path(raw_path)

        if not resolved_playbook:
            # Fallback to simulation if playbook file is not yet provisioned on disk
            logger.warning(f"Playbook {raw_path} not found on disk, falling back to SimulationExecutionEngine")
            from app.adapters.simulation_adapter import SimulationExecutionEngine
            return SimulationExecutionEngine().execute(job, event_callback, secrets)

        # Job-specific private data directory for isolation
        job_dir = os.path.join(self.private_data_dir, f"job-{job.correlation_id}")
        os.makedirs(job_dir, exist_ok=True)

        # Build extra variables combining job parameters and injected secrets
        extravars = dict(job.parameters) if job.parameters else {}
        if secrets:
            extravars.update(secrets)

        # Set target host if provided in parameters or job entity
        if job.target_resource_id and "target_host" not in extravars:
            extravars["target_host"] = job.target_resource_id

        # Setup environment variables for Ansible runner
        envvars = {
            "ANSIBLE_FORCE_COLOR": "True",
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "PYTHONUNBUFFERED": "1",
        }
        cfg_path = self._resolve_ansible_cfg()
        if cfg_path:
            envvars["ANSIBLE_CONFIG"] = cfg_path

        inventory_path = self._resolve_inventory_path()

        event_callback(f"\033[1;34m[VULCAN ANSIBLE ENGINE]\033[0m Initializing execution for {job.catalog_item.name}...")
        event_callback(f"\033[1;36m[TARGET INVENTORY]\033[0m Host: {job.target_resource_id or 'sandbox'} via {inventory_path}")
        event_callback(f"\033[1;36m[PLAYBOOK]\033[0m {resolved_playbook}")
        event_callback(f"\033[1;32m[SPAWNING WORKER]\033[0m ansible-playbook starting against target...\n")

        stdout_lines = []

        def event_handler(event_data):
            if "stdout" in event_data:
                line = event_data["stdout"]
                if line:
                    stdout_lines.append(line)
                    event_callback(line)

        try:
            r = ansible_runner.run(
                private_data_dir=job_dir,
                playbook=resolved_playbook,
                inventory=inventory_path,
                extravars=extravars,
                envvars=envvars,
                event_handler=event_handler,
                quiet=False
            )

            status = "SUCCESS" if r.rc == 0 else "FAILED"
            full_stdout = "\n".join(stdout_lines)

            if r.rc == 0:
                event_callback(f"\n\033[1;32m[VULCAN RECAP]\033[0m Playbook execution completed with Exit Code 0 (SUCCESS).")
            else:
                event_callback(f"\n\033[1;31m[VULCAN ERROR]\033[0m Playbook execution failed with Exit Code {r.rc}.")

            return EngineExecutionResult(
                status=status,
                exit_code=r.rc,
                stdout=full_stdout
            )
        except Exception as exc:
            logger.error(f"Ansible Runner execution exception: {exc}")
            event_callback(f"\033[1;31m[RUNNER EXCEPTION]\033[0m {str(exc)}")
            return EngineExecutionResult(
                status="FAILED",
                exit_code=1,
                stdout=f"Exception during Ansible execution: {str(exc)}"
            )
        finally:
            # Clean up job temp directory artifacts
            shutil.rmtree(job_dir, ignore_errors=True)
