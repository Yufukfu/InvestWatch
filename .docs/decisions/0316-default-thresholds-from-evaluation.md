# 0316. Default thresholds from the gold-set evaluation

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written from Damian's decision (relayed by the coordinating session) on follow-up 17 of `analytics-eval-calibration`; accepted by: pending approval of the PR
- Supersedes: the default values of [0305](0305-threshold-storage.md) (0.6 / 0.5 / 0.7). 0305's storage decision (Redis key `iw:settings:thresholds`, written by the API, read by analytics) stays.

## Context

[0305](0305-threshold-storage.md) set the defaults the API writes when `iw:settings:thresholds` is missing: M1 0.6, M2 0.5, M3 0.7. They were chosen before any module was measured. The gold-set evaluation ([0312](0312-gold-set-evaluation.md), `analytics/eval/`) then measured the rules-only scores. M3 never reaches 0.7: the S3.4 cap holds rules-only scores at 0.62 or below, so a fresh stack shows no M3 alert at all, and a slider move from 0.7 to 0.9 changes nothing (follow-up 17). The jury tests "wpływ zmian parametrów progowych na wyniki w panelu kalibracji" on the default stack (Opis §6).

Rules-only F1 of the module curve on the committed gold set (69 lines; build: `analytics-m1-m3` 6da4f1f with this change), at 0.05 steps:

| Module | Best F1 | At threshold(s) | Point chosen | F1 at the 0305 default |
|---|---|---|---|---|
| M1 | 0.889 | 0.40-0.65 (tie) | 0.65: precision 1.0, recall 0.8 (tp 8, fn 2, tn 8) | 0.889 at 0.6 |
| M2 | 0.703 | 0.05-0.25 (tie) | 0.25: precision 0.929, recall 0.565 (tp 13, fp 1, fn 10, tn 11) | 0.4 at 0.5 |
| M3 | 0.706 | 0.25 | 0.25: precision 0.857, recall 0.6 (tp 6, fp 1, fn 4, tn 7) | 0.0 at 0.7 |

## Options considered

1. **Keep 0305's values.** M3 finds nothing by default (F1 0 at 0.7), and M2's F1 at 0.5 is 0.4.
2. **Best-F1 threshold per module from the rules-only gold run, ties to the higher threshold** (Damian's rule: precision wins a tie). This gives the values above.
3. **The API recomputes the best point from the stored run at startup.** No copy to keep in sync, but the API often starts before `analytics-eval` has written a run, so the defaults would depend on start-up order.

## Decision

Option 2. `python analytics/eval/run.py --write-thresholds` writes the recommended thresholds to `analytics/eval/thresholds.json`, the one source: today `{"M1": 0.65, "M2": 0.25, "M3": 0.25}`. The API image cannot read files from `analytics/` (separate build context), so `api/src/investwatch_api/thresholds.py` `DEFAULTS` is a copy, and so is `analytics/src/investwatch_analytics/events.py` `DEFAULT_THRESHOLDS` (the analytics fallback when the key is missing). `analytics/tests/test_eval_thresholds.py` fails when the file differs from a fresh rules-only run or when either copy differs from the file. The defaults apply only when the key is missing (`SET NX`); a running stack keeps the thresholds its users set, and the calibration panel still changes them.

## Consequences

- A fresh stack alerts on M3, and M2's default sits at its best measured F1 instead of 0.4.
- A rule or gold-set change that moves a module's best F1 fails the analytics tests until someone reruns `--write-thresholds` and copies the values into the two constants. That coupling is intended: the defaults stay measured.
- The values are rules-only. When the LLM layer or more rules land, scores rise, and the defaults move with the next `--write-thresholds`.
- M2 0.25 is low because only part of the 18 rules run today; the README states this next to the numbers.
- `contracts/mocks/thresholds.json` and the OpenAPI example keep 0.6 / 0.5 / 0.7: the mocks stay untouched (Damian's rule), and the example is not a default.
