"""
Project Vulcan: Agent Runtime Adapters (P0 #10)
Author: AgentOS Core Team

Provides pluggable agent runtimes distinguishing deterministic agents from model-backed agents.
DeterministicAgentRuntime: Current pure-Python logic agents (is_deterministic=True).
FoundryAgentRuntime: External LLM/Foundry-backed agents (is_deterministic=False).
"""
from __future__ import annotations

import abc
from typing import Any, Dict, Optional, Type

from app.agentos.schemas import AgentRole, BaseAgentOutput


class IAgentRuntime(abc.ABC):
    """Abstract agent execution runtime."""

    @property
    @abc.abstractmethod
    def is_deterministic(self) -> bool:
        """True if agents produce deterministic output (pure logic). False for LLM-backed."""
        pass

    @property
    @abc.abstractmethod
    def runtime_name(self) -> str:
        pass

    @abc.abstractmethod
    def invoke(
        self,
        agent_role: AgentRole,
        system_prompt: str,
        context: Dict[str, Any],
        output_schema: Type[BaseAgentOutput],
    ) -> BaseAgentOutput:
        """Invoke an agent with the given role and context, returning structured output."""
        pass


class DeterministicAgentRuntime(IAgentRuntime):
    """Current runtime: agents are pure Python logic with deterministic output."""

    @property
    def is_deterministic(self) -> bool:
        return True

    @property
    def runtime_name(self) -> str:
        return "deterministic_python"

    def invoke(
        self,
        agent_role: AgentRole,
        system_prompt: str,
        context: Dict[str, Any],
        output_schema: Type[BaseAgentOutput],
    ) -> BaseAgentOutput:
        raise NotImplementedError(
            "DeterministicAgentRuntime does not use invoke(). "
            "Agents execute directly via agent.execute(ctx)."
        )


class FoundryAgentRuntime(IAgentRuntime):
    """Production runtime skeleton for external LLM/Foundry-backed agents."""

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None):
        self._endpoint = endpoint
        self._api_key = api_key

    @property
    def is_deterministic(self) -> bool:
        return False

    @property
    def runtime_name(self) -> str:
        return "foundry_llm"

    def invoke(
        self,
        agent_role: AgentRole,
        system_prompt: str,
        context: Dict[str, Any],
        output_schema: Type[BaseAgentOutput],
    ) -> BaseAgentOutput:
        # TODO: Wire to Azure AI Foundry / Gemini / external LLM endpoint
        raise NotImplementedError("AgentOS production execution is not yet implemented (FoundryAgentRuntime)")
