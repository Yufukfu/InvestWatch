# 0316. Default thresholds from the gold-set evaluation

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written from Damian's decision (relayed by the coordinating session) on follow-up 17 of `analytics-eval-calibration`; accepted by: pending approval of the PR
- Supersedes: the default values of [0305](0305-threshold-storage.md) (0.6 / 0.5 / 0.7). 0305's storage decision (Redis key `iw:settings:thresholds`, written by the API, read by analytics) stays.

## Context

[0305](0305-threshold-storage.md) set the defaults the API writes when `iw:settings:thresholds` is missing: M1 0.6, M2 0.5, M3 0.7. They were chosen before any module was measured. The gold-set evaluation ([0312](0312-gold-set-evaluation.md), `analytics/eval/`) then measured the rules-only scores. M3 never reaches 0.7: the S3.4 cap holds rules-only scores at 0.62 or below, so a fresh stack shows no M3 alert at all, and a slider move from 0.7 to 0.9 changes nothing (follow-up 17). The jury tests "wpływ zmian parametrów progowych na wyniki w panelu kalibracji" on the default stack (Opis §6).

Rules-only module curves on the committed gold set (69 lines; build: `main` bb770a0, which includes `analytics-m1-m3`, with this change), on the 0.05 grid. The plateau is every threshold whose F1 is within 0.02 of the best:

| Module | Gold cases (pos / neg) | Plateau (F1 within 0.02 of best) | Chosen: its higher end | At the ADR 0305 default |
|---|---|---|---|---|
| M1 | 18 (10 / 8) | 0.40-0.65, F1 0.889 | 0.65: precision 1.0, recall 0.8, F1 0.889 (tp 8, fp 0, fn 2, tn 8) | 0.6: precision 1.0, recall 0.8, F1 0.889 |
| M2 | 35 (23 / 12) | 0.05-0.25, F1 0.667 | 0.25: precision 0.923, recall 0.522, F1 0.667 (tp 12, fp 1, fn 11, tn 11) | 0.5: precision 0.833, recall 0.217, F1 0.345 |
| M3 | 18 (10 / 8) | 0.25 only, F1 0.778 | 0.25: precision 0.875, recall 0.7, F1 0.778 (tp 7, fp 1, fn 3, tn 7) | 0.7: precision 1.0 (nothing flagged), recall 0, F1 0 |

For M3 also at 0.4, the ADR 0308 gate cap: precision 1.0, recall 0.4, F1 0.571 (tp 4, fp 0, fn 6, tn 8).

## Options considered

1. **Keep 0305's values.** M3 finds nothing by default (F1 0 at 0.7), and M2's F1 at 0.5 is 0.4.
2. **Best-F1 threshold per module from the rules-only gold run, the higher end of the plateau within 0.02 of the best F1** (Damian's rule, ties to precision; the plateau refinement from the coordinating session). This gives the values above.
3. **The API recomputes the best point from the stored run at startup.** No copy to keep in sync, but the API often starts before `analytics-eval` has written a run, so the defaults would depend on start-up order.

## Decision

Option 2. `python analytics/eval/run.py --write-thresholds` writes the recommended thresholds to `analytics/eval/thresholds.json`, the one source: today `{"M1": 0.65, "M2": 0.25, "M3": 0.25}`. The report shows the plateau and the point at the old default for each module. The API image cannot read files from `analytics/` (separate build context), so `api/src/investwatch_api/thresholds.py` `DEFAULTS` is a copy, and so is `analytics/src/investwatch_analytics/events.py` `DEFAULT_THRESHOLDS` (the analytics fallback when the key is missing). `analytics/tests/test_eval_thresholds.py` fails when the file differs from a fresh rules-only run or when either copy differs from the file. The defaults apply only when the key is missing (`SET NX`); a running stack keeps the thresholds its users set, and the calibration panel still changes them.

## Consequences

- A fresh stack alerts on M3, and M2's default sits at its best measured F1 instead of 0.4.
- A rule or gold-set change that moves a module's best F1 fails the analytics tests until someone reruns `--write-thresholds` and copies the values into the two constants. That coupling is intended: the defaults stay measured.
- The values are rules-only. When the LLM layer or more rules land, scores rise, and the defaults move with the next `--write-thresholds`.
- M2 0.25 is low because only part of the 18 rules run today; the README states this next to the numbers.
- **M3 0.25 is below the ADR 0308 gate cap (0.4).** A finding with no S3.4 recommendation is capped at 0.4, so with this default a capped finding raises `finding.high_risk` again; in the gold run the one M3 false positive at 0.25 is such a case (`m3-plain-crypto-signals`, 0.378). ADR 0308 rejected an alert from service wording alone. Rules-only, S3.4 is never `fail` (it needs the model), so at 0.4 or above M3 alerts only on the few rule candidates (recall 0.4). This trade-off is open for Damian: keep 0.25 (best F1), or floor M3 at the gate cap until the LLM layer confirms S3.4.
- With the API's medium band (`medium` from threshold - 0.2), M2 and M3 findings count as `medium` from a score of 0.05, so nearly every M2/M3 finding is at least `medium`.
- The mock server keeps 0.6 / 0.5 / 0.7 (`contracts/mocks/thresholds.json`, untouched by rule): the "one source" covers the real API and analytics, not the test double.
- `contracts/mocks/thresholds.json` and the OpenAPI example keep 0.6 / 0.5 / 0.7: the mocks stay untouched (Damian's rule), and the example is not a default.
