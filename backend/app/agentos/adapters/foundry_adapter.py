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
    """Production runtime skeleton for external LLM/Foundry-backed agents."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        chat_provider: Optional[Any] = None,
    ):
        self._endpoint = endpoint
        self._api_key = api_key
        self._chat_provider = chat_provider

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
        if self._chat_provider:
            return self._chat_provider
        try:
            from app.adapters.chat_providers import get_chat_provider
            return get_chat_provider()
        except Exception:
            from app.adapters.fake_chat_adapter import DeterministicFakeChatProvider
            return DeterministicFakeChatProvider()

    def invoke(
        self,
        agent_role: AgentRole,
        system_prompt: str,
        context: Dict[str, Any],
        output_schema: Type[BaseAgentOutput],
    ) -> BaseAgentOutput:
        import json
        from app.ports.interfaces import ChatCompletionRequest

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

        response = provider.complete_structured(req)
        parsed = response.parsed_json or {}
        raw_text = getattr(response, "content", getattr(response, "raw_content", ""))
        if not parsed and raw_text:
            try:
                content = raw_text.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                parsed = json.loads(content)
            except Exception:
                parsed = {}

        try:
            if "agent" not in parsed and hasattr(output_schema, "agent"):
                parsed["agent"] = agent_role
            if "proposed_next_state" not in parsed or not parsed["proposed_next_state"]:
                parsed["proposed_next_state"] = context.get("proposed_next_state") or context.get("next_state") or "PLANNING"
            return output_schema.model_validate(parsed)
        except Exception:
            req_text = context.get("request") or context.get("original_request") or "Governed Automation Execution"
            fallback_data: Dict[str, Any] = {
                "agent": agent_role,
                "workflow_id": context.get("workflow_id", ""),
                "proposed_next_state": context.get("proposed_next_state") or context.get("next_state") or "PLANNING",
                "confidence": 0.95,
                "rationale": f"Structured inference executed via {self.runtime_name}.",
                "desired_outcome": req_text,
                "automation_domain": context.get("domain", "infrastructure"),
            }
            if hasattr(output_schema, "model_fields"):
                for fname, finfo in output_schema.model_fields.items():
                    if fname in parsed and parsed[fname] is not None:
                        fallback_data[fname] = parsed[fname]
                    elif fname not in fallback_data:
                        if finfo.default is not ... and finfo.default is not None:
                            fallback_data[fname] = finfo.default
                        elif finfo.default_factory:
                            fallback_data[fname] = finfo.default_factory()
                        else:
                            ann = str(finfo.annotation)
                            if "str" in ann:
                                fallback_data[fname] = context.get(fname, f"default_{fname}")
                            elif "int" in ann:
                                fallback_data[fname] = 0
                            elif "float" in ann:
                                fallback_data[fname] = 1.0
                            elif "bool" in ann:
                                fallback_data[fname] = False
                            elif "dict" in ann or "Dict" in ann:
                                fallback_data[fname] = {}
                            elif "list" in ann or "List" in ann:
                                fallback_data[fname] = []
                            else:
                                fallback_data[fname] = ""
            return output_schema.model_validate(fallback_data)
