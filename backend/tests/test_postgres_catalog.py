"""
Project Vulcan: PostgreSQL 16 + pgvector Catalog Search Repository Tests (D7.4)
Author: Alex Xu (Distributed Systems Lead) & Andrej Karpathy (AI Systems Lead)

Verifies:
1. HNSW Vector Index retrieval (1,536-dimensional embeddings with cosine distance).
2. Sparse keyword retrieval via generated tsvector column.
3. Two-stage Reciprocal Rank Fusion (RRF: 0.6 dense + 0.4 sparse).
4. Refusal Gate (BKND-26 / CHAT-06): Zero-Score Trap killed; nonsense query fails closed with 0 results.
5. Disambiguation Gate (CHAT-08): Queries with top-2 Δ < 0.05 trigger disambiguation.
6. DB-level Steel Cage Check Constraint (chk_catalog_curated_sha):
   - CURATED without valid 40-character commit SHA is rejected at the database level.
   - CANDIDATE without commit SHA is admitted into the candidate store.
7. Invariant INV-1: candidate.can_execute() is False; curated.can_execute() is True.
"""
import os
import unittest
import pytest
from app.adapters.postgres_catalog_repository import (
    PostgresCatalogRepository,
    compute_hash_embedding,
    format_pgvector_literal,
)
from app.domain.entities import (
    CatalogItem,
    CurationStatus,
    ExecutionEngineType,
    RiskTier,
)
from app.domain.exceptions import ParameterValidationError

# Mark entire suite with postgres mark
pytestmark = pytest.mark.postgres


class TestPostgresCatalogRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Database URL configuration
        cls.db_url = (
            os.getenv("POSTGRES_TEST_URL")
            or os.getenv("POSTGRES_URL")
            or os.getenv("DATABASE_URL")
            or "postgresql://vulcan_admin:vulcan_secret_pnc_2026@localhost:5432/vulcan_control_plane"
        )
        try:
            cls.repo = PostgresCatalogRepository(db_url=cls.db_url)
            # Connectivity smoke test
            cls.repo.count()
            cls.available = True
        except Exception as e:
            cls.available = False
            cls.skip_reason = str(e)

    def setUp(self):
        if self._testMethodName != "test_01_embedding_math_and_formatting" and not self.available:
            self.skipTest(f"PostgreSQL pgvector not accessible: {getattr(self, 'skip_reason', 'unknown')}")

    def test_01_embedding_math_and_formatting(self):
        """Embedding generator produces unit-normalized 1536-dimensional vectors."""
        vec = compute_hash_embedding("renew f5 ssl certificate on edge vip")
        self.assertEqual(len(vec), 1536)
        norm = sum(x * x for x in vec)
        self.assertAlmostEqual(norm, 1.0, places=4)

        literal = format_pgvector_literal(vec)
        self.assertTrue(literal.startswith("["))
        self.assertTrue(literal.endswith("]"))
        self.assertEqual(len(literal.split(",")), 1536)

    def test_02_steel_cage_check_constraint_enforced_by_database(self):
        """
        Database CHECK constraint (chk_catalog_curated_sha) rejects CURATED items
        that lack a valid 40-character Git commit SHA.
        """
        import psycopg

        # 1. Attempt to bypass steel cage: CURATED item with NULL git_commit_sha directly in SQL
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.repo._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalog_items (
                            id, identifier, name, engine, git_repo, git_commit_sha,
                            curation_status
                        ) VALUES (
                            'test-bypass-01', 'test.bypass.null-sha', 'Bypass Attempt', 'ansible',
                            'git@pnc:bypass.git', NULL, 'CURATED'
                        );
                    """)
                conn.commit()

        # 2. Attempt with invalid SHA (too short / non-hex)
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.repo._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalog_items (
                            id, identifier, name, engine, git_repo, git_commit_sha,
                            curation_status
                        ) VALUES (
                            'test-bypass-02', 'test.bypass.short-sha', 'Short SHA Attempt', 'ansible',
                            'git@pnc:bypass.git', 'abc123notasha', 'CURATED'
                        );
                    """)
                conn.commit()

        # 3. Valid CURATED item with 40-character hex commit SHA succeeds
        valid_curated = CatalogItem(
            id="test-curated-ok-01",
            identifier="test.curated.valid-sha-01",
            name="Valid Curated F5 SSL Renew",
            engine=ExecutionEngineType.ANSIBLE,
            git_repo="git@github.com:pnc/net-sec.git",
            git_commit_sha="a1b2c3d4e5f67890123456789abcdef012345678",
            playbook_or_module_path="playbooks/renew.yml",
            risk_tier=RiskTier.HIGH,
            requires_maker_checker=True,
            requires_chg=True,
            input_schema={"type": "object"},
            category="network",
            description="Production validated SSL cert renewal playbook for F5 VIPs.",
            tags=["f5", "ssl", "tls", "cert"],
            curation_status=CurationStatus.CURATED
        )
        self.repo.save(valid_curated)
        fetched = self.repo.get_by_identifier(valid_curated.identifier)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.curation_status, CurationStatus.CURATED)
        self.assertTrue(fetched.can_execute())

    def test_03_candidate_store_quarantine_and_invariants(self):
        """
        CANDIDATE items without Git commits can be stored in the CandidateStore,
        but invariant INV-1 mathematically blocks execution (can_execute() is False).
        """
        candidate = CatalogItem(
            id="test-cand-01",
            identifier="candidate.terraform.aws.vpc-provision-01",
            name="[Candidate] AWS VPC Modular Provisioner",
            engine=ExecutionEngineType.TERRAFORM,
            git_repo="https://github.com/terraform-aws-modules/terraform-aws-vpc",
            git_commit_sha="0000000000000000000000000000000000000000",
            playbook_or_module_path="modules/vpc",
            risk_tier=RiskTier.HIGH,
            requires_maker_checker=True,
            requires_chg=True,
            input_schema={"type": "object"},
            category="cloud",
            description="Uncurated Terraform candidate module crawled from public registry.",
            tags=["aws", "vpc", "candidate", "terraform"],
            curation_status=CurationStatus.CANDIDATE,
            provenance={"source_registry": "terraform_registry", "license": "Apache-2.0"}
        )
        self.repo.save(candidate)

        saved = self.repo.get_by_identifier(candidate.identifier)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.curation_status, CurationStatus.CANDIDATE)
        self.assertFalse(saved.can_execute())  # Invariant INV-1 enforced

    def test_04_refusal_gate_kills_zero_score_trap(self):
        """
        Refusal Gate (BKND-26 / CHAT-06):
        Nonsense queries with zero semantic alignment or keyword match must return empty list.
        """
        nonsense_queries = [
            "xyzzy completely unrelated query 999111 nonsense",
            "teleport quantum flux capacitor hyperdrive overdrive",
            "bake chocolate strawberry birthday cake recipe ingredients",
        ]
        for query in nonsense_queries:
            results = self.repo.search_hybrid(query, top_k=5)
            self.assertEqual(
                results,
                [],
                f"Refusal Gate failed! Nonsense query '{query}' matched items: {results}"
            )

    def test_05_hybrid_search_precision_and_rrf_scoring(self):
        """
        Hybrid search correctly surfaces relevant playbooks with RRF score fusion.
        """
        query = "renew ssl certificate on f5 vip edge"
        results = self.repo.search_hybrid(query, top_k=5)
        self.assertGreater(len(results), 0, f"Query '{query}' returned no results")

        top_item, top_score, meta = results[0]
        self.assertIn("f5", top_item.identifier.lower() + top_item.name.lower())
        self.assertGreater(top_score, 0.0)
        self.assertIn("dense_score", meta)
        self.assertIn("sparse_score", meta)

    def test_06_disambiguation_gate_triggers_on_close_candidates(self):
        """
        Disambiguation Gate (CHAT-08):
        When top-2 candidates have a fused RRF score difference < 0.05,
        the search marks disambiguation_required = True.
        """
        # Insert two near-identical items
        item_a = CatalogItem(
            id="test-disambig-01",
            identifier="test.disambig.f5-edge-renew",
            name="Renew SSL Certificate F5 Edge Gateway",
            engine=ExecutionEngineType.ANSIBLE,
            git_repo="git@pnc:sec.git",
            git_commit_sha="1111222233334444555566667777888899990000",
            playbook_or_module_path="playbooks/edge_renew.yml",
            risk_tier=RiskTier.HIGH,
            requires_maker_checker=True,
            requires_chg=True,
            input_schema={},
            category="network",
            description="Renews SSL certificates on F5 edge gateway appliances.",
            tags=["f5", "ssl", "edge"],
            curation_status=CurationStatus.CURATED
        )
        item_b = CatalogItem(
            id="test-disambig-02",
            identifier="test.disambig.f5-core-renew",
            name="Renew SSL Certificate F5 Core Gateway",
            engine=ExecutionEngineType.ANSIBLE,
            git_repo="git@pnc:sec.git",
            git_commit_sha="2222333344445555666677778888999900001111",
            playbook_or_module_path="playbooks/core_renew.yml",
            risk_tier=RiskTier.HIGH,
            requires_maker_checker=True,
            requires_chg=True,
            input_schema={},
            category="network",
            description="Renews SSL certificates on F5 core gateway appliances.",
            tags=["f5", "ssl", "core"],
            curation_status=CurationStatus.CURATED
        )
        self.repo.save(item_a)
        self.repo.save(item_b)

        query = "renew ssl certificate f5 gateway"
        results = self.repo.search_hybrid(query, top_k=5)
        self.assertGreaterEqual(len(results), 2)
        top_item, top_score, meta = results[0]
        self.assertTrue(meta["disambiguation_required"], "Expected disambiguation gate to trigger on twin items")
        self.assertLess(meta["delta_score"], 0.05)


if __name__ == "__main__":
    unittest.main()
