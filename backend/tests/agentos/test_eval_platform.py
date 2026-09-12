"""
Project Vulcan: Tests for Multi-Tier Evaluation Platform & Statistics (AGENT-12)
"""
import pytest
from app.agentos.eval_platform import AgentOSEvalPlatform


def test_eval_platform_tier0_smoke_evaluation():
    summary = AgentOSEvalPlatform.run_tier_eval(tier=0)
    assert summary.tier == 0
    assert summary.total_scenarios == 20
    assert summary.pass_rate_pct >= 80.0
    assert summary.bootstrap_ci_95[0] <= summary.pass_rate_pct
    assert summary.bootstrap_ci_95[1] >= summary.pass_rate_pct
    assert summary.risk_weighted_score > 0.0
    assert "database" in summary.domain_breakdown


def test_eval_platform_tier4_adversarial_evaluation():
    summary = AgentOSEvalPlatform.run_tier_eval(tier=4)
    assert summary.tier == 4
    assert summary.total_scenarios == 50
    assert summary.pass_rate_pct >= 90.0


def test_bootstrap_confidence_intervals():
    results = [True] * 90 + [False] * 10
    low, high = AgentOSEvalPlatform.calculate_bootstrap_ci(results, num_bootstrap=500)
    assert 80.0 <= low <= 93.0
    assert 87.0 <= high <= 98.0
    assert low < high
