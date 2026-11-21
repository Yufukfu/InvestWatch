# 0312. Gold-set evaluation feeds the calibration panel

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Damian's answers on the `analytics-eval-calibration` proposal; accepted by: pending approval of the PR

## Context

The jury scores "trafność klasyfikacji ryzyka przez moduły AI oraz wpływ zmian parametrów progowych na wyniki w panelu kalibracji" (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf` §6), and the panel's threshold must change "liczbę wyników False Positive vs False Negative" (§2). `GET /api/calibration` (rest-api spec "Calibration curve") reads analyst labels and the latest run in `calibration_points` (migration `api/migrations/versions/0001_initial.py`), but nothing wrote runs, and a fresh `docker compose up` has no labels. `doc/` holds criteria and definitions but no sample ads, so a gold set has to be written by us. Change: [`openspec/changes/archive/2026-11-21-analytics-eval-calibration`](../../openspec/changes/archive/2026-11-21-analytics-eval-calibration/design.md).

## Options considered

1. **Registry for the gold set:** the runtime registry (`analytics/registry/`, which `analytics-knf-registry` fills with real KNF data) or a fixed fictional `analytics/eval/registry.csv`. The runtime one would change results when a KNF list changes and would force synthetic documents to name real firms.
2. **`uncertain` in per-rule metrics:** count it as not flagged (what the rules decide alone), as flagged (what the analyst sees: "do weryfikacji", half a fail in the M2 score), or report both.
3. **Counting code:** import the API's `curve` (impossible: separate services and images) or reimplement it with parity tests on the rest-api spec scenario.
4. **When the run is written:** an opt-in profile, a seed migration in `api/` (wrong owner, numbers frozen), or a one-shot service in the default stack. The last one writes a run on every `up` unless the run is idempotent.
5. **Labels vs gold in the API:** labels replace the gold run (the merged behavior), or both are summed per threshold.

## Decision

- Fictional `analytics/eval/registry.csv` for every evaluation (option 1, second choice).
- Both readings in the report, `strict` (`uncertain` = not flagged) as the headline in the README and slides (Damian).
- Reimplemented counting in `investwatch_analytics.evaluation.metrics` with the API's grid and conventions, pinned by parity tests on the rest-api spec scenario.
- One-shot service `analytics-eval` in the default stack, no profile (Damian: Opis §3 asks for the stack "jedną komendą" and the jury tests the panel on it). Idempotent: a rules-only run gives each module a `run_id` that is a UUID v5 of the gold file hash, the pipeline version, the module and its computed points, a deliberate exception to the UUID v4 convention. Per module, an identical latest run writes nothing, an identical older run gets a new `computed_at`, anything else inserts 19 rows. `--llm` runs get a UUID v4.
- `GET /api/calibration` sums the label counts and the latest gold run's counts per threshold and recomputes the ratios (Damian: one or two analyst labels must never replace the gold curve). Response shape and parameters unchanged.

## Consequences

- The panel has a curve after a plain `docker compose up`, and restarts add no rows.
- A rule change shows up as a new run even without a pipeline version bump, because the points are part of the run id.
- Two counting implementations must stay equal; the parity tests point at the spec.
- The combined curve mixes our synthetic set with real labeled findings; `labeled_samples` shows how many of each are in it only as a sum, and the README says so.
- Real UKNF samples, if they arrive, are added as `origin: uknf-sample` lines with no code change.
