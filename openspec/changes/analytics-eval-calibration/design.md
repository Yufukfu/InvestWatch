# Design

## Context

- `GET /api/calibration` (`api/src/investwatch_api/routes/calibration.py`, rest-api spec "Calibration curve") builds 19 points on the grid 0.05..0.95 from analyst labels (`confirmed` = positive, `false_positive` = negative). With no labels for a module it returns the latest stored run from `calibration_points` (`db/sql.py` `latest_calibration_run`: newest `computed_at`, ties broken by the greatest `run_id`, points by ascending threshold) and copies `threshold, tp, fp, fn, tn, precision, recall` plus `f1` when not null, and `labeled_samples` from the first row.
- Counting conventions there: positive prediction is `score >= t`; `precision = 1.0` when nothing is predicted positive; `recall = 0.0` without positives; `f1 = 0.0` when precision + recall is 0; each rounded to 3 decimals.
- `calibration_points` (migration 0001): `run_id uuid`, `module` in M1/M2/M3, `threshold` in [0, 1], non-negative counts, `precision`/`recall` not null, `f1` nullable, `labeled_samples` not null, `computed_at timestamptz`, unique `(run_id, module, threshold)`. `iw_app` gets INSERT by default privileges.
- Scores: M2 `Σ(w·fail)/Σ(w·applicable)` with uncertain = 0.5 (`modules/m2.py`); M1/M3 `σ(bias + Σ w·x)` and the M3 S3.4 gate at 0.4 (`analytics-m1-m3`). The pipeline is pure (`pipeline.analyze`, injectable `now`/`new_id`), the judge is optional (`analytics-llm-p0`).
- `doc/` has no sample materials: `Opis Wyzwania` (criteria, §6 jury), ZASÓB (R1-R18 operational descriptions and legal bases), annexes 1/2 (KNF list URLs, firm definitions), annex 3 (Art. 76 advice, Art. 2 instruments). The "pendrive" samples (Opis §7) are not in the repository.
- The worker (PR #26) brings `psycopg` 3, `DATABASE_URL`, `StoreUnavailable`/`StoreMisconfigured` and a test-only `tests/sql/schema.sql` mirror for Postgres tests (`TEST_DATABASE_URL`, skipped without it).

## Goals / Non-Goals

**Goals:** a labeled, reviewable gold set for M1, M2 and M3; measured precision/recall/F1 per module and per rule or signal; a stored run the calibration panel shows on a fresh stack; one deterministic command; failure paths that never write a partial or misleading run.

**Non-Goals:** a `gold_labels` table; a schema or contract change; tuning weights; the web panel; new rules.

## Decisions

### 1. Gold line shape: one document, labels per module

```json
{"id": "m2-r3-window-edge", "origin": "synthetic", "basis": "ZASÓB R3", "hard_case": "warning 3 sentences after the claim",
 "document": { ...ScrapedDocument v1... },
 "expect": {"M2": {"label": "positive", "rules": {"R1": "pass", "R3": "fail", "R14": "not_applicable"}}}}
```

- `id` unique slug; `origin` is `synthetic` or `uknf-sample` (reserved for pendrive samples, see open questions); `basis` names the criterion the example was written from (ZASÓB rule, annex 3, Opis module scope); `hard_case` is free text, present only on hard cases.
- `expect` holds only the modules the document is labeled for. A document can be labeled for M1 and M3 at once (finfluencer with own buy calls), or negative for a module it must not trigger (education with a firm mention, negative for M1).
- Rule labels are partial: an omitted rule is not scored on that document. `fail` = violation for M2, signal present for M1/M3 (the catalogues' own meaning).
- Plan §8 had one line per (document, module). Grouping by document avoids repeating the document and lets one example check M1-versus-M3 routing. Plan §8 is updated in the closing docs task.
- Alternatives: a CSV of labels plus a folder of documents (two files to keep in sync, harder to review); reusing `contracts/mocks/documents.json` (forbidden: mocks stay untouched, and they have no negative labels).

### 2. Fictional registry for the gold set

The evaluation loads `analytics/eval/registry.csv` (same columns as `registry/seed.csv`, fictional firms only). `analytics-knf-registry` will replace or extend the runtime registry with real KNF data; a gold set bound to it would change results whenever KNF changes a list, and synthetic documents would have to name real firms. `--registry` can override it for experiments, but the compose service never does.

### 3. Module score and document label

For each gold document and each module in its `expect`, the predicted score is that module's finding `score`, or 0.0 when the pipeline produced no finding for the module (dropped, routed elsewhere or gated). So a routing error is a false negative at every threshold, and a correctly unrouted negative is a true negative. Counting is `metrics.curve(pairs)` with exactly the API's conventions and grid (decision 6).

### 4. Per-rule and per-signal metrics, two readings

Gold `fail` = positive, gold `pass` = negative, gold `not_applicable` is not counted in the confusion matrix but a predicted applicable result on it (or the reverse) is counted as an `applicability_error`. Predicted `uncertain` is the hard part: rules-only, S1.5 is always `uncertain` and S3.3/S3.4 report candidates as `uncertain`.

- `strict`: `uncertain` = not flagged. Measures what the rules decide on their own.
- `review`: `uncertain` = flagged. Measures what an analyst sees (the dashboard marks it "do weryfikacji", and M2 scores it as half a fail).

Both are reported with the `uncertain` count. Neither goes to the database (the table has no rule column); they go to the JSON report. Rules with `implemented: false` are listed as `not_implemented` with their label counts, so `analytics-m2-p1-rules` lands into an already-labeled set.

### 5. Validation before running

The loader reads every line before analyzing anything and fails with exit 2, naming the line number and the field (never the document text), on: no labeled line at all (empty file, only blank lines), invalid JSON, a `document` that fails `ScrapedDocument`, a module outside M1/M2/M3, a label outside the allowed values, a duplicate `id`, a rule or signal id that is in no loaded catalogue (typos like `R3 ` or `S1.9`), or a rule id from another module's catalogue (`R3` under `M1`). The known ids are the union of the loaded catalogues and a static list `evaluation/known_ids.py` copied from the stage-2 catalogues (M2 R1-R11, R12a, R12b, R13-R18; M1 S1.1-S1.7; M3 S3.1-S3.8), so the gold set can label M1/M3 and the new M2 rules before those changes are merged into this build. A known id that the loaded catalogue marks `implemented: false` is reported `not_implemented`; a known id missing from the loaded catalogue is `not_in_build`. Both are valid labels. `origin: uknf-sample` items need no code change: the loader treats them like synthetic ones, and the report counts items per origin.

### 6. Parity with the API instead of shared code

`api/` and `analytics/` are separate services with separate images, so the evaluation cannot import `investwatch_api.routes.calibration.curve`. `evaluation/metrics.py` reimplements it (about 15 lines) and a parity test pins both the rest-api spec scenario (scores 0.9/0.4 positive, 0.6/0.2 negative: at 0.5 `tp 1, fp 1, fn 1, tn 1, precision 0.5, recall 0.5, f1 0.5`) and the two edge conventions. The grid is the same literal `round(0.05 * i, 2) for i in 1..19`. A future change to the API's convention has to change both; the parity tests point at the spec, so a drift shows in review.

### 7. Store: one run, one transaction, idempotent

`computed_at` = one UTC timestamp for the whole run (injectable for tests). For a rules-only run, `run_id` = `uuid5(NAMESPACE, sha256(gold file bytes) + pipeline_version + sha256(canonical JSON of the module points))`, so the same gold set, pipeline version and results always give the same id (a deliberate exception to the UUID v4 convention, recorded in ADR 0312). Including the points means a rule change without a version bump still produces a new run. Per module, in one transaction: if the latest stored run of the module (the API's ordering) already has this `run_id`, nothing is written (`stored: unchanged`); if rows with this `run_id` exist but another run is newer (code rolled back), their `computed_at` is moved to now so the API serves them again (`stored: refreshed`); otherwise the 19 rows are inserted (`stored: inserted`). An `--llm` run is not reproducible, so it always gets a uuid4 and is inserted. All rows of all evaluated modules are inserted with one `executemany` in one transaction; any error rolls back, so the API never serves half a run. `f1` is always written (the API copies it when not null). `labeled_samples` = number of gold documents labeled for that module. A module reported `not_run` (decision 8) gets no rows, so the API keeps serving the previous run for it. Connection errors map to `StoreUnavailable` (exit 3), an unparsable `DATABASE_URL` to `StoreMisconfigured` (exit 2); the message never quotes the URL.

### 8. "Module never ran"

A module that has at least one gold label but produced no finding on any gold document is `not_run`: the module is missing in this build (for example M1 before `analytics-m1-m3`), or routing is broken. Storing an all-zero-recall curve for it would look like a real measurement in the panel, so it gets no rows and the run exits 1 with the module named. A module with no labels at all is simply not evaluated (exit 0).

### 9. Command line and exit codes

`python -m investwatch_analytics.evaluation [--gold PATH] [--registry PATH] [--db] [--llm] [--module M2 ...]` with the thin wrapper `analytics/eval/run.py` (plan §8 names it). Defaults: `analytics/eval/gold.jsonl`, `analytics/eval/registry.csv`, no database, rules-only. stdout: the JSON report (sorted keys, so two rules-only runs are byte-identical except `run_id` and `computed_at`); stderr: JSON logs, like `cli.py`. Exit 0 ok, 1 a module `not_run`, 2 invalid input or configuration (nothing analyzed, nothing written), 3 database write failed (report printed, nothing written).

### 10. LLM optional

`--llm` builds the judge as the worker does from `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`; without those it is an error (exit 2), not a silent rules-only run. A build whose `analyze` has no `judge` parameter (before `analytics-llm-p0`) also exits 2 with "no LLM judge in this build". When the endpoint fails, `analyze` degrades per document as it already does; the report counts documents with `model.llm = null`. The compose service stays rules-only (deterministic, no egress).

### 11. One-shot compose service in the default stack

Damian's decision: Opis §3 asks for the whole stack with one command, and the jury tests the calibration panel on the default stack. `analytics-eval` in `analytics/compose.yaml`, without a profile: same image, `command: ["python", "-m", "investwatch_analytics.evaluation", "--db"]`, `restart: "no"`, `depends_on: api-migrate (completed_successfully), postgres (healthy)`, network `data` only, same hardening as the worker. The Dockerfile copies `eval/`. Thanks to decision 7 a restart writes nothing new. A profile would leave the panel empty unless someone remembers a command during the demo. Alternative considered: a seed migration in `api/` (wrong owner of the data, and the numbers would not follow rule changes).

### 12. Analyst labels plus the gold run in the API

Damian's decision: the panel must never collapse to one or two labels. `GET /api/calibration` computes the label curve as today and, when the module also has a stored run, adds the run's `tp/fp/fn/tn` to the label counts per threshold (both use the same grid; a stored point at a threshold outside the grid is ignored), recomputes `precision`, `recall` and `f1` with the same conventions, and returns `labeled_samples` = labels + run samples. With only one source it returns that source unchanged. No query parameter (the contract is frozen) and no response change. A source switch (`source=gold|labels|both`) is a follow-up if Kacper's panel wants it.

### 13. ADR 0312

Decisions 2, 4, 6, 7 (deterministic run id), 11 and 12 are recorded as ADR 0312 "Gold-set evaluation feeds the calibration panel" (fictional eval registry, strict/review readings, API-parity counting, one-shot service). Written in task group 1 as `Status: accepted`, effective when the PR merges.

## Risks / Trade-offs

- [The gold set is ours, not UKNF's, so it measures how well we encoded our own reading of the criteria] → every line names its `basis`; labels are written from the ZASÓB text and annex 3, not from what the rules currently output (labels first, run second, task groups 6-7); the README says so plainly.
- [Small set (about 60 documents): one example moves precision by several points] → the report shows counts next to ratios; the demo talks about FP/FN counts, which is what Opis §2 asks.
- [Combining labels with gold mixes two populations: real scraped findings and our synthetic set] → the panel shows `labeled_samples`; the README says the curve is gold plus analyst labels.
- [Weights tuned on the same gold set overfit it] → this change does not tune; a later tuning change should hold out the hard cases.
- [Synthetic `.pl` domains or handles might exist for real] → `example`-style names (`*.example.pl` where a Polish domain is the point), checked against `registry/seed.csv`; no person names, phone numbers only from `+48 000 …`.
- [Stage-2 rules change after this lands] → the gold-set test asserts the run finishes and that FP/FN move between the default threshold and +0.2, not exact numbers, so rule changes do not break the build; the report diff is the review signal.

## Migration Plan

No schema change. Deploy = merge; the next `docker compose up` writes the first run. Rollback = remove the service; old runs stay in the table and are harmless (or `DELETE FROM calibration_points WHERE run_id = …`).

## Open Questions

Answered by Damian on 2026-11-21: (1) combine labels and gold, decision 12; (2) no UKNF samples in `doc/` yet, synthetic set now, `uknf-sample` items later without code changes; (3) report both readings, `strict` is the headline in the README and slides; (4) default stack, no profile, idempotent, decisions 7 and 11; (5) about 20 per module, a third hard cases, M2 somewhat more.
