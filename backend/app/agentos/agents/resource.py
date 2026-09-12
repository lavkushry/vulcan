"""
Project Vulcan: Resource Agent (Section 7, 16, 18, 19, 45 & AGENT-06)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Resolve every external resource dependency before execution
- Check availability against External Resources registry (PostgreSQL 16)
- Maintain Zero-Raw-Secrets Invariant: only vault://, cyberark://, env:// references
- Transition to WAITING_FOR_RESOURCE on missing requirements, enabling in-place pause and resume
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, RequiredResource, ResourceOutput
from app.ports.repositories import IExternalResourceRepository


class ResourceAgent(BaseAgent):
    def __init__(self, resource_repo: Optional[IExternalResourceRepository] = None, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.RESOURCE,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Resolve external provider configurations, secret references, and detect missing infrastructure dependencies.",
        )
        self.resource_repo = resource_repo

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return ResourceOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> ResourceOutput:
        req_text = ctx.original_request.lower()

        # Build list of required resources from intent & text
        dependencies = [
            RequiredResource(
                resource_type="credentials",
                provider="cyberark",
                required=True,
                description="CyberArk Enterprise CCP for privileged root credentials",
            ),
            RequiredResource(
                resource_type="itsm",
                provider="servicenow",
                required=True,
                description="ServiceNow Change Management & ticket validation",
            ),
            RequiredResource(
                resource_type="storage",
                provider="s3",
                required=True,
                description="Amazon S3 / MinIO backup storage bucket",
            ),
        ]

        if "datadog" in req_text:
            dependencies.append(
                RequiredResource(
                    resource_type="monitoring",
                    provider="datadog",
                    required=True,
                    description="Datadog APM and host monitoring",
                )
            )

        if "foundry" in req_text or "microsoft" in req_text:
            dependencies.append(
                RequiredResource(
                    resource_type="ai_models",
                    provider="microsoft_foundry",
                    required=True,
                    description="Microsoft Foundry AI Deployment Endpoint",
                )
            )

        missing: List[str] = []
        resolved: Dict[str, Any] = {}
        secret_refs: List[str] = []

        if self.resource_repo:
            try:
                if hasattr(self.resource_repo, "list_all"):
                    available_resources = self.resource_repo.list_all(environment=ctx.environment)
                elif hasattr(self.resource_repo, "list_resources"):
                    available_resources = self.resource_repo.list_resources(environment=ctx.environment)
                else:
                    available_resources = []
            except Exception:
                available_resources = []

        # Map by provider
        provider_map = {r.provider: r for r in available_resources if getattr(r, "enabled", True)}

        for dep in dependencies:
            res = provider_map.get(dep.provider)
            if res:
                dep.is_available = True
                dep.external_resource_id = res.resource_id
                resolved[dep.provider] = {
                    "resource_id": res.resource_id,
                    "endpoint": res.endpoint,
                    "auth_mode": str(res.auth_mode),
                    "health_status": str(res.health_status),
                }
                # Zero Raw Secrets: collect only pointers
                if hasattr(res, "secret_refs") and isinstance(res.secret_refs, dict):
                    for k, ptr in res.secret_refs.items():
                        secret_refs.append(f"{dep.provider}://{res.resource_id}/{k} -> {ptr}")
            elif dep.required:
                dep.is_available = False
                missing.append(dep.provider)

        all_satisfied = (len(missing) == 0)
        next_state = WorkflowState.VALIDATING.value if all_satisfied else WorkflowState.WAITING_FOR_RESOURCE.value

        return ResourceOutput(
            workflow_id=ctx.workflow_id,
            required_resources=dependencies,
            missing_resources=missing,
            resolved_resources=resolved,
            secret_references=secret_refs,
            all_dependencies_satisfied=all_satisfied,
            proposed_next_state=next_state,
            confidence=1.0 if all_satisfied else 0.50,
            rationale="All dependencies resolved via External Resources." if all_satisfied else f"Missing required resources: {missing}. Halting for operator configuration.",
        )
