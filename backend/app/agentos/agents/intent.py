"""
Project Vulcan: Intent Agent (Section 7 & 11)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Normalize natural-language request into structured intent
- Identify desired outcome and automation domain
- Extract known parameters and detect missing critical parameters
- Explicitly enumerate assumptions (Assumption Elimination Invariant)
- Must NEVER generate automation
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, IntentOutput


class IntentAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.INTENT,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Deconstruct natural language infrastructure requirements into unambiguous parameters.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return IntentOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> IntentOutput:
        prompt = ctx.original_request.strip()
        lower_prompt = prompt.lower()

        # 1. Automation Domain Classification
        if any(w in lower_prompt for w in ("postgres", "postgresql", "mysql", "database", "sql")):
            domain = "database"
        elif any(w in lower_prompt for w in ("patch", "kernel", "reboot", "os", "rhel", "linux")):
            domain = "os_patching"
        elif any(w in lower_prompt for w in ("f5", "vip", "cert", "tls", "ssl", "network", "dns")):
            domain = "network"
        elif any(w in lower_prompt for w in ("s3", "bucket", "vpc", "subnet", "terraform", "cloud", "aws", "azure")):
            domain = "cloud"
        else:
            domain = "general"

        # 2. Extract Known Parameters
        known = {}
        missing = []
        assumptions = []

        # Version detection
        v_match = re.search(r'(postgresql|postgres)\s*([0-9]+)', lower_prompt)
        if v_match:
            known["db_version"] = int(v_match.group(2))
        elif domain == "database":
            known["db_version"] = 16
            assumptions.append("Defaulting PostgreSQL version to 16 LTS.")

        # Node count detection
        word_num_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }
        word_nodes_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:rhel\s*\d+\s+)?(?:hardened\s+)?(?:nodes|hosts|servers|instances)', lower_prompt)
        digit_nodes_match = re.search(r'\b([0-9]+)\s+(?:nodes|hosts|servers|instances)', lower_prompt)

        if word_nodes_match:
            known["node_count"] = word_num_map[word_nodes_match.group(1)]
        elif digit_nodes_match and not ("rhel 9" in lower_prompt and digit_nodes_match.group(1) == "9" and any(w in lower_prompt for w in ("one", "two", "three", "four", "five", "six"))):
            known["node_count"] = int(digit_nodes_match.group(1))
        elif any(w in lower_prompt for w in word_num_map):
            for w, n in word_num_map.items():
                if f"{w} nodes" in lower_prompt or f"{w} hosts" in lower_prompt or f"on {w}" in lower_prompt:
                    known["node_count"] = n
                    break

        # OS Platform detection
        if "rhel 9" in lower_prompt or "rhel9" in lower_prompt:
            known["os_platform"] = "rhel9"
        elif "rhel 8" in lower_prompt or "rhel8" in lower_prompt:
            known["os_platform"] = "rhel8"

        # Storage capacity detection
        storage_match = re.search(r'([0-9]+)\s*(gb|tb)', lower_prompt)
        if storage_match:
            known["storage_capacity"] = f"{storage_match.group(1)}{storage_match.group(2).upper()}"

        # External services mentioned
        known["monitoring"] = "datadog" if "datadog" in lower_prompt else None
        known["backup"] = "s3" if "s3" in lower_prompt else None
        known["itsm"] = "servicenow" if "servicenow" in lower_prompt else None
        known["secrets"] = "cyberark" if "cyberark" in lower_prompt else None

        # 3. Detect Ambiguity & Missing Critical Parameters (Section 11)
        # e.g., "restart database" without environment or node ID
        if lower_prompt in ("restart database", "reboot database", "delete database", "drop database"):
            missing.extend(["target_host", "environment", "change_ticket"])
            ambiguity = "HIGHLY_AMBIGUOUS"
            req_input = True
            clarification = "Target database node and environment not specified. Please supply target_host and environment."
        elif domain == "database" and "node_count" not in known and "target_host" not in known:
            missing.append("target_inventory")
            ambiguity = "PARTIAL"
            req_input = True
            clarification = "Target nodes or cluster size not specified."
        else:
            ambiguity = "UNAMBIGUOUS"
            req_input = False
            clarification = None

        desired_outcome = f"Provision and configure {domain} automation matching: {prompt}"

        return IntentOutput(
            workflow_id=ctx.workflow_id,
            desired_outcome=desired_outcome,
            automation_domain=domain,
            known_parameters=known,
            missing_parameters=missing,
            ambiguity_classification=ambiguity,
            requires_operator_input=req_input,
            clarification_prompt=clarification,
            assumptions=assumptions,
            proposed_next_state=WorkflowState.WAITING_FOR_INPUT.value if req_input else WorkflowState.DISCOVERING.value,
            confidence=0.98 if not req_input else 0.40,
            rationale="Intent analyzed against parameter extraction grammar.",
        )
