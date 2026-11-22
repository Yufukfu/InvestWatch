# Tasks

## 1. Measure (~40 min)

- [x] 1.1 Smoke test of `https://api.deepseek.com`: `GET /models` lists `deepseek-flash`; our request shape with `response_format: json_object` returns a plain JSON object in 1.2-1.6 s
- [x] 1.2 Gold-set runs on `main` 0434553b: `python eval/run.py` (rules-only) and `python eval/run.py --llm` (DeepSeek, 28 of 28 calls OK)
- [x] 1.3 End-to-end on the `iw-latest` stack: demo sources, cache (0 calls on the second pass), rules-only fallback on an invalid key (401)

## 2. Defaults (~30 min)

- [x] 2.1 ADR 0318 and the decisions index
- [x] 2.2 `analytics/eval/llm-run-deepseek-flash.json`, `LLM_MEASURED_DEFAULTS` in `evaluation/runner.py`, kept by `--write-thresholds` and refused off the plateau
- [x] 2.3 M1 0.75 in `analytics/eval/thresholds.json`, `events.DEFAULT_THRESHOLDS` and the API `DEFAULTS`
- [x] 2.4 Tests: plateau, gold-set sha, M1's rules-only default, rules-only false positives at the default, CLI refusal, `write_thresholds` override
- [x] 2.5 Mutation check: M1 0.7 in `LLM_MEASURED_DEFAULTS` fails `test_llm_measured_default_is_on_the_recorded_runs_plateau` and `test_cli_write_thresholds`; a wrong `gold_sha256` in the run file fails `test_llm_run_was_measured_on_this_gold_set`

## 3. Docs and closing

- [x] 3.1 `analytics/.env.example`, root `.env.example`, `analytics/README.md` (LLM section, gold-eval table with both runs), `analytics/CLAUDE.md`, `analytics/compose.yaml` comments, `.docs/analytics-plan.md`, `.docs/status/platform.md`
- [x] 3.2 Spec delta `gold-set-evaluation`
- [x] 3.3 Full analytics suite with `CONTRACTS_DIR`, `validate --all --strict` with OpenSpec 2.1.1, `docs-check`
- [x] 3.4 AI log entry (`iw-ai-log`)
- [x] 3.5 Archive the change (last commit)
