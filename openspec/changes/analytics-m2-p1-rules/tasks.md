# Tasks

Stage 3, the lowest priority (Damian). Do not start before `analytics-llm-p0` task groups 5-12 are done and the coordinator gives the go. The work starts on `analytics/analytics-llm-p0`, and the branch is rebased onto `main` once `analytics-worker` and `analytics-llm-p0` merge. Groups 1-6 need only the stage-2 rule engine and R14, which are already on the base branch. Group 7 needs `analytics-llm-p0` task group 8 (the judge seam). The estimates are for one agent session, tests included. If time runs short, cut in the order of the "Cut plan" in `design.md`. Tests read `contracts/mocks/*.json` but never edit them. Every new pattern uses bounded gaps only (design decision 8).

## 1. ReDoS guard and the shared past-performance detector (~1 h)

- [x] 1.1 Write the failing tests. In `tests/test_regex_safety.py`:
  - The loader rejects `(\w+\s*)+niż`, `(?:a*)*` and `(.+)+` in a `*_patterns` list and in `negation_before`, and the error names the rule and the key.
  - The loader accepts `(?:\w+\s+){0,3}` and `.{0,80}?`.
  - A parser-shape test fails loudly if `re._parser` and `sre_parse` are both missing.
  - Timing: every catalogue pattern and every module-level regex in `rules/m2.py` is searched over five 20 000-character adversarial inputs, and each search takes at most 0.2 s.

  In addition, the R14 tests run unchanged against a `_PastPerformance` base.
- [x] 1.2 Add the nested-unbounded-repeat lint to `_check_params` in `rules/engine.py`. Move R14's detector into `_PastPerformance` in `rules/m2.py`, and anchor R14's detector lists in `m2_rules.yaml` (`&pp_figure`, `&pp_amount`, `&pp_amount_return`, `&pp_figure_exclude`, `&pp_past`, `&pp_future`). If an existing pattern is rejected, fix it and log it in `follow-ups.md`. Tests green.
- [x] 1.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 13 tried, 13 caught` (lint: each guard, the nesting flag, lazy repeats, descent into branches; a quadratic module regex the lint cannot see is caught by the timing test; the moved detector: past and future markers, the year boundary, the amount conjunct). No shipped M1-M3 pattern was rejected. Review fix (opcode identity, a class range like `[+-9]` crashed the load): `mutations: 1 tried, 1 caught`. After the rebase onto llm-p0's faster R14 detector, its 5 detector mutations were re-run: `mutations: 5 tried, 5 caught`. The timing test takes the best of 3 runs per search, so a loaded runner's pause is not a red.

## 2. R16 tax information (~45 min)

- [x] 2.1 Write the failing tests for the R16 scenarios:
  - `m2-bank-ok` gives `pass`, with the disclaimer as evidence;
  - `bez podatku Belki w IKZE` gives `fail`;
  - only the individual part gives `fail`, naming the missing change part;
  - `Oferta może ulec zmianie` does not count, and gives `fail`;
  - VAT only gives `not_applicable`;
  - a lone disclaimer sentence gives `not_applicable`;
  - `eurotrade` gives `not_applicable`;
  - empty text gives `not_applicable`.
- [x] 2.2 Write the R16 class. Add `tax_patterns`, `tax_exclude_patterns`, `tax_individual_patterns`, `tax_change_patterns` and `tax_context_patterns` (new `KNOWN_PARAMS`), set the legal basis to art. 44 ust. 7, and set `implemented: true`. Tests green.
- [x] 2.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 13 tried, 13 caught` (VAT strip and its long form, the disclaimer excluded from the trigger, the change part's tax context both ways, each half of the pass condition, each missing part named, both evidence choices, `IKE` as a tax word, the legal basis). Two stage-2 tests change with R16: `test_catalogue_is_complete` lists R16, and `test_compliant_material` gets the tax disclaimer of the `m2-bank-ok` mock (IKE without it is R16's violation). Review fix (`podatny` is not a tax word; a tax claim inside a partial disclaimer still triggers; a generic subject such as "traktowanie podatkowe" is stripped with the disclaimer, new key `tax_subject_patterns`): `mutations: 4 tried, 4 caught`.

## 3. R15 forecasts (~1 h)

- [x] 3.1 Write the failing tests for the R15 scenarios:
  - `eurotrade` gives `fail`, with the forecast as evidence;
  - a forecast with the warning gives `pass`, quoting the forecast, with the explanation starting `Wykryto prognozę`;
  - a weak marker with a figure gives `fail`;
  - a weak marker without a figure gives `uncertain`;
  - the R14 disclaimer alone gives `fail`;
  - `m2-alfa-landing` gives `not_applicable`;
  - a lone warning sentence gives `not_applicable`;
  - a year after `fetched_at` is a strong marker;
  - `W 2026 zarobisz nawet 12%.`, fetched in 2026, gives `fail` (a future-tense verb with a figure);
  - the imperatives `zarabiaj` and `zyskaj` are never forecast markers;
  - a fee percentage with `będzie` is not a forecast.
- [x] 3.2 Write the R15 class. Add `forecast_patterns`, `forecast_verb_patterns`, `forecast_exclude_patterns` (the imperatives), `forecast_weak_patterns`, `performance_patterns` and `forecast_disclaimer_patterns` (`&forecast_disclaimers`), reusing `*return_figure_exclude`, and set `implemented: true`. Tests green.
- [x] 3.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 16 tried, 16 caught` (the excludes, the result-vocabulary gate, the future-year boundary and marker, the future-tense verb with and without a figure, both weak-marker branches, the candidate tier, warnings kept out of the trigger, the compliant pass quoting the forecast and starting `Wykryto prognozę`, the R14 disclaimer not counting, the imperative exclude, `w przyszłym roku`). Three survivors on the first run got their own tests (fetch-year boundary, `w przyszłym roku` alone, the imperative as vocabulary). Review fix (R16: generic tax words such as `opodatkowanie`, `podatkowe`, `taxation` never make a disclaimer sentence a reference; R15: the fee-percentage exclude no longer blanks a return verb): `mutations: 5 tried, 5 caught`.

## 4. R12a period and scope (~1.25 h)

- [x] 4.1 Write the failing tests for the R12a scenarios:
  - `eurotrade` gives `fail`, naming the sub-checks `5 lat / 12 mies.` and `źródło`, and not `okres referencyjny`;
  - 2021–2025 with a source gives `pass`;
  - `od początku roku` gives `fail`, quoting that sentence;
  - `ostatnich 12 miesiącach` is a full period;
  - `w 3 miesiące` is sub-annual;
  - no reference period gives `fail`, naming `okres referencyjny`;
  - since inception without a date gives `fail` (reference period), with the 5-year sub-check named as `uncertain`;
  - since inception with a start year gives `uncertain`, naming only the 5-year sub-check;
  - `ostatnich 10 lat` covers 5 years;
  - five distinct past years cover 5 years;
  - `m2-alfa-landing` gives `not_applicable`;
  - the explanation names the sub-checks that are not `pass`, with their status, in a fixed order;
  - shared trigger: R12a, R12b and R14 are `not_applicable` together on `m2-bank-ok`.
- [x] 4.2 Write the R12a class on `_PastPerformance`, with the three named sub-checks as a `SubCheck` list and the result taken as the worst of them. Add `short_period_patterns`, `five_year_patterns`, `inception_patterns` and `source_patterns` (`&source_markers`), the N-month and year-range checks in code (ReDoS-tested in group 1's timing test), the legal basis art. 44 ust. 4, and `implemented: true`. Tests green.
- [x] 4.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 18 tried, 18 caught` (N months and the multiple of 12, the short-period list and its precedence, the 5-year boundaries for `ostatnich N lat`, a year range and distinct years, the 5-year words, since inception as `uncertain`, each reference-period source, the source check, worst-of, only non-pass sub-checks listed, their fixed order, the decisive sentence as evidence, the legal basis). YAML cannot alias forward and R12a precedes R14, so the `pp_*` lists and `source_markers` now live in the catalogue's `shared:` section, aliased by R12a, R12b and R14 (R14's rules are unchanged, asserted when moving). The months regex uses bounded spaces (`\s{0,3}`), and the timing test gained a digit followed by 20 000 spaces. The two shared-trigger scenarios move to group 5, because they need R12b. Review fix (R15's fee and tax exclude spans punctuation and up to 60 characters within the sentence, stopping only at a return verb; the noun `zysków` does not stop it): `mutations: 4 tried, 4 caught`.

## 5. R12b currency and costs (~45 min)

- [x] 5.1 Write the failing tests for the R12b scenarios:
  - `eurotrade` gives `fail`, naming fees only, and the explanation says the currency warning is not required for PLN results under `art. 44 ust. 4 lit. e`;
  - every R12b explanation cites `art. 44 ust. 4 lit. e`;
  - a fee statement with PLN figures gives `pass`;
  - `nie uwzględniają opłat` counts as a fee statement;
  - USD without a warning gives `fail`, quoting the USD sentence;
  - USD with a warning gives `pass`;
  - `denominowany w EUR` triggers the currency part;
  - `m2-bank-ok` gives `not_applicable`;
  - the "missing disclaimer fails only R14" scenario passes.
- [x] 5.2 Write the R12b class on `_PastPerformance`. Add `fee_patterns`, `foreign_currency_patterns` and `currency_warning_patterns`, and set `implemented: true`. Tests green.
- [x] 5.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 13 tried, 13 caught` (the fee statement, the currency part both ways, the warning, the denominated product and its currency conjunct, lit. e cited for PLN, the PLN note on a fail, the foreign sentence as evidence, the shared trigger, `uwzględniają opłat`, the currency code, the legal basis). One survivor on the first run (a foreign currency outside the results, such as a USD bonus) got its own test. The USD scenario uses `w 2025 roku`, because the sentence splitter keeps `2025 r. Wyniki…` as one sentence. Review fix (R15's fee exclude was quadratic on a fee word followed by a digit run, `\w*` after the stem, now letters only, plus a timing input; it also stops at the noun `zysk` again, not `zysków`; an R12b explanation always cites lit. e): `mutations: 5 tried, 5 caught`.

## 6. R11 product comparisons (~1 h)

- [x] 6.1 Write the failing tests for the R11 scenarios:
  - `3 razy więcej niż lokata` with no source gives `fail`;
  - a source and assumptions give a plain `pass`: it quotes the comparison, and the explanation does not start with `Wykryto`;
  - a source without assumptions gives `uncertain`;
  - `niż rok temu`, `niż inflacja` and `w porównaniu z inflacją` give `not_applicable`;
  - `niższe niż w innych biurach maklerskich` with no source gives `fail`;
  - `pobił WIG20` and `lepszy niż benchmark` with no source give `fail` (the extension);
  - a superlative only gives `uncertain`, and the explanation names the missing source;
  - `m2-bank-ok` gives `not_applicable`;
  - empty text gives `not_applicable` without raising;
  - a source in a footnote counts.
- [x] 6.2 Write the R11 class. Add `comparison_patterns`, `comparison_exclude_patterns`, `benchmark_patterns` (the extension, in its own list), `superlative_patterns`, `source_patterns: *source_markers` and `assumption_patterns`, set the legal basis to art. 44 ust. 3, and set `implemented: true`. Tests green.
- [x] 6.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 19 tried, 19 caught` (R11: the excludes, the benchmark extension, superlatives, source and assumptions, an explicit comparison over a superlative, the missing source named, fail vs uncertain, the plain pass, a number after `niż`, inflation, the legal basis; gold calibration: the year table as a past marker and its fetch-year bound, table years for the 5-year check, the two R16 tax-inclusion excludes, the comparison-method source and the date and amount assumptions). Gold-set calibration (`analytics/eval/gold.jsonl`, ADR 0312): R11 alone moved the measured M2 default 0.1 -> 0.2 (`test_eval_thresholds`), because the gold sample `m2-r11-comparison-with-source` names its source as a comparison method and its assumptions as a date and an order size. The same pass found that the shared detector missed `2021: 2,1%` year tables (R12a, R12b and R14 `not_applicable` on three gold samples), and that R16 read `nie uwzględniają podatku` as tax treatment. With those fixed, 17 of the 18 gold expectations for R11, R12a, R12b, R14, R15 and R16 hold, and the measured M2 default is 0.1 again. The one left, R14 on `m2-r13-past-performance-dominates`, is a `blocks`-based sample (F1). Review fix (a publisher line "opublikowany przez" is not a source; document numbers and best execution are not superlatives): `mutations: 5 tried, 5 caught`.

## 7. Catalogue scenarios and `llm:` blocks (~45 min, needs `analytics-llm-p0` group 8)

- [x] 7.1 Write the failing tests:
  - catalogue complete: R1, R2, R3, R4, R6, R11, R12a, R12b, R14, R15, R16, R17 and R18 are implemented (R10 stays unbuilt: `analytics-llm-p0` merged without its group 11);
  - `llm:` blocks only on R3, R11, R12a, R15, R17 and R18;
  - every entry has a legal basis;
  - `FakeJudge`: an R15 weak-marker `uncertain` is deferred and its verdict merged as `hybrid`; R15's strong `fail` is never deferred; an R11 superlative is deferred; an R12a since-inception case is deferred; R12b and R16 never send a check;
  - the evidence check over all mocks holds, rules-only and with the stub judge.
- [x] 7.2 Write the `llm:` blocks with Polish questions on R11, R12a and R15 (`when: uncertain`). Set the legal bases for R9 and R13, and add the catalogue comments on R9 (LLM-first) and R13 (visual, #29). Correct the stage-2 R11 comment to say that ZASÓB "flaguje naruszenia" means violations only (follow-up F6). Tests green.
- [x] 7.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 7 tried, 7 caught` (each of the three blocks missing, R11 and R15 set to `when: always`, the R9 and R13 legal bases). The stage-2 pin `test_llm_blocks_only_on_r3_r17_r18` now lists the six refined rules. The R11 catalogue comment (F6) was replaced with the R11 entry in group 6.

## 8. Mock run (~30 min)

- [ ] 8.1 Run the CLI on `contracts/mocks/documents.json`, rules-only. The output must pass `contracts/validate.py finding`. Update `follow-ups.md` rows M1-M7 with the real results and add any new rows. `git diff --exit-code contracts/mocks contracts/mock-server web` must be empty.

## 9. Closing

- [ ] 9.1 Apply the iw-docs-update skill:
  - `.docs/analytics-plan.md` §5: the status of R11, R12a, R12b, R15 and R16; R13 marked visual (#29); R9 marked LLM-first;
  - `analytics/README.md`: the rule list;
  - list ADR 0315 and check that it is listed in `.docs/decisions/README.md`;
  - your own domain file in `.docs/status/` only if the coordinator has not taken it;
  - add the iw-ai-log row;
  - `docs-check` clean.
- [ ] 9.2 Run the iw-pr-review skill, including iw-reviewer with a regex-safety focus over the new patterns, and fix real findings.
