"""
Project Vulcan: Tests for Automation Compiler & Intermediate Representation (AGENT-05)
"""
import pytest
from app.agentos.compiler import AutomationCompiler
from app.agentos.specification import (
    AutomationSpecification,
    PostconditionProbeDef,
    ResourceContract,
    ResourceDependency,
)


def test_compiler_renders_hardened_ansible_package():
    spec = AutomationSpecification(
        spec_id="spec-pg-16",
        goal="Hardened PostgreSQL 16 Cluster",
        engine="ansible",
        supported_platforms=["rhel9"],
        desired_state={"port": 5432, "nodes": 3},
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        dependencies=["ansible.builtin", "community.postgresql"],
        resource_contract=ResourceContract(
            dependencies={
                "s3": ResourceDependency(resource_type="storage", provider="s3")
            }
        ),
        execution_dag=[],
        postconditions=[
            PostconditionProbeDef(
                probe_id="p1", target="localhost", probe_type="port_open", expected_value=5432
            )
        ],
    )

    compiled = AutomationCompiler.compile(spec)
    assert compiled.engine == "ansible"
    assert len(compiled.artifact_sha256) == 64

    # Verify FQCN usage
    tasks = compiled.get_file("roles/hardened_postgresql_16_cluster/tasks/main.yml")
    assert tasks is not None
    assert "ansible.builtin.package:" in tasks
    assert "ansible.builtin.service:" in tasks

    # Verify Handlers, Defaults, README, Molecule
    assert compiled.get_file("roles/hardened_postgresql_16_cluster/handlers/main.yml") is not None
    assert compiled.get_file("roles/hardened_postgresql_16_cluster/defaults/main.yml") is not None
    assert compiled.get_file("roles/hardened_postgresql_16_cluster/README.md") is not None
    assert compiled.get_file("roles/hardened_postgresql_16_cluster/molecule/default/molecule.yml") is not None
    assert compiled.get_file("rollback.yml") is not None


def test_compiler_renders_terraform_package():
    spec = AutomationSpecification(
        spec_id="spec-tf-01",
        goal="Cloud VPC and Subnets",
        engine="terraform",
        supported_platforms=["aws"],
        desired_state={"subnets": 3},
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        dependencies=[],
        resource_contract=ResourceContract(),
        execution_dag=[],
    )
    compiled = AutomationCompiler.compile(spec)
    assert compiled.engine == "terraform"
    main_tf = compiled.get_file("main.tf")
    assert main_tf is not None
    assert "required_version" in main_tf
    assert "required_providers" in main_tf
    assert compiled.get_file("variables.tf") is not None
    assert compiled.get_file("outputs.tf") is not None
    assert compiled.get_file("rollback/main.tf") is not None
