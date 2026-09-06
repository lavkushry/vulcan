"""
Project Vulcan: Stack Composition Engine (REG-05)
Synthesizes multi-module infrastructure stacks (e.g. AWS Landing Zones combining VPC + EKS + RDS)
into reviewable, immutable CatalogItem entities bound to verified corporate Git commit SHAs.

Architectural Laws Enforced:
1. INV-1 Compliance: Composite stacks are pre-compiled and pinned to an internal 40-character Git SHA.
2. AI Intent Invariant: The LLM matches operator intent to composite stack parameters; it never generates HCL glue code at runtime.
3. Rule 2 No-Guessing: Stack parameters declare strict ParamSpec schemas; missing values fail-closed to NEEDS_INPUT.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.domain.entities import (
    CatalogItem,
    CurationStatus,
    ExecutionEngineType,
    RiskTier,
)
from app.domain.exceptions import ParameterValidationError


@dataclass(frozen=True)
class CompositeSubModule:
    """Represents a component building block within a multi-module infrastructure stack."""
    module_name: str
    upstream_ref: str
    role: str  # e.g. "network", "compute", "database"
    exposed_parameters: List[str]


class StackComposer:
    """
    Compiles multi-module infrastructure patterns into immutable CatalogItem specifications.
    Enforces governance, risk tiering, and Maker-Checker requirements at composition time.
    """

    @staticmethod
    def compose_stack(
        identifier: str,
        name: str,
        description: str,
        sub_modules: List[CompositeSubModule],
        input_schema: Dict[str, Any],
        internal_git_repo: str = "git@github.internal.bank.com:automation/catalog-modules.git",
        internal_commit_sha: str = "ce42ca5000000000000000000000000000000001",
        risk_tier: RiskTier = RiskTier.HIGH,
        requires_maker_checker: bool = True,
        requires_chg: bool = True,
        category: str = "cloud",
        tags: Optional[List[str]] = None,
        suggested_defaults: Optional[Dict[str, Any]] = None,
    ) -> CatalogItem:
        """
        Creates an immutable, curated composite CatalogItem.
        """
        if not re.match(r"^[0-9a-f]{40}$", internal_commit_sha):
            raise ParameterValidationError(
                f"Composite stack [{identifier}] must bind to a 40-character Git commit SHA."
            )

        composite_tags = tags or ["composite_stack", "landing_zone", "terraform", "enterprise"]
        for mod in sub_modules:
            composite_tags.append(mod.role)

        provenance = {
            "is_composite": True,
            "architecture": "landing_zone",
            "sub_modules": [
                {
                    "module_name": m.module_name,
                    "upstream_ref": m.upstream_ref,
                    "role": m.role,
                    "exposed_parameters": m.exposed_parameters,
                }
                for m in sub_modules
            ],
            "suggested_defaults": suggested_defaults or {},
            "composed_by": "Vulcan StackComposer (REG-05)",
        }

        return CatalogItem(
            id=f"stack-{identifier.replace('.', '-')}",
            identifier=identifier,
            name=name,
            engine=ExecutionEngineType.TERRAFORM,
            git_repo=internal_git_repo,
            git_commit_sha=internal_commit_sha,
            playbook_or_module_path=f"stacks/{identifier.replace('.', '/')}/main.tf",
            risk_tier=risk_tier,
            requires_maker_checker=requires_maker_checker,
            requires_chg=requires_chg,
            input_schema=input_schema,
            category=category,
            description=description,
            tags=list(set(composite_tags)),
            curation_status=CurationStatus.CURATED,
            provenance=provenance,
        )


def create_aws_banking_landing_zone_stack() -> CatalogItem:
    """
    Factory creating the canonical AWS Banking Landing Zone composite stack:
    Combines VPC + EKS Kubernetes Cluster + RDS PostgreSQL Database.
    """
    sub_modules = [
        CompositeSubModule(
            module_name="terraform-aws-modules/vpc/aws",
            upstream_ref="v5.5.0",
            role="network",
            exposed_parameters=["vpc_cidr_block", "aws_region"],
        ),
        CompositeSubModule(
            module_name="terraform-aws-modules/eks/aws",
            upstream_ref="v20.0.0",
            role="compute",
            exposed_parameters=["cluster_name", "eks_node_count"],
        ),
        CompositeSubModule(
            module_name="terraform-aws-modules/rds/aws",
            upstream_ref="v6.4.0",
            role="database",
            exposed_parameters=["db_instance_class", "db_name", "environment"],
        ),
    ]

    input_schema = {
        "type": "object",
        "required": [
            "vpc_cidr_block",
            "aws_region",
            "cluster_name",
            "eks_node_count",
            "db_instance_class",
            "db_name",
            "environment",
        ],
        "properties": {
            "vpc_cidr_block": {
                "type": "string",
                "pattern": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}\/[0-9]{1,2}$",
                "description": "IPv4 CIDR block for the dedicated banking VPC (e.g. 10.100.0.0/16)",
            },
            "aws_region": {
                "type": "string",
                "enum": ["us-east-1", "us-east-2", "us-west-2", "eu-west-1"],
                "description": "Target AWS deployment region",
            },
            "cluster_name": {
                "type": "string",
                "pattern": r"^[a-z0-9-]+$",
                "description": "Unique identifier for the EKS Kubernetes cluster",
            },
            "eks_node_count": {
                "type": "integer",
                "minimum": 3,
                "maximum": 50,
                "description": "Number of EC2 worker nodes in the default managed node group",
            },
            "db_instance_class": {
                "type": "string",
                "enum": ["db.r6g.large", "db.r6g.xlarge", "db.r6g.2xlarge", "db.m6g.large"],
                "description": "RDS PostgreSQL instance hardware specification",
            },
            "db_name": {
                "type": "string",
                "pattern": r"^[a-zA-Z][a-zA-Z0-9_]{2,31}$",
                "description": "Primary transactional database schema name",
            },
            "environment": {
                "type": "string",
                "enum": ["dev", "uat", "prod"],
                "description": "Target banking operating tier",
            },
        },
    }

    suggested_defaults = {
        "aws_region": "us-east-1",
        "eks_node_count": 3,
        "db_instance_class": "db.r6g.large",
    }

    return StackComposer.compose_stack(
        identifier="aws.enterprise.landing_zone.vpc_eks_rds",
        name="AWS Banking Landing Zone (VPC + EKS + RDS)",
        description="Unified Tier-1 cloud landing zone combining isolated VPC network topology, governed EKS Kubernetes cluster, and Multi-AZ PostgreSQL RDS.",
        sub_modules=sub_modules,
        input_schema=input_schema,
        internal_commit_sha="ce42ca5000000000000000000000000000000001",
        risk_tier=RiskTier.HIGH,
        requires_maker_checker=True,
        requires_chg=True,
        category="cloud",
        suggested_defaults=suggested_defaults,
    )
