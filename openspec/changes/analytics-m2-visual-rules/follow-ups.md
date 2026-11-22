# Follow-ups

## Evaluation (rules-only, `eval/run.py --module M2`, gold 35 labeled M2 samples)

| Run | M2 at 0.1: P / R / F1 (tp fp fn tn) | best threshold |
|---|---|---|
| baseline `origin/main` 62f1a475 | 0.944 / 0.739 / 0.829 (17 1 6 11) | 0.1 |
| after R5, R7, R8, R13 + year range | 0.947 / 0.783 / 0.857 (18 1 5 11); at 0.05: 0.952 / 0.870 / 0.909 (20 1 3 11) | **0.05** (plateau [0.05]) |

Per rule (strict = review, gold): R5, R7, R8 and R13 P/R 1.0 / 1.0, no uncertain, no applicability error. R14's one applicability error (gold `m2-r13-past-performance-dominates`, `2021-2025` not detected) is gone; every other rule is unchanged.

The recommended M2 threshold moved from 0.1 to 0.05, so `tests/test_eval_thresholds.py` fails on this branch. That is left on purpose: the default thresholds belong to `analytics/analytics-deepseek-default`, and Damian decides (`python eval/run.py --write-thresholds`, then `events.DEFAULT_THRESHOLDS` and the API's `DEFAULTS`, ADR 0316).

## Items

| Item | Disposition |
|---|---|
| R5 "przesłonięcia przez inne elementy": the renderer reports no overlap between blocks, so occlusion by a banner or a cookie layer is not checked | new-item (renderer: an `occluded` flag per block) |
| `tests/test_rules.py` exact implemented list and the "Catalogue is complete" scenario are also edited by the R9/R10 text-rules change; whichever merges second resolves a one-line conflict | docs |
| `test_eval_thresholds` red until the M2 default moves to 0.05 (or the gold changes) | docs (Damian decides) |
