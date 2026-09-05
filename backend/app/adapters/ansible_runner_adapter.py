"""
Project Vulcan: Ansible Runner Adapter
Author: Uncle Bob & Alex Xu
Integrates ansible-runner via IExecutionEngine port.
"""
import logging
from typing import Callable, Dict
from app.domain.entities import EngineExecutionResult, ExecutionJob
from app.ports.interfaces import IExecutionEngine

logger = logging.getLogger("vulcan.ansible")


class AnsibleRunnerExecutionEngine(IExecutionEngine):
    """
    Adapter executing Ansible playbooks via ansible-runner.
    """

    def __init__(self, private_data_dir: str = "/tmp/vulcan-ansible"):
        self.private_data_dir = private_data_dir

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

        def event_handler(event_data):
            if "stdout" in event_data:
                line = event_data["stdout"]
                if line:
                    event_callback(line)

        r = ansible_runner.run(
            private_data_dir=self.private_data_dir,
            playbook=job.catalog_item.playbook_or_module_path,
            extravars=job.parameters,
            event_handler=event_handler
        )

        return EngineExecutionResult(
            status="SUCCESS" if r.rc == 0 else "FAILED",
            exit_code=r.rc,
            stdout=r.stdout.read() if hasattr(r.stdout, "read") else str(r.stdout)
        )
