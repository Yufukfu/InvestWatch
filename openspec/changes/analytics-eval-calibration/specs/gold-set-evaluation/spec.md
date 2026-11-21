## ADDED Requirements

### Requirement: Gold-set file
The gold set SHALL be `analytics/eval/gold.jsonl`, one JSON object per line with a unique `id`, an `origin` (`synthetic` or `uknf-sample`), a `basis` naming the criterion it was written from, an optional `hard_case` text, a `document` that is a valid `ScrapedDocument` v1 (`.docs/integration-plan.md` §3), and `expect`: a mapping from module (`M1`, `M2`, `M3`) to `{label, rules}`, where `label` is `positive` or `negative` and `rules` maps a rule or signal id of that module's catalogue to `fail`, `pass` or `not_applicable`. Synthetic documents SHALL name only fictional firms, handles and domains and SHALL contain no real person's personal data. The gold set SHALL NOT read or modify `contracts/mocks/`.

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

#### Scenario: Fictional firms only
- **WHEN** the committed gold set and `analytics/eval/registry.csv` are loaded
- **THEN** no firm in `analytics/eval/registry.csv` shares a name, alias or domain with the runtime registry under `analytics/registry/` (which `analytics-knf-registry` fills with real KNF firms), and every `document.author` handle is in the fictional-handles list of the labeling guide (README in `analytics/eval/`)

### Requirement: Gold-set validation before analysis
The evaluation SHALL read and validate the whole gold set before analyzing any document. It SHALL stop with exit code 2, without analyzing or writing anything, when the file is missing, has no labeled line, has a line that is not valid JSON, has a `document` that fails `ScrapedDocument` validation, names a module outside M1/M2/M3, uses a label outside the allowed values, repeats an `id`, or uses a rule or signal id that is not in the loaded catalogue of that module. Each error SHALL name the line number, the gold `id` when known and the field, and SHALL NOT quote document text. A label for a rule that is in the catalogue with `implemented: false` SHALL be valid.

#### Scenario: Empty gold set
- **WHEN** the gold file is empty or holds only blank lines
- **THEN** the run exits 2 with "no labeled document", the report is not printed and no `calibration_points` row is written

#### Scenario: Unknown rule id
- **WHEN** a line labels `R19` (or `S1.9`) under its module
- **THEN** the run exits 2 naming that line, that id and the module, and no document is analyzed

#### Scenario: Rule id of another module
- **WHEN** a line labels `R3` under `M1`
- **THEN** the run exits 2 naming the line, `R3` and `M1`

#### Scenario: Unknown module
- **WHEN** a line has `expect` with key `M4`
- **THEN** the run exits 2 naming the line and `M4`

#### Scenario: Malformed line
- **WHEN** line 7 is not valid JSON, or its `document` has no `url`
- **THEN** the run exits 2 naming line 7 and the failing field, and the log contains no text of the document

#### Scenario: Duplicate id
- **WHEN** two lines share the `id` `m2-r3-window-edge`
- **THEN** the run exits 2 naming both line numbers

#### Scenario: Label for a rule not implemented yet
- **WHEN** a line labels `R5: fail` and `R5` has `implemented: false`
- **THEN** the run continues and the report lists `R5` as `not_implemented` with its label counts

### Requirement: Module curve with the API's counting
For each module with labels, the evaluation SHALL pair each labeled document's label with the score of that module's finding for the document, using 0.0 when the pipeline produced no finding of that module. On the thresholds 0.05, 0.10, ..., 0.95 it SHALL count `tp`, `fp`, `fn`, `tn` with a positive prediction meaning `score >= threshold`, and compute `precision`, `recall` and `f1` with the conventions of the rest-api requirement "Calibration curve" (precision 1.0 when nothing is predicted positive, recall 0.0 without positives, f1 0.0 when both are 0, each rounded to 3 decimals).

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

#### Scenario: Thresholds move FP and FN
- **WHEN** the committed gold set is evaluated rules-only
- **THEN** for each of M1 (0.6), M2 (0.5) and M3 (0.7) the point at the default threshold and the point 0.2 above it differ in `fp` or `fn`

### Requirement: Per-rule and per-signal metrics
For each rule or signal with labels, the report SHALL give `tp`, `fp`, `fn`, `tn`, `precision`, `recall` and `f1` in two readings: `strict`, where a predicted `uncertain` counts as not flagged, and `review`, where it counts as flagged; plus the count of predicted `uncertain` and of `applicability_errors` (gold `not_applicable` with a predicted applicable result, or the reverse). Gold `fail` SHALL be a positive and gold `pass` a negative; gold `not_applicable` SHALL NOT enter the confusion counts. Rules with `implemented: false` SHALL be listed as `not_implemented` without metrics.

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
With `--db`, the evaluation SHALL write one run to `calibration_points`: one `run_id` (UUID v4) and one `computed_at` (UTC) for all rows, 19 rows per evaluated module with `module`, `threshold`, `tp`, `fp`, `fn`, `tn`, `precision`, `recall`, `f1` and `labeled_samples` (the number of gold documents labeled for that module), all in one transaction. The rows SHALL be what `GET /api/calibration` returns for that module when it has no analyst labels. Without `--db` it SHALL NOT connect to a database.

#### Scenario: API serves the stored run
- **WHEN** the evaluation runs with `--db` and M2 has no labeled findings
- **THEN** `GET /api/calibration?module=M2` returns the run's 19 points in ascending threshold, with the same counts, ratios and `f1`, and its `labeled_samples`

#### Scenario: Database down
- **WHEN** the database is unreachable or the insert fails
- **THEN** the run exits 3, no row of this run is in `calibration_points`, the report is still printed, and the log names neither the database URL nor its password

#### Scenario: Bad database URL
- **WHEN** `--db` is given and `DATABASE_URL` is missing or cannot be parsed
- **THEN** the run exits 2 before analyzing, and the message does not quote the URL

#### Scenario: Report only
- **WHEN** the evaluation runs without `--db`
- **THEN** it opens no database connection and exits 0 on a valid gold set

### Requirement: Module that never ran
A module that has at least one gold label but no finding on any gold document SHALL be reported with status `not_run`, SHALL get no `calibration_points` rows, and SHALL make the run exit 1 after the other modules are reported and stored. A module with no gold labels SHALL NOT be evaluated and SHALL NOT affect the exit code.

#### Scenario: Labels for a missing module
- **WHEN** the gold set labels M1 documents but this build produces no M1 finding for any of them
- **THEN** the report lists M1 as `not_run`, M2 and M3 are stored, M1 has no new rows and the exit code is 1

#### Scenario: Previous run kept
- **WHEN** M1 is `not_run` in a run with `--db` and an older M1 run exists
- **THEN** `GET /api/calibration?module=M1` still returns the older run

### Requirement: Deterministic rules-only run
By default the evaluation SHALL run the pipeline rules-only with the gold registry `analytics/eval/registry.csv`, and two runs on the same code and gold set SHALL print the same report except `run_id` and `computed_at`. `--llm` SHALL use the LLM judge configured by `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`; without them it SHALL exit 2. When the judge fails for a document, that document SHALL be analyzed rules-only and the report SHALL count the documents analyzed without the model.

#### Scenario: Two rules-only runs
- **WHEN** the evaluation runs twice without `--llm`
- **THEN** both reports are byte-identical after removing `run_id` and `computed_at`

#### Scenario: LLM requested but not configured
- **WHEN** `--llm` is given and `LLM_BASE_URL` is empty
- **THEN** the run exits 2 before analyzing

#### Scenario: LLM endpoint down
- **WHEN** `--llm` is given and every judge call fails
- **THEN** the run completes rules-only and the report says all documents ran without the model

### Requirement: Command line and compose service
The evaluation SHALL run as `python -m investwatch_analytics.evaluation` and as `python analytics/eval/run.py`, with `--gold`, `--registry`, `--db`, `--llm` and `--module` options, the JSON report on stdout and JSON logs on stderr, and exit codes 0 (ok), 1 (a module `not_run`), 2 (invalid input or configuration) and 3 (database write failed). `analytics/compose.yaml` SHALL define a one-shot service `analytics-eval` that runs it rules-only with `--db` after `api-migrate` completes, on the data network only, without restarting.

#### Scenario: Fresh stack has a curve
- **WHEN** the stack starts with `docker compose up` on an empty database
- **THEN** `analytics-eval` exits 0 and `GET /api/calibration?module=M2` returns 19 points with `labeled_samples` greater than 0

#### Scenario: Restricted module list
- **WHEN** the run uses `--module M2`
- **THEN** only M2 is evaluated and stored, and labels of other modules are still validated
