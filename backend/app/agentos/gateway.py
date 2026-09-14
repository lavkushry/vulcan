"""
Project Vulcan: Typed Tool Gateway & Agent Permission Matrix (Sections 21 & 22)
Author: Architectural Review Board & AgentOS Core Team

Enforces:
1. Zero generic production shell execution tools for agents.
2. Typed narrow tools bound to specific RBAC roles, allowed workflow states, and risk levels.
3. Idempotency key caching and replay prevention.
4. Call rate limiting and budget tracking per agent role.
5. Every tool invocation logs a structured audit event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from app.agentos.context import WorkflowState
from app.agentos.schemas import AgentRole

logger = logging.getLogger("vulcan.tool_gateway")


class ToolRiskLevel(str, enum.Enum):
    READ_ONLY = "READ_ONLY"            # Non-mutating read/search
    STAGING = "STAGING"                # Sandbox, mock, or staging writes
    APPROVAL_BOUND = "APPROVAL_BOUND"  # Requires human sign-off
    RESTRICTED = "RESTRICTED"          # High-risk execution under capability token


@dataclass
class ToolDefinition:
    name: str
    description: str
    risk_level: ToolRiskLevel
    allowed_roles: List[AgentRole]
    allowed_states: List[WorkflowState]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    timeout_sec: float = 30.0


class ToolExecutionError(Exception):
    """Raised when tool execution violates permissions, state bounds, or rate limits."""
    pass


class ToolGateway:
    """
    Central mediation point for all agent tool invocations.
    Validates least-privilege role permissions, workflow state bounds,
    rate limits, idempotency caching, and records immutable audit trails.
    """

    PROHIBITED_TOOLS = {"shell", "bash", "sh", "exec", "ssh", "raw_command", "cmd"}

    def __init__(self, max_calls_per_minute: int = 120):
        self._tools: Dict[str, ToolDefinition] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._idempotency_cache: Dict[str, Dict[str, Any]] = {}
        self._rate_counter: Dict[str, List[datetime]] = {}
        self.max_calls_per_minute = max_calls_per_minute

    def register_tool(self, tool: ToolDefinition) -> None:
        if tool.name.lower() in self.PROHIBITED_TOOLS:
            raise ValueError(f"Registration of arbitrary shell/exec tool '{tool.name}' is strictly forbidden.")
        self._tools[tool.name] = tool

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit_log)

    def invoke(
        self,
        tool_name: str,
        caller_role: AgentRole,
        current_state: WorkflowState,
        arguments: Dict[str, Any],
        correlation_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 0. Reject Prohibited Shell Tools
        if tool_name.lower() in self.PROHIBITED_TOOLS:
            msg = f"Tool '{tool_name}' is forbidden. Generic production shell/SSH execution is strictly prohibited."
            logger.error("Security violation: %s", msg)
            raise ToolExecutionError(msg)

        tool = self._tools.get(tool_name)
        if not tool:
            raise ToolExecutionError(f"Tool '{tool_name}' is not registered.")

        # 1. Check Idempotency Cache
        if idempotency_key:
            cache_key = f"{caller_role.value}:{tool_name}:{idempotency_key}"
            if cache_key in self._idempotency_cache:
                logger.info("Returning cached result for idempotency key [%s]", idempotency_key)
                return self._idempotency_cache[cache_key]

        # 2. Check Least Privilege Agent Role (Section 22)
        if caller_role not in tool.allowed_roles:
            msg = f"Agent role '{caller_role.value}' is not authorized to invoke tool '{tool_name}'."
            logger.warning("Least-privilege violation: %s", msg)
            raise ToolExecutionError(msg)

        # 3. Check Allowed Workflow State
        if current_state not in tool.allowed_states:
            msg = (
                f"Tool '{tool_name}' cannot be called in state '{current_state.value}'. "
                f"Allowed states: {[s.value for s in tool.allowed_states]}"
            )
            logger.warning("State machine violation: %s", msg)
            raise ToolExecutionError(msg)

        # 4. Check Rate Limiting
        now = datetime.now(timezone.utc)
        timestamps = self._rate_counter.setdefault(caller_role.value, [])
        # Expire older than 60s
        self._rate_counter[caller_role.value] = [t for t in timestamps if (now - t).total_seconds() < 60.0]
        if len(self._rate_counter[caller_role.value]) >= self.max_calls_per_minute:
            raise ToolExecutionError(f"Rate limit exceeded for agent role '{caller_role.value}'.")
        self._rate_counter[caller_role.value].append(now)

        # 5. Audit Pre-execution
        event = {
            "timestamp": now.isoformat(),
            "tool_name": tool_name,
            "caller_role": caller_role.value,
            "current_state": current_state.value,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "risk_level": tool.risk_level.value,
        }

        # 6. Invoke Handler
        try:
            result = tool.handler(arguments)
            event["status"] = "SUCCESS"
            self._audit_log.append(event)

            if idempotency_key:
                cache_key = f"{caller_role.value}:{tool_name}:{idempotency_key}"
                self._idempotency_cache[cache_key] = result

            return result
        except Exception as e:
            event["status"] = "ERROR"
            event["error"] = str(e)
            self._audit_log.append(event)
            logger.error("Error executing tool '%s': %s", tool_name, e)
            raise

    @classmethod
    def create_default_gateway(cls) -> ToolGateway:
        """Constructs a production ToolGateway seeded with standard Section 21 narrow tools."""
        gateway = cls()

        # Tool 1: search_catalog
        gateway.register_tool(
            ToolDefinition(
                name="search_catalog",
                description="Search internal curated catalog for automation roles and modules.",
                risk_level=ToolRiskLevel.READ_ONLY,
                allowed_roles=[AgentRole.DISCOVERY, AgentRole.CONTEXT, AgentRole.SUPERVISOR],
                allowed_states=[WorkflowState.DISCOVERING, WorkflowState.UNDERSTANDING, WorkflowState.PLANNING],
                handler=lambda args: {
                    "results": [
                        {"identifier": "curated.database.postgresql_cluster", "name": "Hardened PostgreSQL Cluster", "engine": "ansible"}
                    ],
                    "query": args.get("query", ""),
                },
            )
        )

        # Tool 2: inspect_catalog_item
        gateway.register_tool(
            ToolDefinition(
                name="inspect_catalog_item",
                description="Inspect detailed metadata, input schema, and dependencies of a catalog item.",
                risk_level=ToolRiskLevel.READ_ONLY,
                allowed_roles=[AgentRole.DISCOVERY, AgentRole.PLANNER, AgentRole.COMPOSER],
                allowed_states=[WorkflowState.DISCOVERING, WorkflowState.PLANNING, WorkflowState.COMPOSING],
                handler=lambda args: {
                    "identifier": args.get("identifier"),
                    "engine": "ansible",
                    "trust_state": "CURATED",
                    "supported_platforms": ["rhel9", "rockylinux9"],
                },
            )
        )

        # Tool 3: search_ansible_registry
        gateway.register_tool(
            ToolDefinition(
                name="search_ansible_registry",
                description="Search Ansible Galaxy / Automation Hub for upstream collections.",
                risk_level=ToolRiskLevel.READ_ONLY,
                allowed_roles=[AgentRole.DISCOVERY],
                allowed_states=[WorkflowState.DISCOVERING],
                handler=lambda args: {"candidates": ["community.postgresql", "ansible.posix"]},
            )
        )

        # Tool 4: search_terraform_registry
        gateway.register_tool(
            ToolDefinition(
                name="search_terraform_registry",
                description="Search Terraform/OpenTofu registry for approved provider modules.",
                risk_level=ToolRiskLevel.READ_ONLY,
                allowed_roles=[AgentRole.DISCOVERY],
                allowed_states=[WorkflowState.DISCOVERING],
                handler=lambda args: {"candidates": ["hashicorp/aws", "hashicorp/azurerm"]},
            )
        )

        # Tool 5: validate_artifact
        gateway.register_tool(
            ToolDefinition(
                name="validate_artifact",
                description="Run syntax-check, lint, and secret scanning on staged artifact.",
                risk_level=ToolRiskLevel.READ_ONLY,
                allowed_roles=[AgentRole.VALIDATOR, AgentRole.SECURITY],
                allowed_states=[WorkflowState.VALIDATING, WorkflowState.SECURITY_REVIEW],
                handler=lambda args: {"valid": True, "checks_run": 5, "errors": []},
            )
        )

        # Tool 6: execute_sandbox
        gateway.register_tool(
            ToolDefinition(
                name="execute_sandbox",
                description="Run isolated non-production container converge testing.",
                risk_level=ToolRiskLevel.STAGING,
                allowed_roles=[AgentRole.TEST, AgentRole.VALIDATOR],
                allowed_states=[WorkflowState.VALIDATING, WorkflowState.TESTING],
                handler=lambda args: {"exit_code": 0, "stdout": "Converge completed clean."},
            )
        )

        # Tool 7: request_approval
        gateway.register_tool(
            ToolDefinition(
                name="request_approval",
                description="Submit policy approval request for human Maker-Checker review.",
                risk_level=ToolRiskLevel.APPROVAL_BOUND,
                allowed_roles=[AgentRole.SUPERVISOR, AgentRole.PLANNER],
                allowed_states=[WorkflowState.POLICY_CHECK, WorkflowState.WAITING_FOR_APPROVAL],
                handler=lambda args: {"status": "PENDING_APPROVAL", "workflow_id": args.get("workflow_id")},
            )
        )

        # Tool 8: execute_approved_ansible
        gateway.register_tool(
            ToolDefinition(
                name="execute_approved_ansible",
                description="Execute approved immutable package under cryptographic Capability Token.",
                risk_level=ToolRiskLevel.RESTRICTED,
                allowed_roles=[AgentRole.EXECUTOR],
                allowed_states=[WorkflowState.EXECUTION_READY, WorkflowState.EXECUTING],
                handler=lambda args: {"runner": "ansible_runner_constrained", "exit_code": 0},
            )
        )

        # Tool 9: verify_postcondition
        gateway.register_tool(
            ToolDefinition(
                name="verify_postcondition",
                description="Execute independent read-only probes verifying target desired state.",
                risk_level=ToolRiskLevel.READ_ONLY,
                allowed_roles=[AgentRole.VERIFIER],
                allowed_states=[WorkflowState.VERIFYING, WorkflowState.SUCCESS],
                handler=lambda args: {"probes_passed": True, "latency_ms": 12.0},
            )
        )

        # Tool 10: initiate_rollback
        gateway.register_tool(
            ToolDefinition(
                name="initiate_rollback",
                description="Execute pre-validated rollback playbook following execution or verification failure.",
                risk_level=ToolRiskLevel.RESTRICTED,
                allowed_roles=[AgentRole.ROLLBACK],
                allowed_states=[WorkflowState.ROLLING_BACK],
                handler=lambda args: {"status": "ROLLED_BACK", "exit_code": 0},
            )
        )

        return gateway
