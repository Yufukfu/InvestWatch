## MODIFIED Requirements

### Requirement: Default thresholds from the evaluation
`analytics/eval/thresholds.json` SHALL hold the default threshold per module and SHALL be the one source of the default thresholds: the API's defaults (written to `iw:settings:thresholds` only when the key is missing) and the analytics fallback defaults SHALL equal it. A module's value SHALL come from a rules-only run of the committed gold set, except an LLM-measured module (M1), whose value SHALL lie on the F1 plateau of the committed LLM gold run.

#### Scenario: Committed defaults match the evaluation
- **WHEN** the committed gold set is evaluated rules-only on this build
- **THEN** each module's `default_threshold` except M1's equals its value in `analytics/eval/thresholds.json`

#### Scenario: LLM-measured default
- **WHEN** `analytics/eval/llm-run-deepseek-flash.json` is read
- **THEN** M1's value in `analytics/eval/thresholds.json` (0.75) has an `f1` within 0.02 of that run's best M1 `f1`
- **AND** the run's `gold_sha256` equals the committed gold set's sha256
- **AND** this build's rules-only M1 `default_threshold` equals the run's recorded `rules_only_default_threshold`

#### Scenario: Rules-only fallback at an LLM-measured default
- **WHEN** the committed gold set is evaluated rules-only
- **THEN** the M1 point at M1's default threshold has `fp` 0 and `tp` above 0

#### Scenario: Copies match the file
- **WHEN** the API defaults and the analytics fallback defaults are read
- **THEN** both equal `analytics/eval/thresholds.json`
- **AND** a key that is already set is left unchanged

#### Scenario: Writing the file
- **WHEN** the evaluation runs with `--write-thresholds`
- **THEN** `analytics/eval/thresholds.json` holds the run's default thresholds, M1 keeps its LLM-measured value, and a module without one keeps its previous value

#### Scenario: LLM-measured default off the plateau
- **WHEN** `--write-thresholds` runs and M1's LLM-measured value has an `f1` more than 0.02 below the recorded run's best
- **THEN** the run exits 2 and the file is unchanged

#### Scenario: Thresholds not written from a bad run
- **WHEN** `--write-thresholds` is combined with `--llm`, or a gold document crashed the pipeline, or the file is not a JSON object
- **THEN** the file is unchanged; with `--llm` or a bad file the run exits 2 (with `--llm` before analyzing), after a crash it exits 1
