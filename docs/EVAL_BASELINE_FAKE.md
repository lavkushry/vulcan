# Project Vulcan: 500-Scenario Golden Evaluation Baseline (CHAT-20)

> [!WARNING]
> **TUNED-ON BASELINE LIMITATION (Flag 3 Audit Notice)**:
> The **82.00% Top-1** and **97.33% Top-3** routing figures represent a *tuned-on baseline* calibrated
> against the hermetic fake provider. This establishes a measured, honest floor for regression testing,
> but does **NOT** measure real-world generalization against live semantic variation. Real-world generalization
> remains unmeasured until the live model evaluation on September 22, 2026.

- **Evaluation Timestamp**: `2026-09-09T04:45:36Z`
- **Provider Mode**: `FAKE`
- **Dataset Source**: `evals/golden/scenarios.v2.jsonl`
- **Total Scenarios Evaluated**: **500**

## 1. Category Evaluation Summary

| Category | Scenarios | Primary Metric | Score | Target / Status |
| :--- | :---: | :--- | :---: | :---: |
| **Tool Routing (Top-1)** | 150 | Exact Playbook Accuracy | **82.00%** | Baseline (123/150) |
| **Tool Routing (Top-3)** | 150 | Candidate Recall@3 | **97.33%** | Baseline (146/150) |
| **Slot-Filling F1** | 150 | Field-level F1 Score | **100.00%** | P: 100.0% / R: 100.0% |
| **Adversarial Defense** | 100 | Prompt Injection Refusal | **100.00%** | 100.0% Gate (Zero-Tolerance) |
| **Multi-Turn Sessions** | 50 | 2-Turn Slot Accumulation | **100.00%** | Baseline (50/50) |
| **ServiceNow Hydration** | 25 | CHG Verification & CI Match | **100.00%** | Baseline (25/25) |
| **Out-of-Scope Refusal** | 15 | Non-Automation Recall | **100.00%** | 100.0% Gate (Zero-Tolerance) |
| **False-Refusal Validation** | 10 | False Refusal on Risky Words | **0.00%** | 0.0% Gate (Zero-Tolerance) |

## 2. Top-1 Non-Match Classification (Flag 4 Audit)

Out of 150 routing scenarios, **123** matched Top-1 exactly (82.00%).
The remaining **27** non-matches bifurcate into two operationally distinct populations:

- **Disambiguation-Surfaced (Safe Bento Choice Cards)**: **15 cases (10.00%)**.
  When semantic ambiguity (`delta_sim < 0.05`) occurs, the resolver halts automated execution and presents the operator
  with candidate choice cards. In 11 of these 15 cases, the expected target is among the presented top-3 candidates.
  No silent misroute or erroneous automated execution occurs.
- **Silent Misroutes (Quality Gaps)**: **12 cases (8.00%)**.
  The hermetic resolver confidently matched an incorrect playbook (`status: NEEDS_INPUT` or `READY`).
  These 12 scenarios isolate the exact quality gap that dense vector embeddings must eliminate on September 22.

## 3. Operator Experience Derived Scorecard (The Baseline Triple)

Combining Top-1 accuracy with disambiguation choice card outcomes reveals what an operator actually experiences at the console:

| Operator Outcome | Scenarios | Percentage | Operational Meaning |
| :--- | :---: | :---: | :--- |
| **Correct playbook, first try** | **123** | **82.0%** | Immediate intent match without manual disambiguation |
| **Choice card containing the right answer** | **11** | **7.3%** | Operator selects target playbook from presented Bento card |
| **Choice card without the right answer (dead end)** | **4** | **2.7%** | Disambiguation triggered or top-3 pool lacks target playbook |
| **Silently routed to the wrong playbook** | **12** | **8.0%** | Confident incorrect Top-1 match (quality defect) |

> [!IMPORTANT]
> ### The Baseline Triple (Scorecard for Sept 22 Live Provider)
> - **Operator-Reachable Correct**: **89.3%** (134 / 150)
> - **Silently Wrong**: **8.0%** (12 / 150)
> - **Dead-End Choice Cards**: **2.7%** (4 / 150)
>
> That triple is the honest shape of the fake provider — and it is precisely the scorecard the live model
> gets graded against on the 22nd: **Does 89.3% reachable go up, and does 8.0% silent go to zero?**

## 4. ITSM Multi-Platform Ticket Governance (Flag 1)

- Broadened ticket pattern detection across ServiceNow (`CHG`, `INC`, `RITM`) and Remedy (`CRQ`).
- All routing prompts decouple ticket trigger tokens, preventing artificial gate tripping.
- Fail-closed verification: any unknown or unapproved ticket (`CRQ-UNKNOWN-404`, `CHG-FABRICATED-999`) halts with `REFUSED`.

## 5. Telemetry, Tokenomics & Operational Metrics

| Metric | Measured Value | Standard / Limit | Status |
| :--- | :---: | :---: | :---: |
| **Latency p50** | `0.87 ms` | `< 50.0 ms` | PASS |
| **Latency p95** | `1.85 ms` | `< 100.0 ms` | PASS |
| **Latency Mean** | `0.88 ms` | `< 50.0 ms` | PASS |
| **Mean Tokens / Call** | `430.8` | Working memory budget | PASS |
| **Max Tokens / Call** | `653` | `< 2,500` max limit | PASS |
| **Disambiguation Rate** | `3.20%` | Semantic ambivalence gate | INFORMATIONAL |

## 6. CI Regression Gate & Ratchet Rule Verification (Flag 2)

> [!NOTE]
> **THE RATCHET RULE**: Gate thresholds may strictly ratchet UP, never silently down.
> Programmatic floors (`RATCHET_FLOORS`) enforce that no regression threshold can be lowered.

| Metric Checked | Measured | Threshold | Gate Status |
| :--- | :---: | :---: | :---: |
| `adversarial_refusal_percent` | `100.00%` | `== 100.0` | **✓ PASS** |
| `out_of_scope_refusal_recall_percent` | `100.00%` | `== 100.0` | **✓ PASS** |
| `false_refusal_rate_percent` | `0.00%` | `== 0.0` | **✓ PASS** |
| `token_budget_compliant` | `True` | `== True` | **✓ PASS** |
| `routing_top_1_percent` | `82.00%` | `>= 75.0` | **✓ PASS** |
| `routing_top_3_percent` | `97.33%` | `>= 90.0` | **✓ PASS** |
| `slot_filling_f1_percent` | `100.00%` | `>= 98.0` | **✓ PASS** |
| `multi_turn_accuracy_percent` | `100.00%` | `>= 98.0` | **✓ PASS** |
| `ticket_hydration_accuracy_percent` | `100.00%` | `>= 98.0` | **✓ PASS** |

> **Overall Gate Decision**: **PASSED (GREEN)**
