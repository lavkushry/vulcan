"""
Project Vulcan: Base Specialist Agent Interface (AGENT-02)
Author: Architectural Review Board & AgentOS Core Team

Enforces:
1. Strict typing and validation using Pydantic output schemas.
2. Immutability & version tracking (instruction hash, version tag).
3. Raw LLM responses stored separately for audit and diagnostics.
"""
from __future__ import annotations

import abc
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, ValidationError

from app.agentos.context import WorkflowContext
from app.agentos.schemas import AgentRole, BaseAgentOutput


class AgentExecutionError(Exception):
    """Raised when an agent execution fails schema validation or runtime error."""
    pass


class BaseAgent(abc.ABC):
    """
    Abstract base class for all AgentOS specialist agents.
    Guarantees narrow responsibility, least privilege, and auditable outputs.
    """

    def __init__(
        self,
        role: AgentRole,
        version: str = "v1.0",
        model_provider: str = "microsoft_foundry",
        model_name: str = "gpt-4o",
        system_instructions: str = ""
    ):
        self.role = role
        self.version = version
        self.model_provider = model_provider
        self.model_name = model_name
        self.system_instructions = system_instructions
        self.instruction_hash = hashlib.sha256(system_instructions.encode("utf-8")).hexdigest()

    @property
    @abc.abstractmethod
    def output_schema(self) -> Type[BaseAgentOutput]:
        """The specific Pydantic schema required for this agent's structured response."""
        pass

    @abc.abstractmethod
    def execute(self, ctx: WorkflowContext, **kwargs) -> BaseAgentOutput:
        """Executes agent logic against the WorkflowContext, producing a structured proposal."""
        pass

    def validate_and_parse(self, raw_data: Dict[str, Any]) -> BaseAgentOutput:
        """Validates payload against the agent's schema, rejecting malformed structures."""
        try:
            return self.output_schema.model_validate(raw_data)
        except ValidationError as e:
            raise AgentExecutionError(
                f"Agent '{self.role.value}:{self.version}' produced malformed output: {e}"
            ) from e
