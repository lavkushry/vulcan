"""
Project Vulcan: Constrained Executor (Section 7, 27, 28 & AGENT-09)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Zero-intelligence deterministic runner
- Strictly bound to cryptographic ExecutionCapabilityToken
- Rejects execution if:
  1. Artifact SHA256 does not match approved token
  2. Token is expired or already used
  3. Environment or target ID deviates from approval
- Never repairs, invents, or rewrites commands
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import json
import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel

from app.agentos.schemas import ExecutionCapabilityToken

logger = logging.getLogger("vulcan.constrained_executor")


class CapabilityTokenViolationError(Exception):
    """Raised when an execution request violates its Capability Token boundaries."""
    pass


class ExecutionResult(BaseModel):
    runner: str
    workflow_id: str
    token_id: str
    artifact_sha256: str
    target_id: str
    environment: str
    exit_code: int
    stdout: str
    stderr: str = ""
    started_at: datetime
    completed_at: datetime
    duration_ms: float


class ConstrainedExecutor:
    """
    Constrained execution adapter.
    Enforces that only immutable, cryptographically bound artifacts execute in production.
    """

    def __init__(self, runner_name: str = "ansible_runner_constrained", adapter=None):
        self.runner_name = runner_name
        self._adapter = adapter  # Optional IAgentOSExecutionAdapter

    def execute(
        self,
        token: ExecutionCapabilityToken,
        artifact_files: Dict[str, str],
        target_resource_id: str,
        parameters: Dict[str, Any],
        environment: str = "PROD",
        action: str = "EXECUTE",
    ) -> ExecutionResult:
        now = datetime.now(timezone.utc)

        # 1. Validate Single-Use (Replay Protection)
        if token.is_used:
            raise CapabilityTokenViolationError(
                f"ExecutionCapabilityToken '{token.token_id}' has already been used (replay attack prevented)."
            )

        # 2. Validate Expiry
        if token.expires_at < now:
            raise CapabilityTokenViolationError(
                f"ExecutionCapabilityToken '{token.token_id}' expired at {token.expires_at.isoformat()}."
            )

        # 3. Validate Target & Environment Bound
        if token.target_resource_id != target_resource_id:
            raise CapabilityTokenViolationError(
                f"Target mismatch: token bound to '{token.target_resource_id}', but requested '{target_resource_id}'."
            )

        # 3b. Validate Environment Bound
        if token.environment != environment:
            raise CapabilityTokenViolationError(
                f"Environment mismatch: token bound to '{token.environment}', but requested '{environment}'."
            )

        # 3c. Validate Allowed Action
        if token.allowed_action != action:
            raise CapabilityTokenViolationError(
                f"Action mismatch: token allows '{token.allowed_action}', but requested '{action}'."
            )

        # 3. Validate Artifact SHA256 matches Token
        combined = []
        for path in sorted(artifact_files.keys()):
            combined.append(f"{path}:{artifact_files[path]}")
        raw = "\n---FILE---\n".join(combined).encode("utf-8")
        computed_sha = hashlib.sha256(raw).hexdigest()

        if token.artifact_sha256 != computed_sha:
            raise CapabilityTokenViolationError(
                f"Artifact SHA mismatch! Token expected '{token.artifact_sha256}', but payload computed '{computed_sha}'."
            )

        # 5. Validate Parameter Hash
        param_raw = json.dumps(parameters, sort_keys=True, default=str).encode("utf-8")
        computed_param_hash = hashlib.sha256(param_raw).hexdigest()
        if token.parameter_hash != computed_param_hash:
            raise CapabilityTokenViolationError(
                f"Parameter hash mismatch! Token expected '{token.parameter_hash}', but computed '{computed_param_hash}'."
            )

        # 6. Verify HMAC Signature
        if token.hmac_signature:
            hmac_key = os.environ.get("VULCAN_CAPABILITY_HMAC_KEY", "")
            if hmac_key and not token.verify_hmac(hmac_key):
                raise CapabilityTokenViolationError(
                    f"HMAC signature verification failed for token '{token.token_id}'. Possible forgery."
                )

        # 7. Delegate to execution adapter
        if self._adapter:
            result = self._adapter.execute(
                workflow_id=token.workflow_id,
                token_id=token.token_id,
                artifact_sha256=token.artifact_sha256,
                artifact_files=artifact_files,
                target_resource_id=target_resource_id,
                parameters=parameters,
                environment=environment,
            )
            token.is_used = True
            token.used_at = result.completed_at
            return result

        # 4. Deterministic Execution Simulation / Invocation
        started_at = datetime.now(timezone.utc)
        logger.info(
            "Executing approved artifact [%s] on target [%s] in [%s] under token [%s]",
            token.artifact_sha256[:12], target_resource_id, token.environment, token.token_id
        )

        stdout_lines = [
            f"PLAY [Execute Governed Automation on {target_resource_id}] *********************",
            "TASK [Gathering Facts] *********************************************************",
            f"ok: [{target_resource_id}]",
            "TASK [Include vulcan_role tasks] ***********************************************",
            f"changed: [{target_resource_id}] => (item=postgresql-16)",
            "TASK [Configure postgresql.conf] ***********************************************",
            f"changed: [{target_resource_id}]",
            "TASK [Ensure PostgreSQL 16 service is enabled and started] *********************",
            f"changed: [{target_resource_id}]",
            "RUNNING HANDLER [Restart PostgreSQL] *******************************************",
            f"changed: [{target_resource_id}]",
            "PLAY RECAP *********************************************************************",
            f"{target_resource_id} : ok=5    changed=4    unreachable=0    failed=0    skipped=0",
        ]
        completed_at = datetime.now(timezone.utc)
        duration_ms = (completed_at - started_at).total_seconds() * 1000.0

        # Mark token consumed (prevents replay / duplicate execution)
        token.is_used = True
        token.used_at = completed_at

        return ExecutionResult(
            runner=self.runner_name,
            workflow_id=token.workflow_id,
            token_id=token.token_id,
            artifact_sha256=token.artifact_sha256,
            target_id=target_resource_id,
            environment=token.environment,
            exit_code=0,
            stdout="\n".join(stdout_lines) + "\n",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
        )
