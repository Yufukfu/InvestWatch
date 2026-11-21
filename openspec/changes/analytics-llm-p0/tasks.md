# Tasks

Stage 2. Groups 1-4 are rules-only and can start on `main` before `analytics-worker` lands. Groups 5-11 need it merged (worker, `WorkerSettings`, `compose.yaml`). Estimates are for one agent session with tests. If time runs short, cut in the order of `design.md` "Cut plan". No test calls a real LLM: the `stub_llm` fixture (stdlib `ThreadingHTTPServer` on `127.0.0.1:0`) or `FakeJudge` only.

## 1. R14 past-performance disclaimer (~45 min)

- [x] 1.1 Failing tests for the R14 scenarios (eurotrade `fail`, disclaimer next to past returns `pass`, disclaimer far from the claim `pass` (no proximity requirement, ZASÓB), forecast `not_applicable` with `fetched_at` year, footnote-only R14 `pass`; the R6 half of that scenario is tested in group 2)
- [x] 1.2 R14 class in `rules/m2.py`, `figure_patterns` / `figure_exclude_patterns` (shared with R3) / `figure_extra_exclude_patterns` / `past_patterns` / `future_patterns` / `disclaimer_patterns` (shared with R6) in `m2_rules.yaml` (new keys in `KNOWN_PARAMS`, validated), `implemented: true`; tests green
- [x] 1.3 Mutation check; `mutations: 10 tried, 10 caught`; review fixes (follow-ups R1-R7): `mutations: 10 tried, 10 caught`

## 2. Evidence locator and R6 hidden risk (~1 h)

- [x] 2.1 Failing tests: `RuleResult.evidence_locator` validates against `finding.schema.json` (skipped without `CONTRACTS_DIR`); R6 scenarios (alfa footer `fail`, main region `pass`, footer visible on load `pass`, unknown position `uncertain`, no blocks `not_applicable`, no risk block `not_applicable` with `brak informacji o ryzyku`, only desktop/mobile/tablet evaluated, footnote-only past-performance disclaimer gives R6 `fail`); a shared helper that locates a block's text in `doc.text` (exact, then whitespace-insensitive) or returns null
- [x] 2.2 `EvidenceLocator` in `models.py`; risk-block detection reusing R3's warning patterns via a YAML anchor; R6 class, `hiding_regions` param; worst viewport wins; tests green
- [x] 2.3 Mutation check; `mutations: 19 tried, 19 caught` (two survivors on the first run closed with tests: no-blocks explanation, hidden plus unknown position); review fixes (follow-ups R11-R13): `mutations: 6 tried, 6 caught`

## 3. R4 risk font size (~45 min)

- [x] 3.1 Failing tests for the R4 scenarios (alfa `fail` with 9 px / 20 px / 0,45 in the explanation, readable `pass`, no blocks `not_applicable`, no risk information `not_applicable` with `brak informacji o ryzyku`, risk text only in an invisible block `not_applicable`, worst viewport decides with `evidence_locator.viewport`); a unit test for the length-weighted median
- [x] 3.2 R4 class, `min_ratio` param (number in (0, 1], validated); tests green
- [x] 3.3 Mutation check; `mutations: 15 tried, 15 caught` (one survivor on the first run closed: the no-blocks explanation is pinned exactly)

## 4. R17 and R18, rules-only part (~1 h)

- [ ] 4.1 Failing tests for the rules-only R17/R18 scenarios (explicit approval `fail`, bare mention `pass`, no mention `not_applicable`; same sentence `fail`, neighbouring sentence `uncertain`, neutral legal footer `pass`), plus the catalogue scenario that only R3, R17, R18 carry `llm:` (loader accepts the block; parsing only, no engine change yet)
- [ ] 4.2 R17, R18 classes; `supervisor_patterns`, `approval_patterns`, `safety_patterns` (shared supervisor dictionary via anchor); `llm:` blocks with Polish questions on R3, R17, R18; `implemented: true`; catalogue comments on R5, R7, R9 (`not_applicable` with `brak informacji o ryzyku` when there is no risk information) and on R11, R15 (ZASÓB "Flaguje w raporcie": report the detection even when compliant) for the change that builds them; tests green
- [ ] 4.3 Mutation check; `mutations: N tried, N caught`

## 5. LLM config and OpenAI-compatible client (~1.5 h, needs `analytics-worker`)

- [ ] 5.1 Failing tests: `stub_llm` fixture with a scripted queue (valid content, truncated JSON, non-chat body, array content, 500, 429, 401, sleep past timeout, closed connection) and request recording; config scenarios (disabled by default, model missing exits 2, budget ≥ claim idle, key never logged); request shape (temperature 0, `response_format`, two messages, no `Authorization` without a key); error taxonomy `LlmUnavailable` / `LlmMalformed`; a conftest guard that fails any judge pointed at a non-stub URL
- [ ] 5.2 `config.py` `LlmSettings.from_env` (validated against `WorkerSettings.claim_min_idle_ms` in the worker), `llm/client.py` on `httpx` (connect 3 s, read `LLM_TIMEOUT_S`), host-only logging; `httpx` pinned in `requirements.txt`, `pip-audit -r analytics/requirements.txt` clean; tests green
- [ ] 5.3 Mutation check; `mutations: N tried, N caught`

## 6. Prompt, delimiting and chunking (~1 h)

- [ ] 6.1 Failing tests: injection scenario (tags neutralized to `[document]`, exactly one block at the edges), ignore rule in the system message, `prompt_version` changes when a question changes and is stable otherwise; chunking scenarios (short text one chunk, four-sentence overlap on the border, over-long sentence cut, `LLM_MAX_CHUNKS` truncation logged as `llm_truncated`, every chunk a substring of `doc.text`)
- [ ] 6.2 `llm/prompt.py` (system template, `module_context`, checks list, output schema, `prompt_version = "v1:" + sha256[:12]`), `llm/chunking.py` on `pre.sentences`; tests green
- [ ] 6.3 Mutation check; `mutations: N tried, N caught`

## 7. Response validation, quote verification, chunk merge (~1 h)

- [ ] 7.1 Failing tests: per-item Pydantic validation (result outside allowed set dropped, unrequested rule id dropped, duplicate keeps first, explanation over 500 chars dropped, control characters stripped); hallucinated quote → `uncertain`, quote under 8 chars → `uncertain`, whitespace-insensitive match maps to the exact original span, pass without quote kept; worst chunk wins with ties to the earliest; one failed chunk drops the module's verdicts
- [ ] 7.2 `llm/judge.py`: `SemanticCheck`, `LlmVerdict`, `JudgeOutcome`, `LlmJudge` protocol, `HttpJudge.judge(...)` wiring client + prompt + chunking + validation; tests green against `stub_llm`
- [ ] 7.3 Mutation check; `mutations: N tried, N caught`

## 8. Engine seam, merge and finding assembly (~1.5 h)

- [ ] 8.1 Failing tests: `run_rules(..., judge=None)` equals rules-only; `when: always` / `uncertain` collection; `Rule.ask_llm` override; merge sets `method` `hybrid` / `llm`; M3 test catalogue with an unmodified `S3.3` rule class refined by YAML only; S-ids accepted for non-M2 catalogues; bad `llm:` block rejected; nothing deferred → no request (`m2-bank-ok`); injection cannot flip the deterministic R18 fail; LLM down / timeout / malformed / 500 keep rules-only with the log reasons; `model.llm` and summary scenarios (used, configured but not used); the evidence check over all mocks rules-only and with a stub judge
- [ ] 8.2 `rules/engine.py` (`llm` spec field, `ask_llm`, collect, one judge call per module, merge), `pipeline.analyze(..., judge=None)`, `modules/m2.py` (`model.llm`, Polish mode sentence); R17 `ask_llm` (always when applicable and not a rules fail), R18 `ask_llm` (neighbouring-sentence case only); tests green
- [ ] 8.3 Mutation check; `mutations: N tried, N caught`
- [ ] 8.4 Tell the `analytics-m1-m3` session (or Damian) that the interface in `llm/judge.py` is frozen, with the commit sha

## 9. R3 borderline proximity refinement (~45 min)

- [ ] 9.1 Failing tests for the R3 LLM scenarios (near-window case deferred and overturned to `pass` hybrid, warning absent never deferred, footnote-only not deferred, warning farther than the margin not deferred, borderline without LLM stays rules-only `fail`); every existing R3 scenario still green
- [ ] 9.2 R3 `ask_llm` for the near-window case only (`borderline_margin` param, validated; the rule records the nearest-warning distance while evaluating); tests green
- [ ] 9.3 Mutation check; `mutations: N tried, N caught`

## 10. Cache, budget and circuit breaker (~1 h)

- [ ] 10.1 Failing tests (`fakeredis`, injected clock): re-scan makes no request, model swap and question edit miss, malformed answer not cached, Redis down is a miss and never raises, cache hit re-runs quote verification; budget exhausted → `llm_budget_exhausted` and rules-only; breaker opens after 3 unavailable, skips calls during the cooldown, half-open success closes it, malformed does not count
- [ ] 10.2 `llm/cache.py` (key from `content_hash`, `prompt_version`, model, module, chunk index/count, sorted rule ids; TTL), budget and breaker in `HttpJudge`; tests green
- [ ] 10.3 Mutation check; `mutations: N tried, N caught`

## 11. Per-sentence language and R10 (~1 h)

- [ ] 11.1 Failing tests: `Sentence.lang` scenarios (eurotrade pl / en, `Ryzyko!` none) with the existing preprocessing tests still green; R10 scenarios (eurotrade `fail`, bank `pass`, bilingual `pass`, no warning `not_applicable` with `brak informacji o ryzyku`, English legal block does not set the main language, unknown language `uncertain`)
- [ ] 11.2 `preprocessing.py` (per-sentence guess with a minimum signal), R10 class reusing the warning anchor, main language from non-legal, non-footer blocks when present, `implemented: true`; tests green
- [ ] 11.3 Mutation check; `mutations: N tried, N caught`

## 12. Wiring: worker, CLI, compose (~1 h)

- [ ] 12.1 Failing tests: the worker builds the judge from env with its Redis client and passes it to `analyze`; `llm_mode` logged (`hosted`, `local`, `disabled`); CLI uses the judge when `LLM_BASE_URL` is set (stub), `--no-llm` forces rules-only, CLI output on `contracts/mocks/documents.json` still passes `contracts/validate.py finding` in both modes
- [ ] 12.2 `worker.py`, `cli.py`, `llm/__init__.build_judge`; `analytics/compose.yaml` passes `LLM_*` and joins `egress` (PR #18 key, no `name:`); `analytics/.env.example` documents every `LLM_*` variable (empty `LLM_BASE_URL` = rules-only; the local values for the `ollama` profile); tests green; `docker compose config` valid with and without `--profile llm`
- [ ] 12.3 Mutation check; `mutations: N tried, N caught`
- [ ] 12.4 Manual, outside pytest: run the CLI on all mock documents against the hosted default endpoint (ADR 0304) and against the local `ollama` swap target (`gemma3:4b`); note whether each returns valid JSON and the latency per document; record the result in the AI log, never in a test

## 13. Closing

- [ ] 13.0 Run the CLI on `contracts/mocks/documents.json` (rules-only and with the stub judge) and update `follow-ups.md` with every rule result that differs from `contracts/mocks/findings.json`; `git diff --exit-code contracts/mocks contracts/mock-server web` is empty (the mocks are a test double and are never edited)
- [ ] 13.1 Apply the iw-docs-update skill: `.docs/analytics-plan.md` §7 (object wrapper `{"results": [...]}`, `prompt_version` as prompt hash, chunk and budget defaults), §5 (P0 rules implemented); `analytics/CLAUDE.md` (LLM env variables, the "LLM only decides deferred checks" rule); `analytics/README.md`; ADRs 0309 and 0310 listed; your own row in `.docs/STATUS.md` only if the coordinator has not taken it; add the iw-ai-log row; `docs-check` clean
- [ ] 13.2 Run the iw-pr-review skill with a normal pass and a `focus: security` pass of iw-reviewer (prompts built from scraped text, quote verification, key handling, new `httpx` dependency, outbound egress), and fix real findings
