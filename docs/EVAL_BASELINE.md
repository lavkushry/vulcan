# Project Vulcan: 500-Scenario Golden Evaluation Baseline (CHAT-20)

> [!WARNING]
> **TUNED-ON BASELINE LIMITATION (Flag 3 Audit Notice)**:
> The **82.00% Top-1** and **97.33% Top-3** routing figures represent a *tuned-on baseline* calibrated
> against the hermetic fake provider. This establishes a measured, honest floor for regression testing,
> but does **NOT** measure real-world generalization against live semantic variation.

- **Evaluation Timestamp**: `2026-09-09T06:35:17Z`
- **Provider Mode**: `FAKE`
- **Embedding Provider**: `semantic-cluster-1536`
- **Chat / Slot Engine**: `deterministic-fake` (`deterministic_grammar_regex_fsm`)
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
  with candidate choice cards. In 12 of these 15 cases, the expected target is among the presented top candidates.
  No silent misroute or erroneous automated execution occurs.
- **Silent Misroutes (Quality Gaps)**: **12 cases (8.00%)**.
  The resolver matched an incorrect playbook (`status: NEEDS_INPUT` or `READY`).

## 3. Operator Experience Derived Scorecard (The Baseline Triple)

Combining Top-1 accuracy with disambiguation choice card outcomes reveals what an operator actually experiences at the console:

| Operator Outcome | Scenarios | Percentage | Fake Baseline | Diff vs Baseline | Operational Meaning |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Correct playbook, first try** | **123** | **82.0%** | 82.0% | +0.0% | Immediate intent match without manual disambiguation |
| **Choice card containing the right answer** | **12** | **8.0%** | 7.3% | +0.7% | Operator selects target playbook from presented Bento card |
| **Choice card without the right answer (dead end)** | **3** | **2.0%** | 2.7% | -0.7% | Disambiguation triggered but top-3 pool lacks target playbook |
| **Silently routed to the wrong playbook** | **12** | **8.0%** | 8.0% | +0.0% | Confident incorrect Top-1 match (quality defect) |

> [!IMPORTANT]
> ### The Operator Experience Scorecard
> - **Operator-Reachable Correct**: **90.0%** (135 / 150) [Baseline: 89.3%, diff: +0.7%]
> - **Silently Wrong**: **8.0%** (12 / 150) [Baseline: 8.0%, diff: +0.0%]
> - **Dead-End Choice Cards**: **2.0%** (3 / 150) [Baseline: 2.7%, diff: -0.7%]
>
> **Provider & Engine Attribution**:
> - **Embedding Provider**: `semantic-cluster-1536`
> - **Chat Provider**: `deterministic-fake`
> - **Slot Filling Engine**: `deterministic_grammar_regex_fsm` (Deterministic Regex / Pydantic FSM)

## 4. ITSM Multi-Platform Ticket Governance (Flag 1)

- Broadened ticket pattern detection across ServiceNow (`CHG`, `INC`, `RITM`) and Remedy (`CRQ`).
- All routing prompts decouple ticket trigger tokens, preventing artificial gate tripping.
- Fail-closed verification: any unknown or unapproved ticket (`CRQ-UNKNOWN-404`, `CHG-FABRICATED-999`) halts with `REFUSED`.

## 5. Telemetry, Tokenomics & Operational Metrics

| Metric | Measured Value | Standard / Limit | Status |
| :--- | :---: | :---: | :---: |
| **Latency p50** | `2.48 ms` | `< 50.0 ms` | PASS |
| **Latency p95** | `5.03 ms` | `< 100.0 ms` | PASS |
| **Latency Mean** | `2.32 ms` | `< 50.0 ms` | PASS |
| **Mean Tokens / Call** | `427.2` | Working memory budget | PASS |
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
