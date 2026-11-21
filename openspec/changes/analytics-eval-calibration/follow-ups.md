# Follow-ups

Review findings and out-of-scope items, one row each (iw-commit-cycle step 8).

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | review groups 1-2 | `str.splitlines()` split gold lines on U+2028/U+0085 inside text | fix-here (`raw.split("\n")`, bytes read, test) |
| 2 | review groups 1-2 | duplicate JSON keys in `expect` / `rules` silently kept the last value | fix-here (`object_pairs_hook`, test) |
| 3 | review groups 1-2 | grid test recomputed the grid with the code's own expression | fix-here (literal tuple) |
| 4 | review groups 1-2, declined to judge | gold `fail` predicted `not_applicable` counts as `fn` and as an applicability error | wont-fix: intended (the rule missed a labeled violation, and the applicability mismatch is reported separately); documented in `metrics.rule_metrics` |
| 5 | review groups 1-2, declined to judge | gold `not_applicable` predicted `uncertain` counts toward `uncertain` and `applicability_errors` | wont-fix: both counts describe the prediction; confusion counts stay unchanged as the spec asks |
| 6 | review groups 1-2, declined to judge | per-rule metrics reuse the API's zero-division conventions | docs: stated in the eval README and `metrics.py` docstring |
| 8 | review groups 3-5 | an unescaped `@` in the password put part of it into the libpq host error, which reached the log | fix-here (exception class only, test with `se@cret`) |
| 9 | review groups 3-5 | one run id for all modules re-stored an unchanged module when another changed or with `--module` | fix-here (run id per module; spec and design updated) |
| 10 | review groups 3-5 | a run with a crashed gold document was stored with zero scores | fix-here (not stored, exit 1; spec scenario "Crashed gold document") |
| 11 | review groups 3-5 | an exception from the judge factory escaped as a traceback | fix-here (exit 2, class only in the log) |
| 12 | review groups 3-5 | `iw_app` needs UPDATE on `calibration_points` for the refreshed path | wont-fix: default privileges in `infra/postgres/init/01-app-role.sh` grant SELECT, INSERT, UPDATE, DELETE |
| 7 | group 5 | `--llm` looks for `investwatch_analytics.llm.judge_from_env` and `analyze(judge=...)`; `analytics-llm-p0` has neither yet, so `--llm` exits 2 on this build | new-item: when llm-p0 ships its judge, expose `judge_from_env()` (or adapt `_judge_factory`) and add a FakeJudge CLI test |
