## REMOVED Requirements

### Requirement: Calibration curve
**Reason**: Analyst labels replaced the stored gold-set run, so one or two labels collapsed the calibration panel to a curve of one or two samples. Damian decided that labels and the gold run are combined (ADR 0312).
**Migration**: Replaced by "Calibration curve from labels and the gold run" and "Calibration counting conventions" below. Same route, parameters and response shape (`contracts/openapi.yaml`); only how the counts are formed changes.

## ADDED Requirements

### Requirement: Calibration curve from labels and the gold run
`GET /api/calibration?module=` SHALL return one point per threshold 0.05, 0.10, ..., 0.95 whose `tp`, `fp`, `fn`, `tn` are the analyst-label counts of that module plus the counts of the latest stored `calibration_points` run of that module at the same threshold. `labeled_samples` SHALL be the labeled findings plus the run's `labeled_samples`. `current_threshold` SHALL come from `iw:settings:thresholds`. The response shape SHALL stay as in `contracts/openapi.yaml`.

#### Scenario: Curve from analyst labels
- **WHEN** M2 has confirmed findings with scores 0.9 and 0.4 and false positives with scores 0.6 and 0.2, and no stored run
- **THEN** `labeled_samples` is 4, there are 19 points from 0.05 to 0.95, and the point at 0.5 has `tp: 1, fp: 1, fn: 1, tn: 1, precision: 0.5, recall: 0.5, f1: 0.5`

#### Scenario: Labels added to a stored run
- **WHEN** M2 has the four labeled findings above and the latest stored run has `tp: 10, fp: 2, fn: 3, tn: 20` and `labeled_samples: 35` at 0.5
- **THEN** the point at 0.5 has `tp: 11, fp: 3, fn: 4, tn: 21`, `precision: 0.786`, `recall: 0.733`, `f1: 0.759`, and `labeled_samples` is 39

#### Scenario: One label does not replace the gold curve
- **WHEN** M2 has one confirmed finding with score 0.9 and a stored run of 35 samples
- **THEN** `labeled_samples` is 36 and every point keeps the stored run's counts plus at most one

#### Scenario: Stored run when there are no labels
- **WHEN** M2 has no labeled findings and two stored runs exist
- **THEN** only the newer run's points are returned as stored, sorted by threshold, with that run's `labeled_samples`

#### Scenario: No labels and no run
- **WHEN** M3 has no labeled findings and no stored run
- **THEN** the response is 200 with `points: []`, `labeled_samples: 0` and the current M3 threshold

#### Scenario: Module missing
- **WHEN** a client calls `/api/calibration` without `module`
- **THEN** the response is 422

### Requirement: Calibration counting conventions
For labels, `confirmed` SHALL be a positive and `false_positive` a negative; other statuses SHALL be unlabeled. A positive prediction SHALL be `score >= t`. Each point SHALL have `precision = tp / (tp + fp)` (1.0 when nothing is predicted positive), `recall = tp / (tp + fn)` (0.0 without positives) and `f1` their harmonic mean (0.0 when both are 0), each rounded to 3 decimals from the summed counts.

#### Scenario: Unlabeled findings do not count
- **WHEN** M2 also has findings with status `new`, `in_review` or `closed`
- **THEN** they change neither `labeled_samples` nor any count

#### Scenario: Nothing predicted positive
- **WHEN** no labeled finding and no stored count is predicted positive at a threshold
- **THEN** that point has `precision: 1.0` and `recall: 0.0`
