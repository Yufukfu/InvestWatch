# Design

## Context

This is stage 3 of analytics. It is planned on `analytics/analytics-llm-p0` at `5b4a547`, where task groups 1-4 of `analytics-llm-p0` are done and groups 5-13 are still to do. That branch already has the following:

- **`rules/engine.py`:** `RuleSpec` with an `llm` field, plus `_check_llm`, `KNOWN_PARAMS` and `_check_params` (pattern lists compile, keys are checked). `run_rules(catalogue, ctx)` has an evidence safety net: a quote that is not a substring of `doc.text` becomes `uncertain`. The judge seam (`run_rules(…, judge=…)`, `Rule.ask_llm`, the verdict merge) is specified in `analytics-llm-p0` design §1-2 and arrives with that change's task group 8.
- **`rules/m2.py`:**
  - R1-R3, R4, R6, R14, R17 and R18;
  - R14's past-performance detector `_is_past_performance`, with figure, amount, past and future patterns, the `_YEAR` regex and the `fetched_at` year;
  - the helpers `_RiskWarnings`, `locate` and `R3RiskNextToReturns._hits` (include minus exclude).
- **`rules/m2_rules.yaml`:** anchors `&risk_patterns`, `&return_figure_exclude`, `&past_performance_disclaimers`, `&footnote_markers` and `&supervisor_patterns`. It has `implemented: false` stubs for R9, R11, R12a, R12b, R13, R15 and R16, with comments carrying the stage-2 decisions ("Flaguje w raporcie" for R11 and R15; R9 `not_applicable` without risk information).
- **`modules/m2.py`:** `score = Σ(w·fail) / Σ(w·applicable)`, where `uncertain` counts as half a fail and `pass` is applicable. So a reported compliant detection lowers the score a little, and a rules-only `uncertain` raises it.

Sources:

- **ZASÓB** (`doc/ZASÓB … kryteria oceny informacji o ryzyku.docx`, read from `word/document.xml`): the operational description and legal basis of each rule, quoted in the specs.
- **Art. 44** of Delegated Regulation 2017/565, for the conditions that ZASÓB only summarises: ust. 3 (comparisons), ust. 4 lit. b and e (5 years or since inception, currency), and ust. 6 (forecasts).
- **The mocks** `contracts/mocks/documents.json` and `findings.json`, which are read only:
  - `eurotrade` has one-year past performance and a forecast, and the mock expects R15 `fail` with `method: llm`;
  - `m2-bank-ok` has IKE with the full tax disclaimer;
  - `m2-alfa-landing` has an imperative return promise.

## Goals / Non-Goals

**Goals:**
- Build R11, R12a, R12b, R15 and R16 rules-first, so that every result is useful with the LLM off.
- Follow ZASÓB wording. Where ZASÓB and the regulation differ, follow the regulation's condition and list it as an open question.
- Count each violation once, in the rule that names it.
- Prove that every catalogue pattern is ReDoS-safe, with a check at load and a timing test.

**Non-Goals:**
- R9, which needs an LLM-first judgement.
- R13, R5, R7 and R8, which are visual and need `blocks` (#29).
- Changes to the LLM layer, preprocessing or the Polish summary.
- Gold-set threshold tuning.

## Decisions

### 1. Ownership of the art. 44 elements: count once (ADR 0315)

Each element of art. 44 that ZASÓB names is owned by exactly one rule. Only that rule fails when the element is missing:

| Element | Owner | Not checked by |
|---|---|---|
| Risk warning next to a return claim (ust. 2 lit. b) | R3 | R15, R12a |
| Placement in a footnote or the legal region | R6 | R14, R15, R16 |
| 5 years, 12-month basis, reference period, source (ust. 4 lit. b, c) | R12a | R14 |
| Currency warning, fees impact (ust. 4 lit. e, f) | R12b | R12a, R3 |
| Past performance not the most prominent element (ust. 4 lit. a) | R13 (later) | all |
| Past-performance disclaimer (ust. 4 lit. d) | R14 | R12a, R15 |
| Forecast warning (ust. 6 lit. e) | R15 | R14 |
| Comparison source and assumptions (ust. 3) | R11 | — |
| Tax disclaimer (ust. 7) | R16 | — |

The same sentence may be evidence in several rules, for example a past-performance sentence quoted by R12a and R14. That is not double counting, because each rule reports a different missing element. Within one rule, several missing elements give one `fail` whose explanation lists them all, never several results.

**Shared trigger.** R12a, R12b and R14 use one detector:
- R14's `_is_past_performance` moves into a `_PastPerformance` base class.
- Its parameter lists are YAML anchors on R14 (`&pp_figure`, `&pp_past`, `&pp_future` and the rest), aliased in R12a and R12b.
- R14's tests stay green unchanged.

This means the three rules can never disagree on whether the material presents past performance.

**Why not one "past performance" rule with sub-results?** The contract has one `rules[]` entry per catalogue id. ZASÓB lists R12a, R12b and R14 separately with their own legal bases. The dashboard shows them separately too.

**Overlaps that are deliberately allowed.** A forecast without a risk warning fails both R3 and R15, because those are two different warnings. A past-performance sentence with a year after the fetch year is a forecast, not past performance: R14's future patterns and the year check already make the two exclusive. A sentence with a past marker and a forecast marker, such as "zarobił 12% w 2024 r., w 2027 spodziewamy się 15%", triggers both R14 and R15. That is correct: it states both a past result and a forecast.

### 2. "Flaguje w raporcie": a pass that quotes the detection (ADR 0315)

ZASÓB R15 says "Flaguje w raporcie wykrycie prognozy". ZASÓB R11 says "flaguje naruszenia w raporcie", which refers to violations. The coordinator's stage-2 answer, recorded in the `m2_rules.yaml` comments, reads both as "report the detection even when compliant". Open question 3 asks Damian to confirm the reading for R11.

The finding already carries every rule result in `rules[]`. So for R11 and R15:
- A compliant detection is `pass`.
- Its `evidence` is the detected comparison or forecast, not the warning. R14 is different: there a `pass` quotes the disclaimer.
- The explanation starts with `Wykryto porównanie` or `Wykryto prognozę` and then says what made it compliant.
- No detection gives `not_applicable` with null evidence.

Options considered:
- **(a) `uncertain` for every detection.** This makes every compliant forecast half a violation in the score, so the dashboard would rank lawful pages as risky.
- **(b) A new result value or a flag field.** This is a contract change after the freeze.
- **(c) A line in the Polish summary.** This edits the `document-analysis` M2 finding assembly requirement, which `analytics-llm-p0` is also changing (spec merge order risk). It is left as follow-up F3.
- **(d) A pass with the detection as evidence.** This uses only v1 fields and is visible in the rule list.

We chose (d).

### 3. R11 comparisons

- **Trigger, in two tiers.**
  - Explicit comparisons: a comparative followed by `niż` within `(?:\w+\s+){0,3}`, or a comparison marker. These go to the source and assumptions check.
  - Superlatives without a comparator (`najlepsz…`, `nr 1`, `best`): an implicit market comparison that the rules cannot confirm. Rules-only `uncertain`.
- **Excludes.** Temporal and inflation comparatives (`niż rok temu`, `niż wcześniej`, `niż kiedykolwiek`, `niż inflacja`) are stripped before matching, using the include-minus-exclude helper `_hits`. Art. 44 ust. 3 covers comparisons of services, instruments or providers. Inflation is not one of them (our reading, open question 4).
- **Source and assumptions** may appear anywhere, footnotes included. ZASÓB asks whether they are given, not where they are, and footnote placement of risk text is R6's concern. The source dictionary is a YAML anchor (`&source_markers`) shared with R12a.
- **Results:**
  - no source: `fail`;
  - a source but no assumptions: `uncertain`, which goes to the LLM;
  - both: `pass`.

  Assumptions are hard to detect lexically, so the missing-assumptions case is `uncertain` rather than `fail`.
- **`llm:` block:** `when: uncertain`. The question asks "is this a comparison of products or services, and are the source and the key assumptions stated?", and asks for a quote.

### 4. R12a period and scope

All four elements are computed in code from YAML pattern lists, plus two numeric checks that a regex cannot express:

- **`N miesięcy`.** A period of N months is sub-annual unless N % 12 == 0, so `12 miesięcy` and `24 miesiące` are full periods. The regex `\b(\d{1,3})\s*miesi\w*` captures N.
- **5-year coverage from a year range.** A range `(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}` counts when `end - start + 1 >= 5`, or there are past figures for at least 5 distinct years (a `_YEAR` match in past-performance sentences).
- **Longer periods.** `ostatnich N lat` counts for N ≥ 5, because 10 years include the last 5.
- **Since inception.** `od początku działalności`, `od uruchomienia`, `since inception` and similar give `uncertain` when it is the only coverage. Art. 44 ust. 4 lit. b allows this only for a product that has existed for less than 5 years, and the rules cannot know the product's age. The LLM is asked whether the material states it.
- **Reference period** is searched only in past-performance sentences. A year elsewhere on the page does not date the figure.
- **Evidence.** The 12-month-basis failure quotes the sub-annual sentence. Every other failure quotes the first past-performance sentence. The explanation lists every missing element in a fixed order: okres 12 mies., 5 lat, okres referencyjny, źródło.

### 5. R12b currency and costs

- **Costs** always apply when past performance is present. ZASÓB asks whether the impact of fees is stated. The regulation requires it only for gross performance (ust. 4 lit. f), but the rules cannot tell gross from net unless the text says so, and a net statement satisfies the check anyway.
- **Currency** applies only to past results given in a non-PLN currency, or a product denominated in one (ust. 4 lit. e: "denominated in a currency other than that of the Member State in which the retail client is resident"). ZASÓB R12b states the currency warning without that condition. Requiring it on every PLN page would fail almost every domestic fund advert, so we follow the regulation's condition. Open question 1 asks Damian to confirm.
- **Rules-only.** There is no `llm:` block: both checks are lexical.

### 6. R15 forecasts

- **Markers in two strengths.**
  - Strong markers (`prognoz…`, `spodziewa…`, `oczekuj…`, `w przyszłym roku`, a future year) together with result vocabulary make a forecast.
  - Weak markers (`będzie`, `będą`, `może przynieść`, `will`) make a forecast only together with a figure.
  - A weak marker with result vocabulary and no figure is `uncertain`, and goes to the LLM.

  `będzie` alone is everywhere in Polish marketing (`konto będzie aktywne`), and it would flood R15.
- **The promotional imperative** (`Zarabiaj nawet do 18% rocznie`) is not a forecast. It is a return claim, and R3 owns its risk warning (decision 1). Open question 2 asks Damian whether he wants R15 to catch imperatives too.
- **The forecast warning** is a separate list (`&forecast_disclaimers`). The R14 disclaimer ("wyniki historyczne nie są gwarancją przyszłych wyników") speaks about past results, and ZASÓB R15 names the forecast explicitly. A sentence that matches both lists ("ani prognozy, ani wyniki historyczne nie są…") satisfies both rules.
- **Excludes.** Forecast-warning sentences are removed from the trigger, so a lone warning is `not_applicable`. Fee and tax percentages are removed with `&return_figure_exclude`.
- **`llm:` block:** `when: uncertain`. The question asks "does this sentence forecast future results of the product (fail if there is no warning, pass if not a forecast)?" and asks for a quote.

### 7. R16 tax

- **Trigger and VAT.** The tax trigger strips VAT phrases first, because VAT is not tax treatment of the investment.
- **The two disclaimer parts.** Both are needed, because ZASÓB and ust. 7 name both. The "may change" part counts only when it is tied to the tax context: either in the same sentence as the individual part, or in a sentence that mentions tax or `przepis…`. Otherwise "Oferta może ulec zmianie" would satisfy it.
- **The disclaimer sentence** is excluded from the trigger, so a page whose only tax word is the disclaimer is `not_applicable`. The disclaimer is lawful text, not a reference to tax benefits.
- **Rules-only.**

### 8. ReDoS-safe patterns

Kacper found a catastrophic-backtracking regex in preprocessing. Catalogue patterns run on untrusted scraped text, and Python `re` has no timeout. We use two defences:

- **A lint at load.** `_check_params` parses each `*_patterns` entry and `negation_before` with `re._parser` (CPython's own parser; the import is guarded and falls back to `sre_parse`). It walks the tree and rejects a `MAX_REPEAT` or `MIN_REPEAT` node with an unbounded maximum that contains another such node, for example `(\w+\s*)+`, `(?:a*)*` or `(.+)+`. Bounded outer repeats such as `(?:\w+\s+){0,3}` are allowed, because their backtracking is polynomial and small. Alternation overlap, for example `(a|a)*`, is not detected statically, and the timing test covers it.

  We use the private parser rather than a regex-on-regex heuristic, because it sees through groups and escapes. The risk is that a future CPython renames it. The guarded import and a unit test on the parser output make that a loud failure, not a silent pass.
- **A timing test** runs every catalogue pattern and every module-level regex in `rules/m2.py` (`_YEAR`, `N miesięcy`, the year range) with `search` over 20 000-character adversarial strings: `"a " * n`, `"%" * n`, `"niż " * n`, one unbroken word, and `"1 " * n`. Each search must finish within 0.2 s on the CI runner.
- **Scope.** The lint runs over the whole catalogue, existing patterns included. If an existing R1-R18 pattern fails, task group 1 fixes it and records it in `follow-ups.md`. A scratch run of this lint over the base branch's 175 catalogue patterns, made while planning, found no nested unbounded repeat.

### 9. Catalogue

- **`legal_basis`** comes from ZASÓB:
  - R9: art. 44 ust. 2 lit. d;
  - R11: art. 44 ust. 3;
  - R12a and R12b: art. 44 ust. 4;
  - R13: art. 44 ust. 4 lit. a;
  - R16: art. 44 ust. 7.

  Names stay as they are, because they match `contracts/mocks/generate_mocks.py`.
- **R9** gets the comment "LLM-first (no rules signal); `not_applicable` with `brak informacji o ryzyku` without risk information".
- **R13** gets the comment "visual, needs `blocks` (#29)".
- **New parameter keys** go into `KNOWN_PARAMS`. All of them end in `_patterns`, so the existing validation applies: `comparison_patterns`, `comparison_exclude_patterns`, `superlative_patterns`, `source_patterns`, `assumption_patterns`, `short_period_patterns`, `five_year_patterns`, `inception_patterns`, `fee_patterns`, `foreign_currency_patterns`, `currency_warning_patterns`, `forecast_patterns`, `forecast_weak_patterns`, `performance_patterns`, `forecast_disclaimer_patterns`, `tax_patterns`, `tax_exclude_patterns`, `tax_individual_patterns`, `tax_change_patterns`, `tax_context_patterns`.

### 10. LLM blocks and the seam

R11, R12a and R15 get `llm: {when: uncertain, question: …}`. They use the default `ask_llm` from `analytics-llm-p0` design §1, which asks the LLM when the rules-only result is `uncertain`, so these rules need no override. A deterministic `fail` or `pass` is never deferred, so the injection surface stays as small as stage 2 set it.

On the base branch the loader already parses `llm:` blocks, so groups 1-6 work without the judge. Group 7 adds `FakeJudge` tests for the merge and needs `analytics-llm-p0` group 8. If that group never lands, the blocks are inert, the rules-only `uncertain` stands, and the catalogue scenario is still true.

## Risks / Trade-offs

- **Lexical source and assumption detection is lenient.** `Źródło: opracowanie własne` passes the source check, and "w okresie" anywhere counts as assumptions. → The gold set calibrates this. Missing assumptions alone give `uncertain`, not `pass`.
- **A rules-only `uncertain` raises the score**, by half a fail, for superlatives (R11), since-inception periods (R12a) and weak forecasts (R15). → With the LLM on, it resolves them. With it off, the cases are visible and honest. Open question 5 asks whether superlatives should instead be `pass` rules-only.
- **R12a can fail on pages that are legal but terse.** For example, a fund page that gives 5 years in a table the scraper flattens without years. → The text fallback with distinct years covers flattened tables. The rest is gold-set work.
- **Results differ from the mocks.** `eurotrade` gets R12a and R12b `fail` (absent in the mock) and R15 with `method: rule` instead of `llm`. `m2-bank-ok` gets R16 `pass`. The mocks are never edited; the differences are in `follow-ups.md`.
- **Merge order.** This change modifies the "Rule catalogue" requirement, which `analytics-llm-p0` also modifies. This change's delta restates the post-stage-2 text, so it must be archived after `analytics-llm-p0`. When rebasing onto `main`, re-read the main spec and re-check the delta's full text.
- **`re._parser` is private.** → See decision 8. The fallback and the test make a break loud.

## Cut plan

The total is about 7.5 h of agent work plus closing. If time runs short, cut in this order. The first items cut are the cheapest to lose:

1. **Group 7** (LLM blocks tested against the judge). The rules-only results stand.
2. **Group 6** (R11). It has the weakest lexical signal and the most `uncertain` results. Without the LLM it adds noise.
3. **The superlative tier of R11 only.** Keep the explicit comparisons.
4. **The since-inception branch of R12a.** Treat it as coverage met, with a follow-up.

Never cut group 1 (the ReDoS guard). Every later group adds patterns that it protects.

## Resolved questions

Settled by the brief and the stage-2 answers. Damian can override them.

1. R11 and R15 report a compliant detection: a `pass` quoting the detection (decision 2).
2. Each rule is `not_applicable` without its trigger, and a violation is counted once, by the owner of the element (decision 1, ADR 0315).
3. R9 is not built here: there is no cheap rules signal, so it waits for an LLM-first change. R13 is not built here: it needs `blocks` (#29).
4. The mocks are not edited. The differences go to `follow-ups.md`.

## Open Questions

For Damian. Each one has a default, which the plan implements unless he answers otherwise.

1. **R12b currency warning.** Should it be needed only for non-PLN results (art. 44 ust. 4 lit. e; the default), or on every past-performance page (ZASÓB's wording, without the condition)?
2. **R15 and promotional imperatives.** Is `Zarabiaj nawet do 18% rocznie` a forecast? The default is no: it is a return claim owned by R3. Yes would make R15 fail on `m2-alfa-landing` too.
3. **R11 "flaguje naruszenia".** ZASÓB R11 flags violations, and R15 flags detections. Is a compliant comparison reported as a `pass` with the comparison quoted (the default, the same as R15), or left as a plain `pass` without evidence?
4. **R11 scope.** Are comparisons with inflation or a market index product comparisons? The default excludes inflation and includes indices and benchmarks.
5. **R11 superlatives rules-only.** Should `Najlepsze konto na rynku` without a source be `uncertain` (the default, half a fail) or `pass` with the LLM off?
6. **R12a since inception.** Should "od początku działalności" with no product age be `uncertain` (the default) or `pass`?
