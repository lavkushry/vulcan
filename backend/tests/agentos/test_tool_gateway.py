"""
Project Vulcan: Tests for Typed Tool Gateway & Agent Permission Matrix (Sections 21 & 22)
"""
import pytest
from app.agentos.context import WorkflowState
from app.agentos.gateway import ToolDefinition, ToolExecutionError, ToolGateway, ToolRiskLevel
from app.agentos.schemas import AgentRole


def test_default_tool_gateway_registers_standard_tools():
    gw = ToolGateway.create_default_gateway()
    tools = gw.list_tools()
    assert len(tools) >= 10
    tool_names = [t.name for t in tools]
    assert "search_catalog" in tool_names
    assert "inspect_catalog_item" in tool_names
    assert "search_ansible_registry" in tool_names
    assert "search_terraform_registry" in tool_names
    assert "validate_artifact" in tool_names
    assert "execute_sandbox" in tool_names
    assert "request_approval" in tool_names
    assert "execute_approved_ansible" in tool_names
    assert "verify_postcondition" in tool_names
    assert "initiate_rollback" in tool_names


def test_tool_gateway_least_privilege_role_enforcement():
    gw = ToolGateway.create_default_gateway()

    # IntentAgent cannot invoke execution tool (Least-privilege violation)
    with pytest.raises(ToolExecutionError) as exc_info:
        gw.invoke(
            tool_name="execute_approved_ansible",
            caller_role=AgentRole.INTENT,
            current_state=WorkflowState.EXECUTING,
            arguments={"runner": "test"},
            correlation_id="corr-gw-01",
        )
    assert "is not authorized to invoke tool 'execute_approved_ansible'" in str(exc_info.value)

    # Executor is authorized to invoke execute_approved_ansible
    res = gw.invoke(
        tool_name="execute_approved_ansible",
        caller_role=AgentRole.EXECUTOR,
        current_state=WorkflowState.EXECUTING,
        arguments={"runner": "ansible_runner_constrained"},
        correlation_id="corr-gw-02",
    )
    assert res["exit_code"] == 0


def test_tool_gateway_allowed_state_machine_bounds():
    gw = ToolGateway.create_default_gateway()

    # Executor attempting to run in RECEIVED state must fail
    with pytest.raises(ToolExecutionError) as exc_info:
        gw.invoke(
            tool_name="execute_approved_ansible",
            caller_role=AgentRole.EXECUTOR,
            current_state=WorkflowState.RECEIVED,
            arguments={},
            correlation_id="corr-gw-03",
        )
    assert "cannot be called in state 'RECEIVED'" in str(exc_info.value)


def test_prohibited_generic_shell_tools_rejected():
    gw = ToolGateway.create_default_gateway()

    # Attempting to register or call arbitrary shell/bash is rejected
    with pytest.raises(ValueError) as exc_reg:
        gw.register_tool(
            ToolDefinition(
                name="shell",
                description="arbitrary command execution",
                risk_level=ToolRiskLevel.RESTRICTED,
                allowed_roles=[AgentRole.EXECUTOR],
                allowed_states=[WorkflowState.EXECUTING],
                handler=lambda args: {},
            )
        )
    assert "strictly forbidden" in str(exc_reg.value)

    with pytest.raises(ToolExecutionError) as exc_call:
        gw.invoke(
            tool_name="bash",
            caller_role=AgentRole.EXECUTOR,
            current_state=WorkflowState.EXECUTING,
            arguments={"cmd": "rm -rf /"},
            correlation_id="corr-gw-04",
        )
    assert "Generic production shell/SSH execution is strictly prohibited" in str(exc_call.value)


def test_idempotency_cache_and_audit_logging():
    call_count = 0

    def counting_handler(args):
        nonlocal call_count
        call_count += 1
        return {"call_number": call_count}

    gw = ToolGateway()
    gw.register_tool(
        ToolDefinition(
            name="test_tool",
            description="counting tool",
            risk_level=ToolRiskLevel.READ_ONLY,
            allowed_roles=[AgentRole.DISCOVERY],
            allowed_states=[WorkflowState.DISCOVERING],
            handler=counting_handler,
        )
    )

    # First call with idempotency key
    r1 = gw.invoke(
        tool_name="test_tool",
        caller_role=AgentRole.DISCOVERY,
        current_state=WorkflowState.DISCOVERING,
        arguments={"x": 1},
        correlation_id="corr-gw-05",
        idempotency_key="idemp-key-999",
    )
    assert r1["call_number"] == 1
    assert call_count == 1

    # Second call with same idempotency key returns cached result without re-executing
    r2 = gw.invoke(
        tool_name="test_tool",
        caller_role=AgentRole.DISCOVERY,
        current_state=WorkflowState.DISCOVERING,
        arguments={"x": 1},
        correlation_id="corr-gw-05",
        idempotency_key="idemp-key-999",
    )
    assert r2["call_number"] == 1
    assert call_count == 1  # Handler was NOT executed again!

    # Verify audit log captured invocation
    audit = gw.get_audit_log()
    assert len(audit) >= 1
    assert audit[0]["tool_name"] == "test_tool"
    assert audit[0]["status"] == "SUCCESS"
