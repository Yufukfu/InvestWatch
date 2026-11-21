## MODIFIED Requirements

### Requirement: Calibration curve
`GET /api/calibration?module=` SHALL compute the precision/recall curve from analyst labels on that module's findings together with the latest stored gold-set run of that module in `calibration_points`. For labels, `confirmed` is a positive, `false_positive` a negative, other statuses are unlabeled. For each threshold `t` in 0.05, 0.10, ..., 0.95 it SHALL count `tp` (positive, `score >= t`), `fp` (negative, `score >= t`), `fn` (positive, `score < t`) and `tn` (negative, `score < t`) over the labeled findings, add the stored run's counts at the same threshold, and compute `precision`, `recall` and `f1` from the summed counts. `labeled_samples` SHALL be the number of labeled findings plus the stored run's `labeled_samples`. `current_threshold` SHALL come from `iw:settings:thresholds`. The response shape SHALL stay as in `contracts/openapi.yaml`.

#### Scenario: Curve from analyst labels
- **WHEN** M2 has confirmed findings with scores 0.9 and 0.4 and false positives with scores 0.6 and 0.2, and no stored run
- **THEN** `labeled_samples` is 4, there are 19 points from 0.05 to 0.95, and the point at 0.5 has `tp: 1, fp: 1, fn: 1, tn: 1, precision: 0.5, recall: 0.5, f1: 0.5`

#### Scenario: Metric formulas
- **WHEN** a point is computed for threshold `t`
- **THEN** it SHALL have `precision = tp / (tp + fp)` (1.0 when nothing is predicted positive), `recall = tp / (tp + fn)` (0.0 without positives) and `f1` their harmonic mean (0.0 when both are 0), each rounded to 3 decimals

#### Scenario: Unlabeled findings do not count
- **WHEN** M2 also has findings with status `new`, `in_review` or `closed`
- **THEN** they change neither `labeled_samples` nor any count

#### Scenario: Nothing predicted positive
- **WHEN** no labeled finding and no stored count is predicted positive at a threshold
- **THEN** that point has `precision: 1.0` and `recall: 0.0`

#### Scenario: Labels added to a stored run
- **WHEN** M2 has the four labeled findings above and the latest stored run has `tp: 10, fp: 2, fn: 3, tn: 20` and `labeled_samples: 35` at 0.5
- **THEN** the point at 0.5 has `tp: 11, fp: 3, fn: 4, tn: 21`, `precision: 0.786`, `recall: 0.733`, `f1: 0.759`, and `labeled_samples` is 39

#### Scenario: One label does not replace the gold curve
- **WHEN** M2 has one confirmed finding with score 0.9 and a stored run of 35 samples
- **THEN** `labeled_samples` is 36 and every point keeps the stored run's counts plus at most one

#### Scenario: Stored run when there are no labels
- **WHEN** M2 has no labeled findings and two stored runs exist
- **THEN** only the newer run's points are returned, sorted by threshold, with that run's counts, ratios and `labeled_samples`

#### Scenario: No labels and no run
- **WHEN** M3 has no labeled findings and no stored run
- **THEN** the response is 200 with `points: []`, `labeled_samples: 0` and the current M3 threshold

#### Scenario: Module missing
- **WHEN** a client calls `/api/calibration` without `module`
- **THEN** the response is 422
