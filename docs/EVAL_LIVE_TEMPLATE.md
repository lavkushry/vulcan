# Project Vulcan: Live-Mode Evaluation Runbook & Comparison Template (CHAT-20)

**Date of Record**: September 2026  
**Target Decision Date**: 2026-09-22 (Gemini / Claude Enterprise Key Unlock)  
**Author**: Andrej Karpathy (AI Systems Lead) & Platform SRE Lead  

---

## 1. Overview & Mandate
On **2026-09-22**, the enterprise API keys (`GEMINI_API_KEY` / `OPENAI_API_KEY`) become available for Project Vulcan's production pilot evaluation. This document defines the exact execution protocol, target thresholds, and the one-command comparison workflow to evaluate the live LLM provider against the hermetic fake baseline recorded in [`docs/EVAL_BASELINE_FAKE.md`](file:///Users/lavkushkumar/Desktop/Ideas/vulcan-control-plane/docs/EVAL_BASELINE_FAKE.md).

---

## 2. One-Command Live Evaluation Execution

Set your API credential in the shell environment and execute the evaluation harness with the `--provider live` flag:

```bash
# 1. Export live Gemini or OpenAI API key
export GEMINI_API_KEY="your-production-gemini-key"
# or
export OPENAI_API_KEY="your-production-openai-key"

# 2. Run the 500-scenario evaluation in live mode
python3 scripts/run_eval.py \
  --provider live \
  --scenarios evals/golden/scenarios.v2.jsonl \
  --output-json docs/eval_live_results.json \
  --output-md docs/EVAL_LIVE_RESULTS.md
```

If credentials are unset or invalid, `scripts/run_eval.py` fails closed with exit code `2` and emits an actionable error message without risking silent mock evaluation.

---

## 3. One-Command Automated Baseline Diff

To compute the differential delta between the hermetic fake baseline and the live model run, execute:

```bash
python3 -c "
import json
with open('docs/eval_results.json') as f1, open('docs/eval_live_results.json') as f2:
    base = json.load(f1)['metrics']
    live = json.load(f2)['metrics']

print('=' * 85)
print(f'{\"Metric\":<38} {\"Fake Baseline\":<16} {\"Live Gemini\":<16} {\"Delta\":<12}')
print('-' * 85)
for k, v_base in base.items():
    v_live = live.get(k, 'N/A')
    if isinstance(v_base, (int, float)) and isinstance(v_live, (int, float)) and not isinstance(v_base, bool):
        diff = v_live - v_base
        print(f'{k:<38} {v_base:<16.2f} {v_live:<16.2f} {diff:+10.2f}%')
    else:
        print(f'{k:<38} {str(v_base):<16} {str(v_live):<16} {\"MATCH\" if v_base == v_live else \"DIFF\"}')
print('=' * 85)
"
```

---

## 4. Key Target Thresholds for 2026-09-22

| Metric | Fake Baseline (Hermetic) | Live Pilot Target (2026-09-22) | Minimum Gate Requirement |
| :--- | :---: | :---: | :---: |
| **Tool Routing (Top-1)** | 28.67% | **≥ 99.20%** | ≥ 95.00% |
| **Tool Routing (Top-3)** | 38.67% | **≥ 99.80%** | ≥ 98.00% |
| **Slot-Filling F1** | 100.00% | **≥ 99.50%** | ≥ 98.00% |
| **Adversarial Refusal** | 100.00% | **100.00%** | **100.00% (Zero-Tolerance)** |
| **Out-of-Scope Refusal Recall** | 100.00% | **100.00%** | **100.00% (Zero-Tolerance)** |
| **False-Refusal Rate** | 0.00% | **0.00%** | **0.00% (Zero-Tolerance)** |
| **Multi-Turn Accumulation** | 100.00% | **≥ 99.00%** | ≥ 95.00% |
| **ServiceNow Ticket Hydration**| 100.00% | **100.00%** | 100.00% |
| **Latency p95** | 0.93 ms | **< 1,500 ms** | < 2,500 ms |
| **Working Memory Limit** | 659 tokens | **< 2,500 tokens** | < 2,500 tokens (Hard Cap) |

---

## 5. Fail-Safe & Degradation Protocol
In the event of upstream LLM downtime, rate-limiting (`429`), or network disconnect during live operations:
1. The backend automatically catches network exceptions and invokes the hermetic fallback provider.
2. If similarity falls below the calibrated refusal gate (`dense < 0.35` and `sparse == 0.0`), the system strictly responds with `REFUSED` (killing the zero-score trap).
3. No ambiguous or hallucinated playbook identifier is ever returned to an operator.
