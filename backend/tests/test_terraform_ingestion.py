"""
Project Vulcan: Terraform Registry Ingestion & Typed Schema Transformation Tests
Validates:
1. HCL default value parsing (parse_hcl_default).
2. Terraform type mapping to JSON Schema ParamSpecs (transform_terraform_type).
3. Schema construction and required vs optional field inference (TerraformTypeTransformer).
4. CatalogItem entity invariants (40-char SHA, TERRAFORM engine, category/risk).
5. D1 / CHAT-10 Non-Guessing Invariant: schemas with defaults must NEVER have those
   defaults populated into IntentResolutionResult.extracted_params without explicit user input.
6. Module Disambiguation: near-duplicate modules trigger delta_sim < 0.05 disambiguation.
"""
import pytest
from app.domain.entities import CatalogItem, ExecutionEngineType, RiskTier
from app.adapters.terraform_ingestion import (
    parse_hcl_default,
    transform_terraform_type,
    TerraformTypeTransformer,
    TerraformRegistryApiClient,
)
from app.use_cases.resolve_intent import IntentResolver


class TestHclParsingAndSchemaTransformation:
    """Unit tests for HCL typing and default value parsing."""

    def test_parse_hcl_default_primitives(self):
        assert parse_hcl_default("true") is True
        assert parse_hcl_default("false") is False
        assert parse_hcl_default("null") is None
        assert parse_hcl_default(None) is None
        assert parse_hcl_default("42") == 42
        assert parse_hcl_default("3.14") == 3.14

    def test_parse_hcl_default_strings_and_structures(self):
        # Strips enclosing escaped/raw quotes
        assert parse_hcl_default('"10.0.0.0/16"') == "10.0.0.0/16"
        assert parse_hcl_default("'us-east-1'") == "us-east-1"
        assert parse_hcl_default('["eu-west-1a", "eu-west-1b"]') == ["eu-west-1a", "eu-west-1b"]
        assert parse_hcl_default("[]") == []
        assert parse_hcl_default('{"Environment": "production"}') == {"Environment": "production"}
        assert parse_hcl_default("{}") == {}

    def test_transform_terraform_type(self):
        assert transform_terraform_type("string") == {"type": "string"}
        assert transform_terraform_type("bool") == {"type": "boolean"}
        assert transform_terraform_type("number") == {"type": "number"}
        assert transform_terraform_type("list(string)") == {"type": "array"}
        assert transform_terraform_type("set(string)") == {"type": "array"}
        assert transform_terraform_type("map(string)") == {"type": "object"}
        assert transform_terraform_type("object({ name = string })") == {"type": "object"}
        assert transform_terraform_type(None) == {"type": "string"}

    def test_build_input_schema_with_defaults_and_required(self):
        raw_inputs = [
            {
                "name": "vpc_name",
                "type": "string",
                "description": "Name of the VPC",
                "required": True
            },
            {
                "name": "cidr",
                "type": "string",
                "description": "IPv4 CIDR block",
                "default": '"10.0.0.0/16"',
                "required": False
            },
            {
                "name": "enable_nat_gateway",
                "type": "bool",
                "description": "Should NAT Gateways be enabled",
                "default": "true",
                "required": False
            },
            {
                "name": "azs",
                "type": "list(string)",
                "description": "Availability zones",
                "default": "[]",
                "required": False
            }
        ]

        schema = TerraformTypeTransformer.build_input_schema(raw_inputs)

        assert schema["type"] == "object"
        assert schema["required"] == ["vpc_name"]
        props = schema["properties"]
        assert props["vpc_name"]["type"] == "string"
        assert "default" not in props["vpc_name"]

        assert props["cidr"]["type"] == "string"
        assert props["cidr"]["default"] == "10.0.0.0/16"

        assert props["enable_nat_gateway"]["type"] == "boolean"
        assert props["enable_nat_gateway"]["default"] is True

        assert props["azs"]["type"] == "array"
        assert props["azs"]["default"] == []


class TestTerraformModuleRecordTransformation:
    """Tests transformation of registry records into immutable CatalogItem entities."""

    def test_transform_module_record_invariants(self):
        client = TerraformRegistryApiClient()
        raw_module = {
            "namespace": "terraform-aws-modules",
            "name": "vpc",
            "provider": "aws",
            "version": "6.7.2",
            "description": "Terraform module to create AWS VPC resources",
            "source": "https://github.com/terraform-aws-modules/terraform-aws-vpc",
            "tag": "v6.7.2"
        }
        details = {
            "root": {
                "inputs": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "cidr", "type": "string", "default": '"10.0.0.0/16"'}
                ]
            }
        }

        item = client.transform_module_record(raw_module, details)

        assert item.engine == ExecutionEngineType.TERRAFORM
        assert len(item.git_commit_sha) == 40
        assert item.category in ("cloud", "network")
        assert item.risk_tier == RiskTier.MEDIUM
        assert item.requires_maker_checker is True
        assert item.requires_chg is False
        assert "cidr" in item.input_schema["properties"]
        assert item.input_schema["properties"]["cidr"]["default"] == "10.0.0.0/16"


class TestD1Chat10NonGuessingWithDefaults:
    """
    Adversarial verification of D1 / CHAT-10:
    Real Terraform modules ship with schema defaults on almost every input variable.
    The IntentResolver must NEVER pre-fill schema defaults into extracted_params!
    """

    @pytest.fixture
    def terraform_catalog_item(self):
        return CatalogItem(
            id="cat-tf-test-vpc",
            identifier="terraform.aws.vpc-production",
            name="Terraform AWS Production VPC",
            engine=ExecutionEngineType.TERRAFORM,
            git_repo="https://github.com/terraform-aws-modules/terraform-aws-vpc",
            git_commit_sha="a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
            playbook_or_module_path="modules/vpc",
            risk_tier=RiskTier.MEDIUM,
            requires_maker_checker=True,
            requires_chg=False,
            input_schema={
                "type": "object",
                "required": ["vpc_name", "environment"],
                "properties": {
                    "vpc_name": {"type": "string", "description": "Target VPC Name"},
                    "environment": {"type": "string", "description": "Deployment environment"},
                    "cidr": {"type": "string", "default": "10.0.0.0/16", "description": "VPC CIDR block"},
                    "enable_nat_gateway": {"type": "boolean", "default": True, "description": "Enable NAT Gateway"},
                    "single_nat_gateway": {"type": "boolean", "default": False, "description": "Single NAT Gateway"},
                    "node_count": {"type": "number", "default": 3, "description": "Worker count"}
                }
            },
            category="network",
            description="Terraform module to provision AWS VPC networking with NAT and subnets.",
            tags=["aws", "vpc", "network", "terraform"]
        )

    def test_resolver_never_prefills_schema_defaults(self, terraform_catalog_item):
        resolver = IntentResolver([terraform_catalog_item])

        # Operator provides prompt without specifying cidr, nat gateway, or node count
        prompt = "provision aws production vpc for payments service"
        res = resolver.resolve(prompt)

        assert res.catalog_item.identifier == "terraform.aws.vpc-production"
        
        # Invariant D1 / CHAT-10: Zero silent pre-filling of schema defaults
        extracted = res.extracted_parameters
        assert "cidr" not in extracted, "Resolver violated D1/CHAT-10 by silently filling schema default 'cidr'!"
        assert "enable_nat_gateway" not in extracted, "Resolver violated D1/CHAT-10 by filling 'enable_nat_gateway'!"
        assert "single_nat_gateway" not in extracted, "Resolver violated D1/CHAT-10 by filling 'single_nat_gateway'!"
        assert "node_count" not in extracted, "Resolver violated D1/CHAT-10 by filling 'node_count'!"

        # Missing required parameters must cause status to be NEEDS_INPUT
        assert res.status == "NEEDS_INPUT"
        assert set(res.missing_fields) == {"vpc_name", "environment"}

    def test_resolver_disambiguates_near_duplicate_terraform_modules(self):
        # Two competing VPC modules with high semantic similarity
        mod1 = CatalogItem(
            id="cat-tf-vpc-1",
            identifier="terraform.aws.vpc-standard",
            name="Terraform AWS VPC Standard",
            engine=ExecutionEngineType.TERRAFORM,
            git_repo="https://github.com/terraform-aws-modules/terraform-aws-vpc",
            git_commit_sha="a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
            playbook_or_module_path="modules/vpc",
            risk_tier=RiskTier.MEDIUM,
            requires_maker_checker=True,
            requires_chg=False,
            input_schema={"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
            category="network",
            description="Terraform module to create standard AWS VPC resources.",
            tags=["aws", "vpc", "network", "terraform"]
        )
        mod2 = CatalogItem(
            id="cat-tf-vpc-2",
            identifier="terraform.aws.vpc-advanced",
            name="Terraform AWS VPC Advanced",
            engine=ExecutionEngineType.TERRAFORM,
            git_repo="https://github.com/terraform-aws-modules/terraform-aws-vpc-advanced",
            git_commit_sha="b2c3d4e5f60718293a4b5c6d7e8f9012345678a1",
            playbook_or_module_path="modules/vpc-adv",
            risk_tier=RiskTier.MEDIUM,
            requires_maker_checker=True,
            requires_chg=False,
            input_schema={"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
            category="network",
            description="Terraform module to create advanced AWS VPC resources.",
            tags=["aws", "vpc", "network", "terraform"]
        )

        resolver = IntentResolver([mod1, mod2])
        res = resolver.resolve("provision aws vpc")

        # Must trigger disambiguation when delta_sim < 0.05
        assert res.status == "DISAMBIGUATION"
        assert res.delta_sim < 0.05
        assert len(res.disambiguation_candidates) >= 2
        identifiers = [c["identifier"] for c in res.disambiguation_candidates]
        assert "terraform.aws.vpc-standard" in identifiers
        assert "terraform.aws.vpc-advanced" in identifiers
