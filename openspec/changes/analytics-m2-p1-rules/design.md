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
- Follow ZASÓB wording. Where ZASÓB and the regulation differ, follow the regulation's condition and cite it in the rule's explanation (resolved question 1).
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

### 2. "Flaguje w raporcie": R15 reports every forecast, R11 only violations (ADR 0315)

The two rules use different ZASÓB wording, and Damian's answer (answer 3) follows it:
- **R15** says "Flaguje w raporcie wykrycie prognozy": the detection itself is flagged. A compliant forecast is `pass`, its `evidence` is the forecast (not the warning), and its explanation starts with `Wykryto prognozę` and then names the warning that made it compliant.
- **R11** says "flaguje naruszenia w raporcie": only violations are flagged. A compliant comparison is a plain `pass`. It still stores the quoted comparison as `evidence`, so the reviewer can see what was judged, but its explanation does not start with `Wykryto` and does not present the comparison as a flag.

In both rules, no detection gives `not_applicable` with null evidence. R14 is different again: its `pass` quotes the disclaimer.

The stage-2 catalogue comment on R11 ("report the detection even when compliant") is corrected in group 7.

Options considered:
- **(a) `uncertain` for every detection.** This makes every compliant forecast half a violation in the score, so the dashboard would rank lawful pages as risky.
- **(b) A new result value or a flag field.** This is a contract change after the freeze.
- **(c) A line in the Polish summary.** This edits the `document-analysis` M2 finding assembly requirement, which `analytics-llm-p0` is also changing (spec merge order risk). It is left as follow-up F3.
- **(d) A pass with the detection as evidence.** This uses only v1 fields and is visible in the rule list.

We chose (d).

### 3. R11 comparisons

- **Scope (answer 4).** The core is ZASÓB's "porównania produktów i usług": other products, services or providers (`lepsze niż lokata`, `niższe prowizje niż w innych biurach`). Index and benchmark comparisons (`WIG20`, `benchmark`, `średnia funduszy`) are included as an extension, in their own pattern list (`benchmark_patterns`), so they can be cut alone. Inflation is out.
- **Trigger, in two tiers.**
  - Explicit comparisons: a comparative followed by `niż` within `(?:\w+\s+){0,3}`, or a comparison marker. These go to the source and assumptions check.
  - Superlatives without a comparator (`najlepsz…`, `nr 1`, `best`): an implicit market comparison that the rules cannot confirm. R11 "weryfikuje źródło informacji", so an unsourced superlative leans toward `fail` (answer 5). Rules-only it is `uncertain`, with an explanation that names the missing source as the reason. The LLM may confirm that it is a comparison.
- **Excludes.** Temporal and inflation comparatives (`niż rok temu`, `niż wcześniej`, `niż kiedykolwiek`, `niż inflacja`, `w porównaniu z inflacją`) are stripped before matching, using the include-minus-exclude helper `_hits`. Art. 44 ust. 3 covers comparisons of services, instruments or providers, and inflation is not one of them.
- **Source and assumptions** may appear anywhere, footnotes included. ZASÓB asks whether they are given, not where they are, and footnote placement of risk text is R6's concern. The source dictionary is a YAML anchor (`&source_markers`) shared with R12a.
- **Results:**
  - no source: `fail`;
  - a source but no assumptions: `uncertain`, which goes to the LLM;
  - both: `pass`.

  Assumptions are hard to detect lexically, so the missing-assumptions case is `uncertain` rather than `fail`.
- **`llm:` block:** `when: uncertain`. The question asks "is this a comparison of products or services, and are the source and the key assumptions stated?", and asks for a quote.

### 4. R12a period and scope

R12a is modelled as three named sub-checks (answer 6), each `pass`, `fail` or `uncertain`:
1. `5 lat / pełne okresy 12-mies.`
2. `okres referencyjny`
3. `źródło`

The rule result is the worst sub-check. The explanation names every sub-check that is not `pass`, with its status, so the dashboard says which one failed. A small `SubCheck(name, status, sentence)` list in the class keeps this in one place, and the tests assert on the names.

The sub-checks are computed in code from YAML pattern lists, plus two numeric checks that a regex cannot express:

- **`N miesięcy`.** A period of N months is sub-annual unless N % 12 == 0, so `12 miesięcy` and `24 miesiące` are full periods. The regex `\b(\d{1,3})\s*miesi\w*` captures N.
- **5-year coverage from a year range.** A range `(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}` counts when `end - start + 1 >= 5`, or there are past figures for at least 5 distinct years (a `_YEAR` match in past-performance sentences).
- **Longer periods.** `ostatnich N lat` counts for N ≥ 5, because 10 years include the last 5.
- **Since inception.** `od początku działalności`, `od uruchomienia`, `since inception` and similar make only the 5-year sub-check `uncertain`, when they are the only coverage. Art. 44 ust. 4 lit. b allows this only for a product that has existed for less than 5 years, and the rules cannot know the product's age. ZASÓB separately asks "czy wskazano okres referencyjny", so a since-inception marker without a year or date fails `okres referencyjny` outright, and the rule is `fail`. Only with a start year (`od uruchomienia w 2023 r.`) can the result be `uncertain`. The LLM is then asked whether the material states the product's age, which it can do only when the 5-year sub-check is the only one not `pass`.
- **Reference period** is searched only in past-performance sentences. A year elsewhere on the page does not date the figure.
- **Evidence.** A sub-12-month failure quotes the sub-annual sentence, an `uncertain` quotes the since-inception sentence, and every other failure quotes the first past-performance sentence. The explanation lists the sub-checks in the fixed order given above.

### 5. R12b currency and costs

- **Costs** always apply when past performance is present. ZASÓB asks whether the impact of fees is stated. The regulation requires it only for gross performance (ust. 4 lit. f), but the rules cannot tell gross from net unless the text says so, and a net statement satisfies the check anyway.
- **Fees in scope (answer 1).** The fees and charges check ("wskazano wpływ prowizji, opłat i obciążeń na wyniki") always applies when past performance is shown.
- **Currency** applies only to past results given in a non-PLN currency, or a product denominated in one (ust. 4 lit. e: "denominated in a currency other than that of the Member State in which the retail client is resident"). ZASÓB R12b ("Weryfikuje, czy zawarto ostrzeżenie o wpływie zmian kursów walutowych…") states the currency warning without that condition. Requiring it on every PLN page would fail almost every domestic fund advert, so we follow the regulation's condition, as Damian confirmed.
- **Explanation.** So that a juror who reads ZASÓB sees why the condition exists, every R12b explanation cites `art. 44 ust. 4 lit. e` for the currency part. When the part does not apply, it says so: "ostrzeżenie walutowe niewymagane – wyniki w PLN (art. 44 ust. 4 lit. e)".
- **Rules-only.** There is no `llm:` block: both checks are lexical.

### 6. R15 forecasts

- **Markers in two strengths.**
  - Strong markers (`prognoz…`, `spodziewa…`, `oczekuj…`, `w przyszłym roku`, a future year) together with result vocabulary make a forecast.
  - Weak markers (`będzie`, `będą`, `może przynieść`, `will`) make a forecast only together with a figure.
  - A weak marker with result vocabulary and no figure is `uncertain`, and goes to the LLM.

  `będzie` alone is everywhere in Polish marketing (`konto będzie aktywne`), and it would flood R15.
- **A figure tied to a future period** is a forecast (answer 2), even in the fetch year. A future-tense return verb (`zarobisz`, `zyskasz`, `przyniesie`, `wypracuje`, `osiągnie`) together with a figure is a strong marker (`W 2026 zarobisz 12%`), and so are `w przyszłym roku spodziewamy się…` and a year after the fetch year.
- **The promotional imperative** (`Zarabiaj nawet do 18% rocznie`, `zyskaj`, `earn`) is not a forecast. It is a return claim, and R3 owns its risk warning (decision 1, answer 2). The imperative forms are listed as excludes, so `zyska…` does not catch `zyskaj`.
- **Every detected forecast is reported** (decision 2).
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
- **New parameter keys** go into `KNOWN_PARAMS`. All of them end in `_patterns`, so the existing validation applies: `comparison_patterns`, `comparison_exclude_patterns`, `benchmark_patterns`, `superlative_patterns`, `forecast_exclude_patterns`, `forecast_verb_patterns`, `source_patterns`, `assumption_patterns`, `short_period_patterns`, `five_year_patterns`, `inception_patterns`, `fee_patterns`, `foreign_currency_patterns`, `currency_warning_patterns`, `forecast_patterns`, `forecast_weak_patterns`, `performance_patterns`, `forecast_disclaimer_patterns`, `tax_patterns`, `tax_exclude_patterns`, `tax_individual_patterns`, `tax_change_patterns`, `tax_context_patterns`.

### 10. LLM blocks and the seam

R11, R12a and R15 get `llm: {when: uncertain, question: …}`. They use the default `ask_llm` from `analytics-llm-p0` design §1, which asks the LLM when the rules-only result is `uncertain`, so these rules need no override. A deterministic `fail` or `pass` is never deferred, so the injection surface stays as small as stage 2 set it.

On the base branch the loader already parses `llm:` blocks, so groups 1-6 work without the judge. Group 7 adds `FakeJudge` tests for the merge and needs `analytics-llm-p0` group 8. If that group never lands, the blocks are inert, the rules-only `uncertain` stands, and the catalogue scenario is still true.

### 11. Dictionaries

The spec requirements stay under the OpenSpec 2.1.1 limit of 500 characters, so the starting dictionaries live here. Implementation writes them into `m2_rules.yaml`, which is the source of truth from then on. `…` stands for `\w*`, and every gap is bounded (decision 8).

- **R11 comparisons (`comparison_patterns`):**
  - a comparative followed by `niż` within 3 words: `lepsz…`, `wyższ…`, `niższ…`, `tańsz…`, `korzystniejsz…`, `więcej`, `better/higher/lower/cheaper than`;
  - `w porównaniu z/do`, `vs`, `versus`, `N razy więcej`, `bije … (lokaty|konkurencję|rynek)`, `outperform…`, `compared to/with`.
- **R11 benchmarks (`benchmark_patterns`):** `WIG20`, `WIG`, `indeks…`, `benchmark…`, `średni… funduszy`, `pobił/pokonał <index>`.
- **R11 excludes (`comparison_exclude_patterns`):** `niż rok temu`, `niż wcześniej`, `niż kiedykolwiek`, `niż inflacja`, `w porównaniu z inflacją`.
- **R11 superlatives (`superlative_patterns`):** `najlepsz…`, `najtańsz…`, `najwyższ… oprocentowanie`, `nr 1`, `numer 1`, `best`, `cheapest`.
- **Source (`&source_markers`, shared by R11 and R12a):** `źródło`, `według danych`, `wg danych`, `na podstawie danych`, `dane z/za`, `source`, `data from`.
- **R11 assumptions (`assumption_patterns`):** `przy założeniu`, `zakładając`, `założeni…`, `dla kwoty`, `w okresie`, `na dzień`, `stan na`, `assuming`, `as of`.
- **R12a sub-12-month periods (`short_period_patterns`):** `w ostatnim miesiącu`, `N miesięcy` with N not a multiple of 12 (checked in code), `od początku roku`, `YTD`, `w I…IV kwartale`, a month name, `tygodni…`, `dzienn…`.
- **R12a 5-year coverage (`five_year_patterns`):** `ostatnich/minionych N lat` with N ≥ 5, `5-letn…`, `pięcioletn…`, `5-year`. In code: a year range of 5 or more calendar years, or 5 or more distinct past years.
- **R12a since inception (`inception_patterns`):** `od początku działalności`, `od uruchomienia`, `od powstania`, `since inception`.
- **R12a reference period:** a year (`_YEAR`), a year range, a date, `ostatnich N lat/miesięcy`, searched in the past-performance sentences only.
- **R12a evidence:**
  - `fail` quotes the sub-12-month sentence, or else the first past-performance sentence;
  - `uncertain` quotes the since-inception sentence;
  - `pass` quotes the first past-performance sentence.
- **R12b fees (`fee_patterns`):** `po potrąceniu/odliczeniu/uwzględnieniu … opłat/prowizji/kosztów`, `nie uwzględnia… opłat/prowizji`, `wyniki netto/brutto`, `opłaty … obniżają/pomniejszają`, `net of fees`, `before/after/excluding fees`.
- **R12b foreign currency (`foreign_currency_patterns`):** `EUR`, `USD`, `CHF`, `GBP`, `€`, `$`, `w euro`, `w dolarach`, `denominowan… w`, `w walucie obcej`.
- **R12b currency warning (`currency_warning_patterns`):** `zmian/wahań kursów walut`, `ryzyko walutowe`, `currency fluctuations`, `exchange rate`.
- **R12b `pass`** quotes the first past-performance sentence.
- **R15 result vocabulary (`performance_patterns`):** `wynik…`, `zysk…`, `stopa zwrotu`, `zwrot…`, `rentown…`, `dochód`, `wzrost…`, a percentage that is not a fee or tax (`*return_figure_exclude`), `return`, `performance`, `growth`.
- **R15 strong markers (`forecast_patterns`):** `prognoz…`, `spodziewa…`, `oczekuj…`, `przewidu…`, `szacuj…`, `w przyszłym/kolejnym/następnym roku`, `cel… zwrotu`, `expect…`, `forecast…`, `projected`, `target return`. In code: a year after `fetched_at`.
- **R15 future-tense verbs (`forecast_verb_patterns`, strong together with a figure):** `zarobisz`, `zyskasz`, `zarobimy`, `przyniesie`, `wypracuje`, `osiągnie`.
- **R15 weak markers (`forecast_weak_patterns`):** `będzie`, `będą`, `może przynieść/osiągnąć`, `will`.
- **R15 imperatives (`forecast_exclude_patterns`):** `zarabiaj`, `zyskaj`, `pomnażaj`, `earn`.
- **R15 warning (`&forecast_disclaimers`):**
  - `prognoz… … nie jest/są/stanowi… … wiarygodn…/gwarancj…`;
  - `przyszłe wyniki … mogą się różnić / nie są gwarantowane`;
  - `nie ma gwarancji osiągnięcia … prognoz…/zakładanych wyników`;
  - `forecasts/projections are not a reliable indicator`.
- **R16 tax reference (`tax_patterns`):** `podat…`, `opodatkowan…`, `IKE`, `IKZE`, `Belk…`, `ulga podatkowa`, `zwolnieni… z podatku`, `odliczeni… od dochodu/podatku`, `PIT`, `tax…`.
- **R16 tax excludes (`tax_exclude_patterns`):** `VAT`, `podatek od towarów i usług`.
- **R16 individual part (`tax_individual_patterns`):** `zależy/uzależnion… od indywidualnej/osobistej sytuacji`, `individual circumstances`.
- **R16 change part (`tax_change_patterns`):** `może/mogą ulec zmianie / się zmienić`, `subject to change`, `may change`.
- **R16 tax context (`tax_context_patterns`):** tax words and `przepis…`.

## Risks / Trade-offs

- **Lexical source and assumption detection is lenient.** `Źródło: opracowanie własne` passes the source check, and "w okresie" anywhere counts as assumptions. → The gold set calibrates this. Missing assumptions alone give `uncertain`, not `pass`.
- **A rules-only `uncertain` raises the score**, by half a fail, for superlatives (R11), dated since-inception periods (R12a) and weak forecasts (R15). → With the LLM on, it resolves them. With it off, the cases are visible and honest, and for unsourced superlatives the lean toward `fail` is what Damian asked for (answer 5).
- **R12a can fail on pages that are legal but terse.** For example, a fund page that gives 5 years in a table the scraper flattens without years. → The text fallback with distinct years covers flattened tables. The rest is gold-set work.
- **Results differ from the mocks.** `eurotrade` gets R12a and R12b `fail` (absent in the mock) and R15 with `method: rule` instead of `llm`. `m2-bank-ok` gets R16 `pass`. The mocks are never edited; the differences are in `follow-ups.md`.
- **Merge order.** This change modifies the "Rule catalogue" requirement, which `analytics-llm-p0` also modifies. This change's delta restates the post-stage-2 text, so it must be archived after `analytics-llm-p0`. When rebasing onto `main`, re-read the main spec and re-check the delta's full text.
- **`re._parser` is private.** → See decision 8. The fallback and the test make a break loud.

## Cut plan

The total is about 7.5 h of agent work plus closing. If time runs short, cut in this order. The first items cut are the cheapest to lose:

1. **Group 7** (LLM blocks tested against the judge). The rules-only results stand.
2. **Group 6** (R11). It has the weakest lexical signal and the most `uncertain` results. Without the LLM it adds noise.
3. **The benchmark extension and the superlative tier of R11.** Keep the explicit comparisons with products, services and providers.
4. **The since-inception branch of R12a.** Without a date it still fails `okres referencyjny`. With a date it is treated as `uncertain` through the plain "no 5-year coverage" path, and a follow-up is recorded.

Never cut group 1 (the ReDoS guard). Every later group adds patterns that it protects.

## Resolved questions

The general principles were settled by the brief and the stage-2 answers:
- Each rule is `not_applicable` without its trigger, and a violation is counted once, by the owner of the element (decision 1, ADR 0315).
- R9 is not built here: there is no cheap rules signal, so it waits for an LLM-first change. R13 is not built here: it needs `blocks` (#29).
- The mocks are not edited. The differences go to `follow-ups.md`.

The six product questions were answered by Damian on 2026-11-21 and relayed by the coordinating session, which checked them against the exact ZASÓB wording. Damian also set this change as the lowest priority of stage 3. Implementation starts only after `analytics-llm-p0` groups 5-12, on the coordinator's go.

1. **R12b currency.** The warning is conditional on non-PLN figures (art. 44 ust. 4 lit. e), and the explanation and this design cite that article, because ZASÓB states no condition. The fees and charges check always applies when past performance is shown (decision 5).
2. **R15 imperatives.** `Zarabiaj nawet do 18% rocznie` is not a forecast: it is R3's return claim. A figure tied to a future period (`w 2026 zarobisz…`, `w przyszłym roku spodziewamy się…`) is a forecast, and a detected forecast is always reported (decisions 2 and 6).
3. **R11 reporting.** "Flaguje naruszenia w raporcie" means violations only. A compliant comparison is a plain `pass` that stores the quoted comparison as evidence, without a flag (decision 2).
4. **R11 scope.** The core is other products, services and providers. Index and benchmark comparisons are included as an extension. Inflation is out (decision 3).
5. **R11 superlatives.** An unsourced superlative leans toward `fail`. Rules-only it is `uncertain`, with the missing source named as the reason, and the LLM may confirm it is a comparison (decision 3).
6. **R12a since inception.** It is modelled as named sub-checks. "Od początku działalności" without dates fails `okres referencyjny` outright, and only the 5-year / 12-month sub-check can be `uncertain` (decision 4).

## Open Questions

None. All product questions are resolved above.
