# gold-set-evaluation Specification

## Purpose

The labeled gold set in `analytics/eval/` and the evaluation that measures M1-M3 against it: precision, recall and F1 per module and per rule or signal, counted like `GET /api/calibration`; the stored calibration run the panel shows on a fresh stack; and the default thresholds derived from it (ADRs 0312 and 0316).

## Requirements

### Requirement: Gold-set file
The gold set SHALL be `analytics/eval/gold.jsonl`, one JSON object per line with a unique `id`, an `origin`, a `basis` naming the criterion it was written from, an optional `hard_case`, a `document` that is a valid `ScrapedDocument` v1 (`.docs/integration-plan.md` §3), and `expect`: module (`M1`, `M2`, `M3`) to `{label, rules}`. `label` SHALL be `positive` or `negative`; `rules` SHALL map a rule or signal id of that module to `fail`, `pass` or `not_applicable`.

#### Scenario: One document labeled for two modules
- **WHEN** a line has `expect` with `M1` positive and `M3` positive
- **THEN** the document is scored once for M1 and once for M3, and it adds one to `labeled_samples` of each

#### Scenario: Omitted rule is not scored
- **WHEN** a line labels only `R3` for M2 and the pipeline also returns `R2: fail` for that document
- **THEN** `R2`'s metrics do not count that document

#### Scenario: Coverage per module
- **WHEN** the committed gold set is loaded
- **THEN** each of M1, M2 and M3 has at least 15 labeled documents with at least 5 positives and 5 negatives, and every implemented rule or signal has at least one `fail` and one `pass` label

#### Scenario: Every ZASÓB rule has a pair
- **WHEN** the committed gold set is loaded
- **THEN** each of R1-R18 (R12a and R12b separately) has at least one `fail` and one `pass` label under M2, whether implemented or not

### Requirement: Gold-set origins and privacy
`origin` SHALL be `synthetic` (written by us), `zasob-example` (built around a phrasing quoted in the ZASÓB or Opis documents) or `uknf-sample` (official sample material, none available so far). All three SHALL be loaded and scored the same way, with no code change to add one. Documents SHALL name only fictional firms, handles and domains, SHALL hold no real person's personal data, and the gold set SHALL NOT read or modify `contracts/mocks/`.

#### Scenario: Fictional firms only
- **WHEN** the committed gold set and `analytics/eval/registry.csv` are loaded
- **THEN** no firm in `analytics/eval/registry.csv` shares a name, alias or domain with the runtime registry under `analytics/registry/`, and every `document.author` handle is in the fictional-handles list of the labeling guide (README in `analytics/eval/`)

#### Scenario: ZASÓB phrasing
- **WHEN** the committed gold set is loaded
- **THEN** at least one `zasob-example` line contains ZASÓB's R18 example "w pełni bezpieczna – spełniamy rygorystyczne wymogi nadzorcze KNF", and every `zasob-example` line has a `basis` starting with "ZASÓB"

#### Scenario: UKNF sample item
- **WHEN** a line has `origin: uknf-sample`
- **THEN** it is validated and scored like a synthetic line, and the report counts it under `origin` `uknf-sample`

### Requirement: Gold-set validation before analysis
The evaluation SHALL validate the whole gold set before analyzing any document, and SHALL exit 2 without analyzing or writing anything when the file is missing or has no labeled line, a line is not valid JSON or repeats a key, a `document` fails `ScrapedDocument` validation, a module or label is outside the allowed values, an `id` repeats, or a rule id is not a known id of its module. Each error SHALL name the line number, the gold `id` when known and the field, never document text.

#### Scenario: Empty gold set
- **WHEN** the gold file is empty or holds only blank lines
- **THEN** the run exits 2 with "no labeled document", the report is not printed and no `calibration_points` row is written

#### Scenario: Unknown module
- **WHEN** a line has `expect` with key `M4`
- **THEN** the run exits 2 naming the line and `M4`

#### Scenario: Malformed line
- **WHEN** line 7 is not valid JSON, or its `document` has no `url`
- **THEN** the run exits 2 naming line 7 and the failing field, and the log contains no text of the document

#### Scenario: Duplicate id
- **WHEN** two lines share the `id` `m2-r3-window-edge`
- **THEN** the run exits 2 naming both line numbers

#### Scenario: Duplicate key
- **WHEN** a line's `expect.M2.rules` names `R3` twice
- **THEN** the run exits 2 naming `expect.M2.rules.R3` as a duplicate key

### Requirement: Known rule and signal ids
The known ids of a module SHALL be the ids in its loaded catalogue plus the static stage-2 list (M2 R1-R11, R12a, R12b, R13-R18; M1 S1.1-S1.7; M3 S3.1-S3.8). A known id that the loaded catalogue marks `implemented: false` SHALL be reported `not_implemented`, and a known id missing from the loaded catalogue `not_in_build`; both SHALL be valid labels.

#### Scenario: Unknown rule id
- **WHEN** a line labels `R19` (or `S1.9`) under its module
- **THEN** the run exits 2 naming that line, that id and the module, and no document is analyzed

#### Scenario: Rule id of another module
- **WHEN** a line labels `R3` under `M1`
- **THEN** the run exits 2 naming the line, `R3` and `M1`

#### Scenario: Label for a signal not in this build
- **WHEN** a line labels `S1.2: fail` under M1 and this build has no M1 catalogue
- **THEN** the run continues and the report lists `S1.2` as `not_in_build`

#### Scenario: Label for a rule not implemented yet
- **WHEN** a line labels `R5: fail` and `R5` has `implemented: false`
- **THEN** the run continues and the report lists `R5` as `not_implemented` with its label counts

### Requirement: Module curve with the API's counting
For each module with labels, the evaluation SHALL pair each labeled document's label with that module's finding score for it (0.0 when there is no finding of that module). On the thresholds 0.05, 0.10, ..., 0.95 it SHALL count `tp`, `fp`, `fn`, `tn` with a positive prediction meaning `score >= threshold`, and compute `precision`, `recall` and `f1` with the conventions of the rest-api calibration requirements.

#### Scenario: Same numbers as the API
- **WHEN** a module has positives with scores 0.9 and 0.4 and negatives with scores 0.6 and 0.2
- **THEN** there are 19 points and the point at 0.5 is `tp 1, fp 1, fn 1, tn 1, precision 0.5, recall 0.5, f1 0.5`

#### Scenario: Score equal to the threshold
- **WHEN** a positive has score exactly 0.5
- **THEN** it counts as `tp` at threshold 0.5 and as `fn` at 0.55

#### Scenario: No finding is a zero score
- **WHEN** a document labeled M1 positive is routed only to M2
- **THEN** it is an `fn` for M1 at every threshold

#### Scenario: Nothing predicted positive
- **WHEN** no document of a module has a score at or above 0.95
- **THEN** the 0.95 point has `precision 1.0`, `recall 0.0` and `f1 0.0`

### Requirement: Recommended threshold
For each evaluated module the report SHALL give `f1_plateau`, the lowest and highest grid threshold whose `f1` is within 0.02 of the module curve's best, and `recommended_threshold`, the plateau's higher end, plus the points at both and at ADR 0305's default. When the best `f1` is 0, both SHALL be null.

#### Scenario: Best F1 wins
- **WHEN** a module's curve has `f1` 0.70 at 0.25 and 0.67 at 0.3
- **THEN** `recommended_threshold` is 0.25

#### Scenario: Tie goes to the higher threshold
- **WHEN** a module's curve has its best `f1` 0.889 at every threshold from 0.4 to 0.65
- **THEN** `recommended_threshold` is 0.65

#### Scenario: Near-tie goes to the higher threshold
- **WHEN** a module's curve has `f1` 0.80 at 0.3, 0.79 at 0.35 and 0.785 at 0.4
- **THEN** `f1_plateau` is [0.3, 0.4] and `recommended_threshold` is 0.4

#### Scenario: Nothing found
- **WHEN** every point of a module has `f1` 0
- **THEN** `recommended_threshold` and `f1_plateau` are null

#### Scenario: Thresholds move FP and FN
- **WHEN** the committed gold set is evaluated rules-only
- **THEN** for each evaluated module, the point at its recommended threshold differs in `fp` or `fn` from the point 0.2 below it or 0.2 above it

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

### Requirement: Threshold floor
Each evaluated module's `default_threshold` SHALL be its `recommended_threshold` raised to the module's floor. The M3 floor SHALL be the S3.4 gate cap of ADR 0308 (`modules/m3.py` `GATE_CAP`, 0.4), so a capped M3 finding never raises `finding.high_risk` at the default; M1 and M2 SHALL have no floor. The report SHALL give the point at `default_threshold`.

#### Scenario: M3 recommendation below the gate cap
- **WHEN** M3's recommended threshold is 0.25 and the gate cap is 0.4
- **THEN** M3's `default_threshold` is 0.4 and `at_default_threshold` is the 0.4 point

#### Scenario: Recommendation above the floor
- **WHEN** M3's recommended threshold is 0.55
- **THEN** M3's `default_threshold` is 0.55

#### Scenario: No floor for M2
- **WHEN** M2's recommended threshold is 0.25
- **THEN** M2's `default_threshold` is 0.25

### Requirement: Per-rule and per-signal metrics
For each labeled rule or signal the report SHALL give `tp`, `fp`, `fn`, `tn`, `precision`, `recall` and `f1` in two readings, `strict` (a predicted `uncertain` counts as not flagged) and `review` (it counts as flagged), plus counts of `uncertain` and of `applicability_errors`. Gold `fail` SHALL be a positive and `pass` a negative; gold `not_applicable` SHALL stay out of the counts.

#### Scenario: Uncertain in both readings
- **WHEN** `S1.5` is labeled `fail` on a document and the rules-only result is `uncertain`
- **THEN** it is an `fn` in `strict`, a `tp` in `review`, and `uncertain` is 1

#### Scenario: Applicability error
- **WHEN** `R4` is labeled `not_applicable` (no blocks) and the pipeline returns `R4: fail`
- **THEN** `applicability_errors` of `R4` is 1 and its confusion counts do not change

#### Scenario: Rule missing from the result
- **WHEN** `R3` is labeled on a document but the module produced no finding for it
- **THEN** that label counts as not flagged in both readings

### Requirement: Stored calibration run
With `--db`, the evaluation SHALL write in one transaction 19 rows per evaluated module to `calibration_points`, with one `computed_at` for the run, one `run_id` per module, and `labeled_samples` = gold documents labeled for that module. They SHALL be what `GET /api/calibration` returns when the module has no analyst labels. A run in which a gold document failed analysis SHALL NOT be stored. Without `--db` it SHALL NOT connect to a database.

#### Scenario: API serves the stored run
- **WHEN** the evaluation runs with `--db` and M2 has no labeled findings
- **THEN** `GET /api/calibration?module=M2` returns the run's 19 points in ascending threshold, with the same counts, ratios and `f1`, and its `labeled_samples`

#### Scenario: Crashed gold document
- **WHEN** the pipeline raises on one gold document during a run with `--db`
- **THEN** nothing is stored, the report lists that gold id under `analysis_errors`, and the exit code is 1

#### Scenario: Database down
- **WHEN** the database is unreachable or the insert fails
- **THEN** the run exits 3, no row of this run is in `calibration_points`, the report is still printed, and the log names neither the database URL, its host nor its password (also when the password holds an unescaped `@`)

#### Scenario: Bad database URL
- **WHEN** `--db` is given and `DATABASE_URL` is missing or cannot be parsed
- **THEN** the run exits 2 before analyzing, and the message does not quote the URL

#### Scenario: Report only
- **WHEN** the evaluation runs without `--db`
- **THEN** it opens no database connection and exits 0 on a valid gold set

### Requirement: Idempotent stored run
For a rules-only run, a module's `run_id` SHALL be a UUID derived from the gold-set content hash, the pipeline version, the module and its points. Per module the evaluation SHALL write nothing when the module's latest stored run has that `run_id`, SHALL move `computed_at` of existing rows with that `run_id` to now when another run is newer, and SHALL insert otherwise. An `--llm` run SHALL get a random UUID v4 and always be inserted.

#### Scenario: Restart with the same gold set
- **WHEN** the evaluation runs with `--db` twice on the same code and gold set
- **THEN** the second run writes no row, the report says `unchanged` per module, and the exit code is 0

#### Scenario: Gold set changed
- **WHEN** one gold label changes between two runs with `--db`
- **THEN** the second run inserts a new run with a different `run_id`, which the API returns

#### Scenario: Another module changed
- **WHEN** only M3's points change between two runs with `--db`, or the second run uses `--module M2`
- **THEN** M2 is reported `unchanged` and gets no new rows

#### Scenario: Rolled-back code
- **WHEN** run A is stored, then run B, then the code that produced A runs again
- **THEN** no row is inserted, A's rows get the new `computed_at`, and the API returns A's points

### Requirement: Module that never ran
A module that has at least one gold label but no finding on any gold document SHALL be reported with status `not_run`, SHALL get no `calibration_points` rows, and SHALL make the run exit 1 after the other modules are reported and stored. A module with no gold labels SHALL NOT be evaluated and SHALL NOT affect the exit code.

#### Scenario: Labels for a missing module
- **WHEN** the gold set labels M1 documents but this build produces no M1 finding for any of them
- **THEN** the report lists M1 as `not_run`, M2 and M3 are stored, M1 has no new rows and the exit code is 1

#### Scenario: Previous run kept
- **WHEN** M1 is `not_run` in a run with `--db` and an older M1 run exists
- **THEN** `GET /api/calibration?module=M1` still returns the older run

### Requirement: Deterministic rules-only run
By default the evaluation SHALL run the pipeline rules-only with the gold registry `analytics/eval/registry.csv`, and two runs on the same code and gold set SHALL print the same report except `computed_at`. `--llm` SHALL use the LLM judge configured by `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`, and SHALL exit 2 without them or in a build without a judge. A document whose judge call fails SHALL be analyzed rules-only and counted in the report.

#### Scenario: Two rules-only runs
- **WHEN** the evaluation runs twice without `--llm`
- **THEN** both reports are byte-identical after removing `computed_at`

#### Scenario: LLM requested but not configured
- **WHEN** `--llm` is given and `LLM_BASE_URL` is empty
- **THEN** the run exits 2 before analyzing

#### Scenario: LLM endpoint down
- **WHEN** `--llm` is given and every judge call fails
- **THEN** the run completes rules-only and the report says all documents ran without the model

### Requirement: Command line
The evaluation SHALL run as `python -m investwatch_analytics.evaluation` and as `python analytics/eval/run.py`, with `--gold`, `--registry`, `--db`, `--llm`, `--module` and `--write-thresholds`, the JSON report on stdout and JSON logs on stderr, and exit codes 0 (ok), 1 (a module `not_run` or a crashed gold document), 2 (invalid input or configuration) and 3 (database write failed).

#### Scenario: Restricted module list
- **WHEN** the run uses `--module M2`
- **THEN** only M2 is evaluated and stored, and labels of other modules are still validated

### Requirement: One-shot compose service
`analytics/compose.yaml` SHALL define a one-shot service `analytics-eval` in the default stack (no profile) that runs the evaluation rules-only with `--db` after `api-migrate` completes, on the data network only, without restarting.

#### Scenario: Fresh stack has a curve
- **WHEN** the stack starts with `docker compose up` on an empty database
- **THEN** `analytics-eval` exits 0 and `GET /api/calibration?module=M2` returns 19 points with `labeled_samples` greater than 0

#### Scenario: Restart of the stack
- **WHEN** the stack is stopped and started again with `docker compose up`
- **THEN** `analytics-eval` exits 0 and `calibration_points` has no new rows
