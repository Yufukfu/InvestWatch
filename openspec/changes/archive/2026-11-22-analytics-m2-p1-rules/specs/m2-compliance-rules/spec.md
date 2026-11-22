## MODIFIED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, the legal basis that ZASÓB gives it, its dictionaries, an `implemented` flag and an optional `llm:` block (see `llm-analysis`). Only implemented rules SHALL run. Shared dictionaries MAY be written once with YAML anchors.

#### Scenario: Catalogue is complete
- **WHEN** the catalogue is loaded
- **THEN** it holds 19 entries whose ids match the contract `rule_id` pattern, and exactly R1, R2, R3, R4, R6, R11, R12a, R12b, R14, R15, R16, R17 and R18 are implemented

#### Scenario: LLM-refined rules declare it
- **WHEN** the catalogue is loaded
- **THEN** R3, R11, R12a, R15, R17 and R18 have an `llm:` block and no other M2 entry has one

#### Scenario: Legal basis from ZASÓB
- **WHEN** the catalogue is loaded
- **THEN** every entry has a non-null `legal_basis`, and R11, R12a, R12b, R15 and R16 name art. 44 ust. 3, ust. 4, ust. 4, ust. 6 and ust. 7 of Delegated Regulation 2017/565

#### Scenario: Malformed catalogue
- **WHEN** an entry has an unknown severity or a duplicate id
- **THEN** loading fails with an error naming the entry

#### Scenario: Bad rule parameter
- **WHEN** `negation_before` is not a valid regex, or `prominent_sentences` is not an integer, or `min_ratio` is 0 or above 1, or the root is a list
- **THEN** loading fails with a catalogue error naming the rule or the file

#### Scenario: Shared dictionaries
- **WHEN** a dictionary is written once with a YAML anchor (for example the risk-warning patterns of R3, or the past-performance lists of R12a, R12b and R14 under `shared:`) and reused by other rules through an alias
- **THEN** every rule that uses the alias sees the same list, and a top-level key other than `rules` (such as `shared:`) is never read as a rule

## ADDED Requirements

### Requirement: Catalogue parameters are validated at load
Loading SHALL validate every rule parameter that the rules read:
- pattern lists and `negation_before` compile;
- `window`, `prominent_sentences` and `borderline_margin` are non-negative integers;
- `min_ratio` is a number in (0, 1];
- `labels`, `footnote_markers` and `hiding_regions` are lists of strings, and `labels` is non-empty.

Unknown keys SHALL be rejected and the YAML root SHALL be a mapping, so a bad catalogue fails at load, never on a document.

#### Scenario: Unknown parameter key
- **WHEN** R16's params contain `tax_patern` (a typo)
- **THEN** loading fails with a catalogue error naming R16 and the key

#### Scenario: Non-list pattern parameter
- **WHEN** R11's `comparison_patterns` is a string, not a list
- **THEN** loading fails with a catalogue error naming R11 and `comparison_patterns`

### Requirement: Catalogue patterns are ReDoS-safe
Loading SHALL reject any pattern that nests an unbounded repetition inside another unbounded repetition, such as `(\w+\s*)+` or `(?:a*)*`, naming the rule and the parameter. The patterns run on untrusted scraped text, and nested repetition can backtrack exponentially. Gaps between words SHALL use bounded forms such as `.{0,80}?` or `(?:\w+\s+){0,3}`.

#### Scenario: Pattern with nested unbounded repetition
- **WHEN** a rule's `comparison_patterns` contains `(\w+\s*)+niż`
- **THEN** loading fails with a catalogue error naming the rule and `comparison_patterns`

#### Scenario: Bounded gaps are accepted
- **WHEN** a pattern uses `(?:\w+\s+){0,3}` or `.{0,80}?`
- **THEN** loading accepts it

#### Scenario: Patterns stay fast on adversarial text
- **WHEN** every catalogue pattern and every module-level regex in `rules/m2.py` is searched in 20 000 characters of adversarial input (a repeated word and space, repeated `%`, repeated `niż `, one unbroken word)
- **THEN** each search finishes within 0.2 s

### Requirement: A detected forecast is always reported
ZASÓB R15 says "Flaguje w raporcie wykrycie prognozy przyszłych wyników". So a compliant R15 `pass` SHALL quote the detected forecast as `evidence`, and its Polish explanation SHALL start with `Wykryto prognozę` and name the warning that made it compliant. Without a forecast, R15 SHALL be `not_applicable` with null evidence.

#### Scenario: Compliant forecast is still reported
- **WHEN** a material contains a forecast and the forecast warning
- **THEN** R15 is `pass`, its `evidence` is the forecast sentence, and the explanation starts with `Wykryto prognozę`

### Requirement: A compliant comparison is a plain pass
ZASÓB R11 says "flaguje naruszenia w raporcie", which covers violations only. A compliant comparison SHALL be a plain `pass` that quotes the comparison as `evidence`. Its explanation SHALL NOT start with `Wykryto` and SHALL NOT present the comparison as a flag.

#### Scenario: Compliant comparison is a plain pass
- **WHEN** a material contains a comparison with a source and the assumptions
- **THEN** R11 is `pass`, its `evidence` is the comparison sentence, and the explanation does not start with `Wykryto`

### Requirement: Past performance is detected once
R12a, R12b and R14 SHALL share R14's past-performance detector. Without a past-performance sentence, all three SHALL be `not_applicable` with `Materiał nie prezentuje wyników historycznych.`

Each SHALL check only its own element of art. 44 ust. 4:
- R12a: period, 12-month basis, reference period, source;
- R12b: currency and costs;
- R14: the disclaimer;
- R13, once built: prominence.

#### Scenario: No past performance
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R12a, R12b and R14 are `not_applicable` with the same explanation

#### Scenario: A missing disclaimer fails only R14
- **WHEN** the past performance is given for 5 full years, with a source and a fee statement, and with no disclaimer
- **THEN** R14 is `fail`, and R12a and R12b are `pass`

#### Scenario: Forecast is not past performance
- **WHEN** the only figure is in `W 2026 roku spodziewamy się 10% zysku.` and `fetched_at` is in 2026
- **THEN** R12a, R12b and R14 are `not_applicable`

### Requirement: R11 comparison detection
R11 SHALL detect comparisons with other products, services or providers (ZASÓB R11 "porównania produktów i usług", art. 44 ust. 3), using `comparison_patterns`, plus comparisons with an index or benchmark (`benchmark_patterns`) as an extension. Temporal and inflation comparisons SHALL be excluded (`niż rok temu`, `niż inflacja`). A superlative without a comparator (`najlepsz…`, `nr 1`) SHALL count as an implicit comparison. The dictionaries are listed in design §11.

#### Scenario: Temporal comparison is not a product comparison
- **WHEN** the only comparative is `Zyski są wyższe niż rok temu.`
- **THEN** R11 is `not_applicable`

#### Scenario: Inflation is out of scope
- **WHEN** the only comparative is `Zysk wyższy niż inflacja.`
- **THEN** R11 is `not_applicable`

#### Scenario: Rival provider comparison
- **WHEN** the text is `Prowizje niższe niż w innych biurach maklerskich.` with no source
- **THEN** R11 is `fail` with that sentence as evidence

#### Scenario: Benchmark comparison is included
- **WHEN** the text is `Fundusz pobił WIG20 o 5 pkt proc.` or `lepszy niż benchmark`, with no source
- **THEN** R11 is `fail`

#### Scenario: No comparison
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R11 is `not_applicable` with null evidence

#### Scenario: Empty or unsegmentable text
- **WHEN** the document text is empty or has no sentence boundary
- **THEN** R11 is `not_applicable` and no exception is raised

### Requirement: R11 source and assumptions
ZASÓB R11 "weryfikuje źródło informacji, przyjęte założenia"; markers count anywhere. R11 SHALL be:
- `fail`, quoting the first comparison, without a source;
- `uncertain` with a source but no assumptions;
- `uncertain` for an unsourced superlative only, quoting it and naming the missing source;
- a plain `pass` with both.

Its `llm:` block (`when: uncertain`) SHALL ask whether it is a comparison and whether the source and assumptions are stated.

#### Scenario: Comparison without a source
- **WHEN** the text is `Nasze konto daje 3 razy więcej niż lokata w banku.` and nothing else names a source
- **THEN** R11 is `fail` with that sentence as evidence

#### Scenario: Comparison with source and assumptions
- **WHEN** `Fundusz A przyniósł więcej niż średnia funduszy akcji.` is followed by `Źródło: dane Analizy.pl, stan na 30.09.2026.`
- **THEN** R11 is `pass` with the comparison as evidence

#### Scenario: Source without assumptions
- **WHEN** the comparison is followed only by `Źródło: opracowanie własne.`
- **THEN** R11 is `uncertain`

#### Scenario: Superlative only
- **WHEN** the only trigger is `Najlepsze konto maklerskie na rynku!` with no source
- **THEN** R11 is `uncertain` with that sentence as evidence, and the explanation names the missing source

### Requirement: R12a named sub-checks
R12a (ZASÓB: "okres ostatnich 5 lat … pełne okresy 12-miesięczne … okres referencyjny i źródło", art. 44 ust. 4) SHALL evaluate three named sub-checks on the past-performance sentences, each `pass`, `fail` or `uncertain`: `5 lat / 12 mies.`, `okres referencyjny` and `źródło`. The result SHALL be the worst sub-check (`fail` > `uncertain` > `pass`). The Polish explanation SHALL name every sub-check that is not `pass`, with its status, in that order.

#### Scenario: One year, no source
- **WHEN** the `eurotrade` mock is analyzed (`Nasi klienci zarobili średnio 34% w 2025 roku.`)
- **THEN** R12a is `fail` with that sentence as evidence, the explanation names the 5-year sub-check and `źródło` as failed, and `okres referencyjny` (2025) is not named

#### Scenario: Five years with source
- **WHEN** `W latach 2021–2025 fundusz wypracował średnio 7% rocznie.` is followed by `Źródło: dane własne TFI.`
- **THEN** R12a is `pass`

#### Scenario: No past performance
- **WHEN** the `m2-alfa-landing` mock is analyzed
- **THEN** R12a is `not_applicable`

### Requirement: R12a 5-year and 12-month sub-check
The `5 lat / 12 mies.` sub-check SHALL:
- fail when a past-performance sentence uses a period shorter than 12 months;
- pass with 5 or more years of coverage (a range, `ostatnich N lat`, distinct years);
- on a since-inception marker alone (art. 44 ust. 4 lit. b), pass if the launch year is under 5 years before the fetch year, fail if over, and be `uncertain` at exactly 5 or with no year;
- fail otherwise.

#### Scenario: Period shorter than 12 months
- **WHEN** the material also says `Od początku roku fundusz zyskał 9%.`, next to a 5-year figure with a source
- **THEN** R12a is `fail` quoting `Od początku roku fundusz zyskał 9%.`

#### Scenario: Twelve months is a full period
- **WHEN** a past-performance sentence says `w ostatnich 12 miesiącach` and 5-year figures with a source are also given
- **THEN** the 12-month basis is met and R12a is `pass`

#### Scenario: Since inception with a start year
- **WHEN** the only past performance is `Od uruchomienia w 2021 r. fundusz zarobił 18%.`, with a source, fetched in 2026
- **THEN** R12a is `uncertain` with that sentence as evidence, and the explanation names only the 5-year sub-check

#### Scenario: Since inception of a young or an old product
- **WHEN** the launch year is 2023, or 2019, and the material was fetched in 2026
- **THEN** the 5-year sub-check is `pass` for 2023 and `fail` for 2019, quoting the since-inception sentence

### Requirement: R12a reference period and source sub-checks
`okres referencyjny` SHALL pass when a year, a year range, a date or `ostatnich N lat/miesięcy` is in a past-performance sentence, and fail otherwise. A since-inception marker without a date SHALL fail it outright. `źródło` SHALL pass when a source marker (shared with R11) appears anywhere. The `llm:` block (`when: uncertain`) SHALL ask whether the product is under 5 years old.

#### Scenario: No reference period
- **WHEN** the only past-performance sentence is `Nasi klienci zarobili 34%.`
- **THEN** R12a is `fail` and the explanation names the missing reference period

#### Scenario: Since inception without a date
- **WHEN** the only past performance is `Od początku działalności fundusz zarobił 18%.`, with a source
- **THEN** R12a is `fail`, and the explanation names `okres referencyjny` as failed and the 5-year sub-check as `uncertain`

### Requirement: R12b costs
ZASÓB R12b asks "czy wskazano wpływ prowizji, opłat i obciążeń na wyniki" (art. 44 ust. 4). Whenever past performance is shown, R12b SHALL require a fee-impact statement anywhere in the material (`po potrąceniu opłat`, `nie uwzględniają prowizji`, `wyniki netto`, `net of fees`). Without one it SHALL `fail`, quoting the first past-performance sentence. R12b is rules-only.

#### Scenario: No fee statement
- **WHEN** the `eurotrade` mock is analyzed
- **THEN** R12b is `fail`, the explanation names the missing statement on fees and commissions as the only missing part, and it says the currency warning was not required for PLN results under art. 44 ust. 4 lit. e

#### Scenario: Fee statement, PLN figures
- **WHEN** the past performance is `Fundusz zarobił 8% w 2025 r.` and the material says `Wyniki uwzględniają opłatę za zarządzanie.`
- **THEN** R12b is `pass`

#### Scenario: No past performance
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R12b is `not_applicable`

### Requirement: R12b currency warning
ZASÓB requires a currency warning without a condition. R12b SHALL require it only when a past result is in a currency other than PLN, or the product is denominated in one (art. 44 ust. 4 lit. e). Without the warning it SHALL `fail`, quoting the foreign-currency sentence. Every R12b explanation SHALL cite `art. 44 ust. 4 lit. e` and, for PLN results, say the warning was not required.

#### Scenario: Foreign currency without a warning
- **WHEN** the past performance is `Subfundusz USD zyskał 11% w 2025 r.`, with a fee statement and without a currency warning
- **THEN** R12b is `fail` quoting that sentence, and the explanation names the missing currency warning

#### Scenario: Foreign currency with a warning
- **WHEN** the same material adds `Zmiany kursów walut mogą zwiększyć lub zmniejszyć wynik.`
- **THEN** R12b is `pass`

### Requirement: R15 forecast detection
R15 SHALL treat a sentence as a forecast when it has result vocabulary and either:
- a strong marker (`prognoz…`, `spodziewa…`, `w przyszłym roku`, a year after `fetched_at`, or a future-tense return verb with a figure, such as `W 2026 zarobisz 12%`); or
- a weak marker (`będzie`, `will`) with a figure.

An imperative return promise (`zarabiaj`, `zyskaj`) is not a forecast; it is R3's claim. Forecast-warning sentences SHALL NOT count.

#### Scenario: Figure tied to a future period
- **WHEN** the text is `W 2026 zarobisz nawet 12%.`, `fetched_at` is in 2026, and there is no forecast warning
- **THEN** R15 is `fail` with that sentence as evidence

#### Scenario: Weak marker with a figure
- **WHEN** the text is `Fundusz będzie zarabiał 12% rocznie.` with no warning
- **THEN** R15 is `fail`

#### Scenario: Promotional imperative is not a forecast
- **WHEN** the `m2-alfa-landing` mock is analyzed (`Zarabiaj nawet do 18% rocznie…`)
- **THEN** R15 is `not_applicable`, and the missing risk warning stays R3's

#### Scenario: Warning sentence is not a forecast
- **WHEN** the only sentence is `Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników.`
- **THEN** R15 is `not_applicable`

### Requirement: R15 forecast warning
ZASÓB R15 requires a clear warning that a forecast is not a reliable indicator of future results (art. 44 ust. 6). R15 SHALL be:
- `fail`, quoting the first forecast, when there is no warning;
- `uncertain` when the only candidates are weak-marker sentences without a figure;
- `pass` when a warning exists.

The R14 past-performance disclaimer alone SHALL NOT count. The `llm:` block (`when: uncertain`) SHALL ask whether the sentence forecasts results.

#### Scenario: Forecast without a warning
- **WHEN** the `eurotrade` mock is analyzed (`W przyszłym roku spodziewamy się jeszcze lepszych wyników.`)
- **THEN** R15 is `fail` with that sentence as evidence

#### Scenario: Forecast with a warning
- **WHEN** `Prognozujemy stopę zwrotu 6% w 2027 roku.` is followed by `Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników.`
- **THEN** R15 is `pass` with the forecast sentence as evidence

#### Scenario: Weak marker without a figure
- **WHEN** the only candidate is `Wyniki będą zależeć od sytuacji rynkowej.` with no warning
- **THEN** R15 is `uncertain`

#### Scenario: Past-performance disclaimer does not cover a forecast
- **WHEN** a forecast is followed only by `Wyniki historyczne nie są gwarancją przyszłych wyników.`
- **THEN** R15 is `fail`

### Requirement: R16 tax reference
R16 (ZASÓB, art. 44 ust. 7) SHALL apply when the material refers to tax treatment (`podat…`, `IKE`, `IKZE`, `Belk…`, `zwolnieni… z podatku`, `tax…`). VAT mentions and the disclaimer sentence itself SHALL NOT count as a tax reference. Without a tax reference R16 SHALL be `not_applicable` with null evidence.

#### Scenario: VAT is not tax treatment
- **WHEN** the only tax word is in `Cena zawiera podatek VAT.`
- **THEN** R16 is `not_applicable`

#### Scenario: No tax reference
- **WHEN** the `eurotrade` mock is analyzed
- **THEN** R16 is `not_applicable` with null evidence

### Requirement: R16 tax disclaimer
R16 SHALL require both parts: the treatment depends on the client's individual situation, and it may change. The change part counts only in the same sentence as the individual part, or in a sentence that mentions tax or `przepis…`. R16 SHALL `pass` with both, quoting the individual part's sentence. Otherwise it SHALL `fail`, quoting the partial disclaimer or the first tax reference, and naming each missing part. R16 is rules-only.

#### Scenario: IKE with the full disclaimer
- **WHEN** the `m2-bank-ok` mock is analyzed (`Otwórz IKE…`, `Traktowanie podatkowe zależy od indywidualnej sytuacji klienta i może ulec zmianie.`)
- **THEN** R16 is `pass` with the disclaimer sentence as evidence

#### Scenario: Tax benefit without a disclaimer
- **WHEN** the text is `Inwestuj bez podatku Belki w IKZE!` and nothing else
- **THEN** R16 is `fail` with that sentence as evidence

#### Scenario: Only the individual part
- **WHEN** the disclaimer is only `Korzyść podatkowa zależy od indywidualnej sytuacji klienta.`
- **THEN** R16 is `fail` and the explanation names the missing possibility of change

#### Scenario: Unrelated change sentence
- **WHEN** the individual part is present and the only change sentence is `Oferta może ulec zmianie.`
- **THEN** R16 is `fail`
