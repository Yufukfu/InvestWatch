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

Option 2, with a floor for M3 (Damian). The default is the recommendation raised to the module's floor. M3's floor is the S3.4 gate cap of [0308](0308-m3-s34-gate.md) (`modules/m3.py` `GATE_CAP`, 0.4), so **M3's default is 0.4, not its best-F1 0.25**:

| M3 at | Precision | Recall | F1 | tp / fp / fn / tn |
|---|---|---|---|---|
| 0.25 (best F1) | 0.875 | 0.7 | 0.778 | 7 / 1 / 3 / 7 |
| 0.4 (gate cap, chosen) | 1.0 | 0.4 | 0.571 | 4 / 0 / 6 / 8 |

Why 0.4: it keeps ADR 0308's rule that service wording without a recommendation of instruments never reaches the alert threshold; it removes the one false `finding.high_risk` of the gold run (`m3-plain-crypto-signals`, plain crypto signals, score 0.378); and for alerts sent to a supervisor, precision comes first. M3 is re-evaluated once the LLM layer scores S3.4: rescoring S3.4 is expected to move confirmed cases to about 0.88, above the cap, and the recommendation may then rise above the floor on its own.

`python analytics/eval/run.py --write-thresholds` writes the floored defaults to `analytics/eval/thresholds.json`, the one source: today `{"M1": 0.65, "M2": 0.25, "M3": 0.4}`. The report shows the plateau and the point at the old default for each module. The API image cannot read files from `analytics/` (separate build context), so `api/src/investwatch_api/thresholds.py` `DEFAULTS` is a copy, and so is `analytics/src/investwatch_analytics/events.py` `DEFAULT_THRESHOLDS` (the analytics fallback when the key is missing). `analytics/tests/test_eval_thresholds.py` fails when the file differs from a fresh rules-only run or when either copy differs from the file. The defaults apply only when the key is missing (`SET NX`); a running stack keeps the thresholds its users set, and the calibration panel still changes them.

## Consequences

- A fresh stack alerts on M3 (at the gate cap, so only on rule-candidate recommendations), and M2's default sits at its best measured F1 (0.667) instead of 0.345.
- A rule or gold-set change that moves a module's best F1 fails the analytics tests until someone reruns `--write-thresholds` and copies the values into the two constants. That coupling is intended: the defaults stay measured.
- The values are rules-only. When the LLM layer or more rules land, scores rise, and the defaults move with the next `--write-thresholds`.
- M2 0.25 is low because only part of the 18 rules run today; the README states this next to the numbers.
- M3 alerts less than its best F1 allows: recall 0.4 instead of 0.7 rules-only, in exchange for no alert on capped findings (ADR 0308). The floor is a code constant (`THRESHOLD_FLOORS` in `evaluation/runner.py`, from `GATE_CAP`), so a change of the cap moves the default with it.
- With the API's medium band (`medium` from threshold - 0.2), M2 findings count as `medium` from a score of 0.05 (M3 from 0.2), so nearly every M2 finding is at least `medium`; a UI question for Kacper, no change here.
- The mock server keeps 0.6 / 0.5 / 0.7 (`contracts/mocks/thresholds.json`, untouched by rule): the "one source" covers the real API and analytics, not the test double.
- `contracts/mocks/thresholds.json` and the OpenAPI example keep 0.6 / 0.5 / 0.7: the mocks stay untouched (Damian's rule), and the example is not a default.
