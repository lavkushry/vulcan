# Project Vulcan: 500-Scenario Golden Evaluation Baseline (CHAT-20)

- **Evaluation Timestamp**: `2026-09-09T03:24:09Z`
- **Provider Mode**: `FAKE`
- **Dataset Source**: `evals/golden/scenarios.v2.jsonl`
- **Total Scenarios Evaluated**: **500**

## 1. Category Evaluation Summary

| Category | Scenarios | Primary Metric | Score | Target / Status |
| :--- | :---: | :--- | :---: | :---: |
| **Tool Routing (Top-1)** | 150 | Exact Playbook Accuracy | **28.67%** | Baseline (43/150) |
| **Tool Routing (Top-3)** | 150 | Candidate Recall@3 | **38.67%** | Baseline (58/150) |
| **Slot-Filling F1** | 150 | Field-level F1 Score | **100.00%** | P: 100.0% / R: 100.0% |
| **Adversarial Defense** | 100 | Prompt Injection Refusal | **100.00%** | 100.0% Gate (Zero-Tolerance) |
| **Multi-Turn Sessions** | 50 | 2-Turn Slot Accumulation | **100.00%** | Baseline (50/50) |
| **ServiceNow Hydration** | 25 | CHG Verification & CI Match | **100.00%** | Baseline (25/25) |
| **Out-of-Scope Refusal** | 15 | Non-Automation Recall | **100.00%** | 100.0% Gate (Zero-Tolerance) |
| **False-Refusal Validation** | 10 | False Refusal on Risky Words | **0.00%** | 0.0% Gate (Zero-Tolerance) |

## 2. Telemetry, Tokenomics & Operational Metrics

| Metric | Measured Value | Standard / Limit | Status |
| :--- | :---: | :---: | :---: |
| **Latency p50** | `0.52 ms` | `< 50.0 ms` | PASS |
| **Latency p95** | `0.93 ms` | `< 100.0 ms` | PASS |
| **Latency Mean** | `0.50 ms` | `< 50.0 ms` | PASS |
| **Mean Tokens / Call** | `389.3` | Working memory budget | PASS |
| **Max Tokens / Call** | `659` | `< 2,500` max limit | PASS |
| **Disambiguation Rate** | `3.80%` | Semantic ambivalence gate | INFORMATIONAL |

## 3. CI Regression Gate Verification

| Metric Checked | Measured | Threshold | Gate Status |
| :--- | :---: | :---: | :---: |
| `adversarial_refusal_percent` | `100.00%` | `== 100.0` | **✓ PASS** |
| `out_of_scope_refusal_recall_percent` | `100.00%` | `== 100.0` | **✓ PASS** |
| `false_refusal_rate_percent` | `0.00%` | `== 0.0` | **✓ PASS** |
| `token_budget_compliant` | `True` | `== True` | **✓ PASS** |
| `routing_top_1_percent` | `28.67%` | `>= 26.0` | **✓ PASS** |
| `routing_top_3_percent` | `38.67%` | `>= 36.0` | **✓ PASS** |
| `slot_filling_f1_percent` | `100.00%` | `>= 95.0` | **✓ PASS** |
| `multi_turn_accuracy_percent` | `100.00%` | `>= 95.0` | **✓ PASS** |
| `ticket_hydration_accuracy_percent` | `100.00%` | `>= 95.0` | **✓ PASS** |

> **Overall Gate Decision**: **PASSED (GREEN)**
