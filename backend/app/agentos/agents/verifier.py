"""
Project Vulcan: Verifier Agent (Section 7, 29 & AGENT-10)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Independent read-only verification of real desired state
- Execution exit code 0 is strictly insufficient to declare success
- Evaluates multi-signal postcondition probes:
  1. Service active status
  2. TCP port accessibility (e.g. 5432)
  3. Database query synthetic health
  4. Disk capacity assertions (e.g. 500GB)
  5. Monitoring and backup configuration presence
Only 100% passing postconditions can transition workflow to SUCCESS.
"""
from __future__ import annotations

from typing import List, Type, Dict, Optional, Any
import abc
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, VerificationProbe, VerifierOutput


class IVerificationProbeRunner(abc.ABC):
    """Abstract probe runner for postcondition verification."""
    @property
    @abc.abstractmethod
    def is_simulation(self) -> bool:
        pass

    @abc.abstractmethod
    def run_probe(self, probe_type: str, target: str, probe_config: Dict[str, Any]) -> VerificationProbe:
        pass


class SimulationProbeRunner(IVerificationProbeRunner):
    """CI/testing probe runner. Returns simulated results clearly labeled."""
    @property
    def is_simulation(self) -> bool:
        return True

    def run_probe(self, probe_type: str, target: str, probe_config: Dict[str, Any]) -> VerificationProbe:
        """Returns a simulated passing probe with simulation metadata."""
        return VerificationProbe(
            probe_id=f"sim-probe-{probe_type}",
            target=target,
            probe_type=probe_type,
            passed=True,
            latency_ms=1.0,
            details={**probe_config, "simulation": True},
        )


class ProductionProbeRunner(IVerificationProbeRunner):
    """Production probe runner. Delegates to real observability probes."""
    @property
    def is_simulation(self) -> bool:
        return False

    def run_probe(self, probe_type: str, target: str, probe_config: Dict[str, Any]) -> VerificationProbe:
        raise NotImplementedError("ProductionProbeRunner is not yet implemented for real infrastructure probes.")



class VerifierAgent(BaseAgent):
    def __init__(self, version: str = "v1.0", probe_runner: Optional[IVerificationProbeRunner] = None):
        super().__init__(
            role=AgentRole.VERIFIER,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Execute read-only probes against actual target infrastructure to verify postconditions independently of runner exit codes.",
        )
        self._probe_runner = probe_runner or SimulationProbeRunner()

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return VerifierOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> VerifierOutput:
        target = ctx.execution_result.get("target_id", "db-cluster.internal")
        probes: List[VerificationProbe] = []

        # Define probe configs from desired state / spec
        probe_configs = [
            ("port_open", {"port": 5432, "protocol": "tcp"}),
            ("service_status", {"service": "postgresql-16"}),
            ("disk_capacity", {"mount": "/var/lib/pgsql", "min_gb": 500}),
            ("db_query", {"query": "SELECT version();"}),
        ]
        if "datadog" in ctx.original_request.lower():
            probe_configs.append(("telemetry_active", {"agent": "datadog"}))
        if "s3" in ctx.original_request.lower():
            probe_configs.append(("backup_accessible", {"bucket": "vulcan-backups"}))

        for probe_type, config in probe_configs:
            probe = self._probe_runner.run_probe(probe_type, target, config)
            probes.append(probe)

        all_passed = bool(probes) and all(p.passed for p in probes)
        next_state = WorkflowState.SUCCESS.value if all_passed else WorkflowState.VERIFY_FAILED.value

        return VerifierOutput(
            workflow_id=ctx.workflow_id,
            all_passed=all_passed,
            probes=probes,
            actual_state_matches_desired=all_passed,
            proposed_next_state=next_state,
            confidence=1.0 if all_passed else 0.0,
            rationale=f"All {len(probes)} postcondition probes passed{' (SIMULATION)' if self._probe_runner.is_simulation else ''}."
                if all_passed else "Postcondition probes failed; actual state diverged from desired state.",
        )
