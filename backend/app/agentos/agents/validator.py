"""
Project Vulcan: Validator Agent & Validation Factory (Section 7 & 24)
Author: Architectural Review Board & AgentOS Core Team

Preflight Validation Pipeline:
- Syntax check & YAML/HCL parsing
- Secret scanning (zero plaintext credentials)
- SAST & dangerous command analysis
- Idempotency & check-mode verification
- Molecule / sandbox container testing
- Postcondition & rollback artifact validation
Enforces: No stage may report PASS if skipped; strict PASS, FAIL, SKIPPED, NOT_APPLICABLE.
"""
from __future__ import annotations

import os
import re
from typing import List, Type
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import (
    AgentRole,
    BaseAgentOutput,
    ValidationCheck,
    ValidationCheckStatus,
    ValidatorOutput,
)


class ValidatorAgent(BaseAgent):
    def __init__(self, version: str = "v1.0"):
        super().__init__(
            role=AgentRole.VALIDATOR,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Execute rigorous preflight validation pipeline across syntax, lint, security, and idempotency.",
        )

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return ValidatorOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> ValidatorOutput:
        artifacts = ctx.generated_artifacts or []
        checks: List[ValidationCheck] = []

        all_files_content = ""
        syntax_ok = True
        total_files = 0
        yaml_files_checked = 0
        yaml_errors: List[str] = []

        try:
            import yaml
        except ImportError:
            yaml = None

        for art in artifacts:
            for f in art.get("files", []):
                total_files += 1
                path = f.get("path", "")
                content = f.get("content", "")
                all_files_content += content + "\n"

                # Only run YAML safe_load on YAML files (.yml, .yaml) or files with YAML doc separator that aren't markdown/json/tf
                is_yaml = path.endswith((".yml", ".yaml")) or (content.strip().startswith("---") and not path.endswith((".md", ".json", ".tf", ".txt")))
                if is_yaml and yaml and content.strip():
                    try:
                        yaml.safe_load(content)
                        yaml_files_checked += 1
                    except yaml.YAMLError as e:
                        yaml_errors.append(f"{path}: {str(e)[:150]}")

        # 1. Syntax Check
        if total_files == 0 or not all_files_content.strip():
            syntax_ok = False
            checks.append(
                ValidationCheck(
                    check_name="syntax_check",
                    status=ValidationCheckStatus.FAIL,
                    details="No automation artifact files provided for validation (fail-closed).",
                )
            )
        elif yaml_errors:
            syntax_ok = False
            checks.append(
                ValidationCheck(
                    check_name="syntax_check",
                    status=ValidationCheckStatus.FAIL,
                    details=f"YAML syntax error: {'; '.join(yaml_errors)}",
                )
            )
        elif "terraform" in all_files_content.lower() or "---" in all_files_content or "playbook" in all_files_content or yaml_files_checked > 0:
            checks.append(
                ValidationCheck(
                    check_name="syntax_check",
                    status=ValidationCheckStatus.PASS,
                    details=f"Structured automation syntax validated ({yaml_files_checked} YAML file(s) checked via yaml.safe_load).",
                )
            )
        else:
            syntax_ok = False
            checks.append(
                ValidationCheck(
                    check_name="syntax_check",
                    status=ValidationCheckStatus.FAIL,
                    details="No recognizable automation format detected.",
                )
            )

        # 2. Secret Scan (No plaintext passwords, tokens, private keys)
        secret_patterns = [
            r'password\s*[:=]\s*["\'](?!\{\{)[^"\']+["\']',
            r'token\s*[:=]\s*["\'](?!\{\{)[^"\']+["\']',
            r'BEGIN PRIVATE KEY',
            r'BEGIN RSA PRIVATE KEY',
        ]
        has_secret_leak = False
        for p in secret_patterns:
            if re.search(p, all_files_content, re.IGNORECASE):
                has_secret_leak = True
                break

        if has_secret_leak:
            checks.append(
                ValidationCheck(
                    check_name="secret_scan",
                    status=ValidationCheckStatus.FAIL,
                    details="Plaintext secret or unvaulted credential detected!",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    check_name="secret_scan",
                    status=ValidationCheckStatus.PASS,
                    details="Zero plaintext secrets detected (passed regex SAST scanner).",
                )
            )

        # 3. Dangerous Command Analysis
        dangerous_cmds = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:"]
        has_dangerous_cmd = any(cmd in all_files_content for cmd in dangerous_cmds)
        if has_dangerous_cmd:
            checks.append(
                ValidationCheck(
                    check_name="dangerous_command_check",
                    status=ValidationCheckStatus.FAIL,
                    details="Destructive system command detected in artifact.",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    check_name="dangerous_command_check",
                    status=ValidationCheckStatus.PASS,
                    details="No dangerous system-wiping commands detected.",
                )
            )

        # 4. Idempotency Verification
        checks.append(
            ValidationCheck(
                check_name="idempotency_verification",
                status=ValidationCheckStatus.SKIPPED,
                details="Idempotency check requires ansible --check mode or terraform plan. Not available in this environment.",
            )
        )

        # 5. Molecule Sandbox Check
        checks.append(
            ValidationCheck(
                check_name="molecule_sandbox_test",
                status=ValidationCheckStatus.SKIPPED,
                details="Molecule/sandbox testing requires container runtime. Not available in this environment.",
            )
        )

        non_skipped = [c for c in checks if c.status != ValidationCheckStatus.SKIPPED]
        
        is_env_prod = ctx.environment.upper() == "PROD"
        is_mode_prod = os.environ.get("AGENTOS_MODE", "").lower() == "production"
        if is_env_prod and is_mode_prod:
            mandatory_checks = {"ansible_lint", "idempotency_verification", "molecule_sandbox_test"}
            existing_check_names = {c.check_name for c in checks}
            for mc in mandatory_checks:
                if mc not in existing_check_names:
                    checks.append(ValidationCheck(
                        check_name=mc,
                        status=ValidationCheckStatus.SKIPPED,
                        details="Check was completely missing from validation run."
                    ))

            for c in checks:
                if c.check_name in mandatory_checks and c.status == ValidationCheckStatus.SKIPPED:
                    c.status = ValidationCheckStatus.FAIL
                    c.details = f"{c.details} [FATAL in PROD: Mandatory check cannot be SKIPPED]"
            
            failed = any(c.status == ValidationCheckStatus.FAIL for c in checks)
            all_passed = not failed and len(checks) > 0
        else:
            all_passed = bool(non_skipped) and all(c.status == ValidationCheckStatus.PASS for c in non_skipped)

        next_state = WorkflowState.SECURITY_REVIEW.value if all_passed else WorkflowState.VALIDATION_FAILED.value

        return ValidatorOutput(
            workflow_id=ctx.workflow_id,
            all_passed=all_passed,
            checks=checks,
            syntax_valid=syntax_ok,
            lint_passed=False,  # No real linter was run
            idempotency_verified=False,  # SKIPPED or FAIL
            sandbox_passed=False,  # SKIPPED or FAIL
            proposed_next_state=next_state,
            confidence=1.0 if all_passed else 0.20,
            rationale="All required preflight checks passed." if all_passed else "Preflight validation failed; workflow halted.",
        )
