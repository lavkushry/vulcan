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


class ProviderUnavailableError(Exception):
    """Raised when an external model/chat provider cannot be resolved or is unavailable."""
    pass


class InvalidAgentOutputError(Exception):
    """Raised when LLM returns invalid or malformed output that fails validation after bounded repair attempts."""
    pass


class IAgentRuntime(abc.ABC):
    """Abstract agent execution runtime."""

    @property
    @abc.abstractmethod
    def is_deterministic(self) -> bool:
        """True if agents produce deterministic output (pure logic). False for LLM-backed."""
        pass

    @property
    @abc.abstractmethod
    def is_simulation(self) -> bool:
        """True if runtime uses simulated/in-memory agent execution."""
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
    def is_simulation(self) -> bool:
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
    """Production runtime for external LLM/Foundry-backed agents."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        chat_provider: Optional[Any] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.05,
        max_repair_attempts: int = 2,
    ):
        self._endpoint = endpoint
        self._api_key = api_key
        self._chat_provider = chat_provider
        self._max_retries = max(1, max_retries)
        self._retry_delay_seconds = max(0.0, retry_delay_seconds)
        self._max_repair_attempts = max(0, max_repair_attempts)

    @property
    def is_deterministic(self) -> bool:
        return False

    @property
    def is_simulation(self) -> bool:
        return False

    @property
    def runtime_name(self) -> str:
        return "foundry_llm"

    def _resolve_chat_provider(self):
        """
        Resolves the live chat provider. Never silently falls back to a fake provider.
        Retries up to max_retries before raising ProviderUnavailableError.
        """
        if self._chat_provider:
            return self._chat_provider

        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                from app.adapters.chat_providers import get_chat_provider
                from app.adapters.fake_chat_adapter import DeterministicFakeChatProvider
                provider = get_chat_provider()
                if isinstance(provider, DeterministicFakeChatProvider):
                    raise ProviderUnavailableError(
                        "get_chat_provider() defaulted to DeterministicFakeChatProvider because no live API keys "
                        "were detected. Silent fallback to fake provider is forbidden in FoundryAgentRuntime."
                    )
                if provider is not None:
                    return provider
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries and self._retry_delay_seconds > 0:
                    import time
                    time.sleep(self._retry_delay_seconds)

        raise ProviderUnavailableError(
            f"Failed to resolve real chat provider after {self._max_retries} attempts: {last_error}"
        )

    def invoke(
        self,
        agent_role: AgentRole,
        system_prompt: str,
        context: Dict[str, Any],
        output_schema: Type[BaseAgentOutput],
    ) -> BaseAgentOutput:
        import json
        from app.ports.interfaces import ChatCompletionRequest
        from app.agentos.schemas import ExecutionMode
        from pydantic import ValidationError

        provider = self._resolve_chat_provider()
        user_prompt = (
            f"You are the {agent_role.value} agent in AgentOS.\n"
            f"Context: {json.dumps(context, default=str)}\n"
            f"Generate structured output conforming to the required JSON schema for {output_schema.__name__}."
        )

        schema = output_schema.model_json_schema() if hasattr(output_schema, "model_json_schema") else None
        req = ChatCompletionRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            grammar_json_schema=schema,
            temperature=0.0,
            max_tokens=4096,
        )

        last_error: Optional[Exception] = None
        current_req = req

        for attempt in range(self._max_repair_attempts + 1):
            raw_text = ""
            parsed: Dict[str, Any] = {}
            try:
                response = provider.complete_structured(current_req)
                parsed = getattr(response, "parsed_json", None) or {}
                raw_text = getattr(response, "content", getattr(response, "raw_content", ""))
                if not parsed and raw_text:
                    content = raw_text.strip()
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    parsed = json.loads(content)

                if not isinstance(parsed, dict):
                    raise ValueError(f"Expected JSON object output, got {type(parsed).__name__}")

                if "agent" not in parsed and hasattr(output_schema, "agent"):
                    parsed["agent"] = agent_role
                if "proposed_next_state" not in parsed or not parsed["proposed_next_state"]:
                    parsed["proposed_next_state"] = context.get("proposed_next_state") or context.get("next_state") or "PLANNING"
                if "workflow_id" not in parsed:
                    parsed["workflow_id"] = context.get("workflow_id", "")
                parsed["execution_mode"] = ExecutionMode.LIVE.value

                return output_schema.model_validate(parsed)
            except (ValidationError, json.JSONDecodeError, ValueError, Exception) as exc:
                last_error = exc
                if attempt < self._max_repair_attempts:
                    repair_prompt = (
                        f"Your previous response failed validation: {exc}\n"
                        f"Previous raw content: {raw_text[:500]}\n"
                        f"Please fix all formatting or validation errors and return only valid JSON for {output_schema.__name__}."
                    )
                    current_req = ChatCompletionRequest(
                        system_prompt=system_prompt,
                        user_prompt=repair_prompt,
                        grammar_json_schema=schema,
                        temperature=0.0,
                        max_tokens=4096,
                    )

        # Honest failure: after bounded repairs fail, raise InvalidAgentOutputError instead of fabricating fields
        raise InvalidAgentOutputError(
            f"Agent '{agent_role.value}' failed to produce valid output conforming to "
            f"{output_schema.__name__} after {self._max_repair_attempts} repair attempts: {last_error}"
        )
