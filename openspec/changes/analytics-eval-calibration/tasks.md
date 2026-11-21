# Tasks

Rule for every group: `contracts/mocks/`, `contracts/mock-server/` and the `web/` mock mode stay untouched; the gold set never reads or copies them. `api/` code and migrations stay untouched (open question 1 in design.md is a follow-up).

Prerequisite: `analytics-worker` (PR #26), `analytics-m1-m3` and `analytics-llm-p0` are merged and this branch is rebased on `main` (proposal, Dependencies). Groups 1-5 only need the worker and M2; groups 6-7 need the stage-2 rule and signal ids. Total estimate ≈ 11.5 h.

## 1. Gold-set loader and validation (≈ 1.25 h)

- [ ] 1.1 Failing tests (`tests/test_eval_gold.py`) for every scenario of "Gold-set validation before analysis" and the two shape scenarios of "Gold-set file" (two modules on one document, omitted rule): empty file and blank-only file, invalid JSON on line 7, `document` without `url`, module `M4`, label `maybe`, rule label `failed`, duplicate id naming both lines, `R19` and `S1.9` unknown, `R3` under `M1`, `R5` with `implemented: false` accepted; error messages name line, id and field and never contain the document text (assert a marker string from the text is absent from logs)
- [ ] 1.2 `evaluation/gold.py`: `GoldItem`/`ModuleExpectation` (pydantic, strict on `expect`, `ScrapedDocument` for `document`), `load_gold(path, catalogues)` reading all lines first and raising `GoldError` with every problem found; per-module catalogue lookup (M2 `m2_rules.yaml`, M1/M3 signal catalogues); ADR 0312 (design decision 12) with its row in `.docs/decisions/README.md`; tests green
- [ ] 1.3 Mutation check on the validation branches; `mutations: N tried, N caught`

## 2. Counting and metrics (≈ 1 h)

- [ ] 2.1 Failing tests (`tests/test_eval_metrics.py`), one per metric and convention: `confusion(pairs, t)` with a score equal to the threshold (tp at 0.5, fn at 0.55); `precision` (normal, nothing predicted → 1.0); `recall` (normal, no positives → 0.0); `f1` (normal, both 0 → 0.0); rounding to 3 decimals; the grid has 19 values 0.05..0.95 with no float drift; API parity on the rest-api scenario (0.9/0.4 positive, 0.6/0.2 negative → point at 0.5 is 1/1/1/1, 0.5/0.5/0.5); per-rule `strict` vs `review` on `uncertain`; `applicability_errors` both ways; missing rule result counts as not flagged
- [ ] 2.2 `evaluation/metrics.py`: `GRID`, `confusion`, `ratios`, `curve`, `rule_metrics`; a docstring pointing at the rest-api requirement "Calibration curve" as the source of the conventions; tests green
- [ ] 2.3 Mutation check on the counting code (`>=` vs `>`, the two zero-division defaults, the rounding, tp/fp swap, uncertain mapping per reading, the not_applicable exclusion); `mutations: N tried, N caught`

## 3. Runner and report (≈ 1.5 h)

- [ ] 3.1 Failing tests (`tests/test_eval_runner.py`) on small inline gold sets with the eval registry: a module finding's score is used; no finding of a labeled module = score 0 (M1 positive routed only to M2 is fn at every threshold); "Module that never ran" (M1 labels, no M1 finding → `not_run`, others reported); a module without labels is not in the report; `--module M2` filter; `not_implemented` rules listed with label counts; two runs give byte-identical reports after removing `run_id`/`computed_at`; with a `FakeJudge` that always raises, the report counts every document as run without the model
- [ ] 3.2 `evaluation/runner.py`: `evaluate(gold, registry, catalogues, judge=None, modules=None, now, run_id)` calling `pipeline.analyze` with injected `now`/`new_id`; report dict (per module: status, `labeled_samples`, `points`, per-rule metrics; run: `run_id`, `computed_at`, `pipeline_version`, `llm`, `documents_without_llm`), JSON with sorted keys; `analytics/eval/registry.csv` (fictional firms, seed.csv columns); tests green
- [ ] 3.3 Mutation check (score default 0.0, not_run detection, module filter, sorted output); `mutations: N tried, N caught`

## 4. Calibration store (≈ 1.25 h)

- [ ] 4.1 Failing tests (`tests/test_eval_store.py`, Postgres backend with `TEST_DATABASE_URL`, skipped without it, plus an in-memory fake for the transaction logic): one run writes 19 rows per evaluated module with one `run_id` and one `computed_at`; columns and values match the report points including `f1` and `labeled_samples`; the API's `latest_calibration_run` query shape (re-stated in the test as SQL: newest `computed_at`, then greatest `run_id`, ascending threshold) returns exactly the report points; an insert failure on the last row leaves zero rows of the run; a `not_run` module gets no rows and an older run of it stays the latest; unreachable server → `StoreUnavailable`, bad URL → `StoreMisconfigured`, neither message contains the URL or password
- [ ] 4.2 Add `calibration_points` (from `api/migrations/versions/0001_initial.py`, verbatim constraints) to the test-only `tests/sql/schema.sql`; `evaluation/store.py` `write_run(dsn, report)` with psycopg 3, one transaction, `executemany`, reusing the worker's error types; tests green
- [ ] 4.3 Mutation check (transaction scope, `labeled_samples` source, skipping `not_run`, f1 written); `mutations: N tried, N caught`

## 5. Command line and exit codes (≈ 1 h)

- [ ] 5.1 Failing tests (`tests/test_eval_cli.py`): exit 0 on a valid gold set without `--db` and no connection attempted (store patched to fail if called); exit 2 on an empty gold set with nothing on stdout; exit 2 on `--db` without `DATABASE_URL`; exit 2 on `--llm` with empty `LLM_BASE_URL`; exit 1 when a module is `not_run` (rows of the other modules written); exit 3 when the store raises `StoreUnavailable` with the report still on stdout; stdout is only the JSON report and logs go to stderr as JSON; `python analytics/eval/run.py --help` and `python -m investwatch_analytics.evaluation --help` both work
- [ ] 5.2 `evaluation/__main__.py` (argparse: `--gold`, `--registry`, `--db`, `--llm`, `--module`; defaults relative to the package so they resolve in the image), `analytics/eval/run.py` wrapper; LLM judge built from `LLM_*` like the worker; tests green
- [ ] 5.3 Mutation check (each exit-code branch, the no-db path); `mutations: N tried, N caught`

## 6. Gold set: M2 (≈ 2 h)

- [ ] 6.1 Failing tests (`tests/test_eval_goldset.py`, on the committed file): the M2 part of "Coverage per module" (≥ 15 documents, ≥ 5 positive, ≥ 5 negative, every implemented M2 rule has a `fail` and a `pass`) and "Every ZASÓB rule has a pair" (R1-R18 with R12a/R12b); "Fictional firms only" for M2 documents; the full file loads with no `GoldError`
- [ ] 6.2 Write the labeling guide (README in `analytics/eval/`) first: labeling guide (labels come from the ZASÓB text and annex 3, never from the current rule output; what `fail` means for M2 vs M1/M3; `basis` and `hard_case`; fictional names and the handles list; how to add a line; no real personal data, phone numbers only `+48 000 …`). Then the M2 lines of `gold.jsonl`: one violating and one compliant example per ZASÓB rule written from its operational description (web pages with `blocks` for R4-R8 and R13, social posts with no blocks where visual rules are `not_applicable`), plus hard cases: risk warning at the R3 window edge, risk only in the footer, negated "nie jest gwarancją", KNF named as a fact vs as approval (R17), "bezpieczna" next to supervision (R18), past performance with and without the R14 warning, a firm's own social post routed to M2; spread the labels so rules-only scores fall on both sides of 0.5 and 0.7; tests green; then run the evaluation and record in `follow-ups.md` each rule whose `strict` recall or precision is below 0.5, with a disposition (rule follow-up, not a label change)
- [ ] 6.3 Mutation check on the gold set itself: flip 3 labels and remove one rule's `pass` example, the coverage tests must catch each; `mutations: N tried, N caught`

## 7. Gold set: M1 and M3 (≈ 2 h)

- [ ] 7.1 Failing tests: the M1 and M3 parts of "Coverage per module" (every implemented signal of S1.1-S1.7 and S3.1-S3.8 has a `fail` and a `pass`; S3.7 listed `not_implemented`), "Fictional firms only" for all documents, and "Thresholds move FP and FN" for M1 (0.6), M2 (0.5) and M3 (0.7)
- [ ] 7.2 M1 lines (Opis Moduł 1 scope): finfluencer posts with referral links and promo codes, labeled and unlabeled partnerships, a Polish-language ad of a foreign firm (positive) and an English one without Polish markers (negative, S1.7), an educational review that names a firm without affiliate signals (negative), a firm's own account marked `third_party` (negative for M1, positive for M2). M3 lines (annex 3): unregistered "wealth management" and "family office" offers with buy/sell/hold calls on Art. 2 instruments (positive), personalization without a recommendation (capped, negative at 0.7), plain crypto calls only (S3.8, negative), a crypto CFD call (positive), education with "to nie jest rekomendacja" (negative), a registered firm's own advisory page (negative for M3), a finfluencer with own buy calls labeled M1 and M3; tests green; record low-scoring signals in `follow-ups.md` as in 6.2
- [ ] 7.3 Mutation check as in 6.3 for M1/M3, plus moving one hard case across the threshold so "Thresholds move FP and FN" fails; `mutations: N tried, N caught`

## 8. Image and one-shot compose service (≈ 1 h)

- [ ] 8.1 Failing test (`tests/test_eval_compose.py`, YAML-level): `analytics/compose.yaml` has `analytics-eval` with the analytics image, command `python -m investwatch_analytics.evaluation --db`, `restart: "no"`, `depends_on` `api-migrate` (`service_completed_successfully`) and `postgres` (`service_healthy`), networks `[data]` only, `read_only`, `cap_drop: [ALL]`, no `LLM_*` env; the Dockerfile copies `eval`; `.dockerignore` does not exclude it
- [ ] 8.2 Dockerfile `COPY eval eval`, the compose service; smoke run on the full stack (`docker compose up`): `analytics-eval` exits 0 and `GET /api/calibration?module=M2` returns 19 points with `labeled_samples > 0`, then `PUT /api/settings/thresholds` with M2 0.7 and the panel's FP/FN change (record the numbers in the PR body); if the stack cannot be run, say so in the PR body and in the task line
- [ ] 8.3 Mutation check (remove `depends_on`, add `egress`, drop `--db`: the YAML test catches each); `mutations: N tried, N caught`

## 9. Closing

- [ ] 9.1 Apply the iw-docs-update skill (`analytics/README.md` evaluation section with the latest rules-only numbers per module, `.docs/analytics-plan.md` §8 gold line shape and how to run it, `.docs/integration-plan.md` §5 note that `gold_labels` is a file not a table, ADR 0312 row; `.docs/STATUS.md` and `.docs/status/*` only if the coordinating session no longer owns them; `docs-check` clean) and add the iw-ai-log row
- [ ] 9.2 Run the iw-pr-review skill and fix real findings
