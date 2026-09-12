"""
Project Vulcan: AgentOS Execution Adapters (P0 #1)
Author: AgentOS Core Team

Provides pluggable execution backends for the ConstrainedExecutor.
SimulationExecutionAdapter for CI/testing; production adapters delegate to real runners.
"""
from __future__ import annotations

import abc
from datetime import datetime, timezone
from typing import Any, Dict

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
    """Production adapter skeleton for ansible-runner. Wire to real infrastructure."""

    @property
    def is_simulation(self) -> bool:
        return False

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
        # TODO: Wire to actual ansible-runner subprocess
        raise NotImplementedError(
            "AnsibleRunnerExecutionAdapter requires ansible-runner to be installed and configured. "
            "Use SimulationExecutionAdapter for CI/testing."
        )
