# 0319. M2 default threshold 0.05, re-measured after all 18 rules are built

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written from Damian's decision (relayed by the coordinating session); accepted by: pending approval of PR #159 (`analytics-m2-visual-rules`)
- Supersedes: only the M2 default value (0.1) recorded in [ADR 0316](0316-default-thresholds-from-evaluation.md) and restated in [ADR 0318](0318-hosted-llm-deepseek-flash.md). The method of 0316 (best F1 of the rules-only gold run, the upper end of the plateau, `eval/thresholds.json` as the one source) and 0318's M1 rule are unchanged.

## Context

M2's default threshold was 0.1, the best F1 of the rules-only gold run when M2 had 13 implemented rules. Two changes then completed the catalogue:
- `analytics-m2-text-rules` (PR #160) added R9 and R10.
- `analytics-m2-visual-rules` (PR #159) added R5, R7, R8 and R13.

All 18 ZASÓB rules (19 entries, with R12a and R12b) now run. ADR 0316 asks for a re-measure after any rule change that moves the best F1, and `tests/test_eval_thresholds.py` failed on the combined code. Its message was `assert 0.05 == 0.1`.

Why the best threshold falls: the M2 score is the weighted share of failing rules among the applicable ones, Σ(weight·fail) / Σ(weight·applicable). Here weight is high 3, medium 2, low 1, and `uncertain` counts as half a fail (`analytics/src/investwatch_analytics/modules/m2.py`, `score`). Every new rule that applies and passes adds to the denominator only. So a material with one real violation scores lower than before, and a threshold that caught it with 13 rules can miss it with 18. The gold set (69 documents, 35 labeled for M2) did not change.

## Evidence (2026-11-22, branch `analytics/analytics-m2-visual-rules` after merging `main` 313c625)

`python eval/run.py --write-thresholds` (rules-only) and `python eval/run.py --llm --module M2`. The LLM run used DeepSeek Flash with `LLM_TIMEOUT_S=60` and `LLM_DOC_BUDGET_S=90`; all 29 calls returned 200. The M2 cases are 23 positive and 12 negative.

| Run | Threshold | P | R | F1 | TP / FP / FN / TN | F1 plateau |
|---|---|---|---|---|---|---|
| rules-only | 0.1 (old default) | 0.950 | 0.826 | 0.884 | 19 / 1 / 4 / 11 | 0.05 only |
| rules-only | **0.05** | 0.955 | 0.913 | 0.933 | 21 / 1 / 2 / 11 | |
| DeepSeek Flash | 0.1 | 1.0 | 0.870 | 0.930 | 20 / 0 / 3 / 12 | 0.05 only |
| DeepSeek Flash | **0.05** | 1.0 | 0.957 | 0.978 | 22 / 0 / 1 / 12 | |

For comparison, the rules-only run on `main` 62f1a475, before R5, R7, R8, R9, R10 and R13, gave P 0.944 / R 0.739 / F1 0.829 (17 / 1 / 6 / 11) at 0.1. That was then its best point.

## Options

1. Keep 0.1. On this gold set it misses 2 more positives rules-only and 2 more with DeepSeek, with no gain in precision.
2. **0.05, the measured best F1 (0316's rule), on both runs.**
3. Rescale the M2 score, for example by dividing by the maximum a single violation can reach, so that the threshold stays put as rules are added. That would change what the stored `score` means for the API and dashboard after the contract freeze. It is out of scope for the hand-in.

## Decision

Option 2: the M2 default is **0.05**. The rules-only run's plateau is the single point 0.05, so it is also the upper end that 0316 asks for. The LLM run agrees.

- `analytics/eval/thresholds.json` is `{"M1": 0.75, "M2": 0.05, "M3": 0.4}`. It was written by `--write-thresholds`, which keeps M1 from the recorded DeepSeek run (ADR 0318) and M3 at its gate cap.
- The copies `events.DEFAULT_THRESHOLDS` (analytics) and `DEFAULTS` (`api/src/investwatch_api/thresholds.py`) are updated in the same PR, and `tests/test_eval_thresholds.py` is green again.
- A deployment with `iw:settings:thresholds` already set keeps its stored values. The API writes defaults only when the key is missing (ADR 0305).

Rationale:
- It is 0316's rule applied to the current code.
- Both runs gain recall, rules-only 0.826 → 0.913 and DeepSeek 0.870 → 0.957, and precision does not drop.

## Consequences

- 0.05 is the lowest point of the evaluated grid (0.05-0.95). If M2's best threshold falls further, the grid cannot show it. The next M2 rule change should re-measure, and option 3 should be considered then rather than lowering the grid.
- One medium-severity `uncertain` alone, among about 14 applicable rules, scores about 0.035. That stays below 0.05, so a single unconfirmed signal does not raise a high-risk alert by itself.
- The recorded LLM run file `analytics/eval/llm-run-deepseek-flash.json` still describes `main` 0434553b. It is the source only for M1 (0318), and this decision does not replace it.
