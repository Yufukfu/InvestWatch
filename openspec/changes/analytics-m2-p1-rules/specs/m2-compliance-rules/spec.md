## MODIFIED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, a legal basis, its dictionaries, an `implemented` flag and an optional `llm:` block (see the `llm-analysis` capability). Every entry SHALL carry the legal basis that ZASÓB gives the rule. Only implemented rules SHALL run.

Loading SHALL validate every rule parameter that the rules read:
- pattern lists and `negation_before` compile;
- `window`, `prominent_sentences` and `borderline_margin` are non-negative integers;
- `min_ratio` is a number in (0, 1];
- `labels`, `footnote_markers` and `hiding_regions` are lists of strings, and `labels` SHALL be non-empty.

Unknown parameter keys SHALL be rejected, and the YAML root SHALL be a mapping, so that a bad catalogue fails at load and never on the first document.

Loading SHALL also reject any pattern that nests an unbounded repetition inside another unbounded repetition, for example `(\w+\s*)+` or `(?:a*)*`, naming the rule and the parameter. Such patterns can backtrack exponentially (ReDoS), and the patterns run on untrusted scraped text. Gaps between words SHALL be written with bounded forms such as `.{0,80}?` or `(?:\w+\s+){0,3}`.

Shared dictionaries MAY be written once with YAML anchors and reused by several rules.

#### Scenario: Catalogue is complete
- **WHEN** the catalogue is loaded
- **THEN** it holds 19 entries whose ids match the contract `rule_id` pattern, and exactly R1, R2, R3, R4, R6, R10, R11, R12a, R12b, R14, R15, R16, R17 and R18 are implemented

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

#### Scenario: Pattern with nested unbounded repetition
- **WHEN** a rule's `comparison_patterns` contains `(\w+\s*)+niż`
- **THEN** loading fails with a catalogue error naming the rule and `comparison_patterns`

#### Scenario: Bounded gaps are accepted
- **WHEN** a pattern uses `(?:\w+\s+){0,3}` or `.{0,80}?`
- **THEN** loading accepts it

#### Scenario: Patterns stay fast on adversarial text
- **WHEN** every catalogue pattern and every module-level regex in `rules/m2.py` is searched in 20 000 characters of adversarial input (a repeated word and space, repeated `%`, repeated `niż `, one unbroken word)
- **THEN** each search finishes within 0.2 s

## ADDED Requirements

### Requirement: Detection rules report a compliant detection
Some rules check content only when it is present. For these rules, R11 and R15, ZASÓB says the detection is flagged in the report. For these rules, a `pass` SHALL quote the detected content (the comparison or the forecast) as `evidence`. The Polish explanation SHALL say what was detected and what made it compliant. A `pass` adds no violation to the score. Without the detected content, the rule SHALL be `not_applicable` and its `evidence` SHALL be null.

#### Scenario: Compliant forecast is still reported
- **WHEN** a material contains a forecast and the forecast warning
- **THEN** R15 is `pass`, its `evidence` is the forecast sentence, and the explanation starts with `Wykryto prognozę`

#### Scenario: Compliant comparison is still reported
- **WHEN** a material contains a comparison with a source and the assumptions
- **THEN** R11 is `pass`, its `evidence` is the comparison sentence, and the explanation starts with `Wykryto porównanie`

### Requirement: Past performance is detected once
R12a, R12b and R14 SHALL use one past-performance detector: R14's definition of a past-performance sentence (see the R14 requirement). When the detector finds no such sentence, all three SHALL be `not_applicable` with `Materiał nie prezentuje wyników historycznych.`

Each of these rules SHALL check only its own element of art. 44 ust. 4:
- R12a checks the period, the 12-month basis, the reference period and the source.
- R12b checks currency and costs.
- R14 checks the disclaimer.
- R13 checks prominence, once it is built.

None of them SHALL check an element that another of them owns.

#### Scenario: No past performance
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R12a, R12b and R14 are `not_applicable` with the same explanation

#### Scenario: A missing disclaimer fails only R14
- **WHEN** the past performance is given for 5 full years, with a source and a fee statement, and with no disclaimer
- **THEN** R14 is `fail`, and R12a and R12b are `pass`

#### Scenario: Forecast is not past performance
- **WHEN** the only figure is in `W 2026 roku spodziewamy się 10% zysku.` and `fetched_at` is in 2026
- **THEN** R12a, R12b and R14 are `not_applicable`

### Requirement: R11 product comparisons
R11 SHALL detect comparisons of products and services and check that the source of the information and the assumptions are given (ZASÓB R11, art. 44 ust. 3).

A comparison sentence is either of these:
- A comparative followed by `niż` within 3 words: `lepsz…`, `wyższ…`, `niższ…`, `tańsz…`, `korzystniejsz…`, `więcej` or `better/higher/lower/cheaper than`.
- One of these markers: `w porównaniu z/do`, `vs`, `versus`, `N razy więcej`, `bije … (lokaty|konkurencję|rynek|indeks)`, `outperform…`, `compared to/with`.

A temporal or inflation comparison is excluded, because it compares no product or service: `niż rok temu`, `niż wcześniej`, `niż kiedykolwiek`, `niż inflacja`.

A superlative without a comparator, such as `najlepsz…`, `najtańsz…`, `najwyższ… oprocentowanie`, `nr 1` or `best`, is an implicit comparison.

A source is a marker anywhere in the material: `źródło`, `według danych`, `wg danych`, `na podstawie danych`, `dane z/za`, `source`, `data from`. Assumptions are a marker anywhere: `przy założeniu`, `zakładając`, `założeni…`, `dla kwoty`, `w okresie`, `na dzień`, `stan na`, `assuming`, `as of`.

R11 SHALL produce:
- `not_applicable` without any comparison or superlative;
- `fail`, quoting the first comparison, when a comparison has no source;
- `uncertain`, quoting the comparison, when a source is given but no assumptions;
- `uncertain`, quoting the superlative, when the only trigger is a superlative without a source;
- `pass`, quoting the first comparison (see "Detection rules report a compliant detection"), when a source and assumptions are given.

Its `llm:` block (`when: uncertain`) SHALL ask whether the material compares products or services and whether it states the source and the key assumptions.

#### Scenario: Comparison without a source
- **WHEN** the text is `Nasze konto daje 3 razy więcej niż lokata w banku.` and nothing else names a source
- **THEN** R11 is `fail` with that sentence as evidence

#### Scenario: Comparison with source and assumptions
- **WHEN** `Fundusz A przyniósł więcej niż średnia funduszy akcji.` is followed by `Źródło: dane Analizy.pl, stan na 30.09.2026.`
- **THEN** R11 is `pass` with the comparison as evidence

#### Scenario: Source without assumptions
- **WHEN** the comparison is followed only by `Źródło: opracowanie własne.`
- **THEN** R11 is `uncertain`

#### Scenario: Temporal comparison is not a product comparison
- **WHEN** the only comparative is `Zyski są wyższe niż rok temu.`
- **THEN** R11 is `not_applicable`

#### Scenario: Superlative only
- **WHEN** the only trigger is `Najlepsze konto maklerskie na rynku!` with no source
- **THEN** R11 is `uncertain` with that sentence as evidence

#### Scenario: No comparison
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R11 is `not_applicable` with null evidence

#### Scenario: Empty or unsegmentable text
- **WHEN** the document text is empty or has no sentence boundary
- **THEN** R11 is `not_applicable` and no exception is raised

### Requirement: R12a past performance, period and scope
ZASÓB R12a checks that the past performance covers the last 5 years and is based on full 12-month periods, and that the reference period and the source are given (art. 44 ust. 4). R12a SHALL apply to the past-performance sentences from the shared detector.

It SHALL check four elements:
- **12-month basis.** No past-performance sentence uses a period shorter than 12 months. Such periods are `w ostatnim miesiącu`, `w N miesiącach` with N not a multiple of 12, `od początku roku`, `YTD`, `w I…IV kwartale`, a month name, `tygodni…` and `dzienn…`.
- **5-year coverage.** One of these is given: `ostatnich/minionych 5 (or more) lat`, `5-letn…`, `pięcioletn…`, `5-year`, a year range spanning 5 or more calendar years, or past figures for 5 or more distinct years.
- **Reference period.** A year, a year range, a date or `ostatnich N lat/miesięcy` appears in a past-performance sentence.
- **Source.** The same source markers as R11 appear anywhere in the material.

R12a SHALL produce:
- `fail`, quoting the first offending past-performance sentence, when any element is missing. The Polish explanation lists every missing element.
- `uncertain`, when coverage rests only on a since-inception marker (`od początku działalności`, `od uruchomienia`, `od powstania`, `since inception`) and the other elements are met. Art. 44 ust. 4 lit. b allows a shorter period only for a product younger than 5 years, which the rules cannot verify.
- `pass` otherwise, quoting the first past-performance sentence.

Its `llm:` block (`when: uncertain`) SHALL ask whether the material states that the product has existed for less than 5 years.

#### Scenario: One year, no source
- **WHEN** the `eurotrade` mock is analyzed (`Nasi klienci zarobili średnio 34% w 2025 roku.`)
- **THEN** R12a is `fail` with that sentence as evidence, and the explanation names the missing 5-year coverage and the missing source

#### Scenario: Five years with source
- **WHEN** `W latach 2021–2025 fundusz wypracował średnio 7% rocznie.` is followed by `Źródło: dane własne TFI.`
- **THEN** R12a is `pass`

#### Scenario: Period shorter than 12 months
- **WHEN** the material also says `Od początku roku fundusz zyskał 9%.`, next to a 5-year figure with a source
- **THEN** R12a is `fail` quoting `Od początku roku fundusz zyskał 9%.`

#### Scenario: Twelve months is a full period
- **WHEN** a past-performance sentence says `w ostatnich 12 miesiącach` and 5-year figures with a source are also given
- **THEN** the 12-month basis is met and R12a is `pass`

#### Scenario: No reference period
- **WHEN** the only past-performance sentence is `Nasi klienci zarobili 34%.`
- **THEN** R12a is `fail` and the explanation names the missing reference period

#### Scenario: Since inception
- **WHEN** the only coverage is `Od początku działalności fundusz zarobił 18%.`, with a source
- **THEN** R12a is `uncertain` with that sentence as evidence

#### Scenario: No past performance
- **WHEN** the `m2-alfa-landing` mock is analyzed
- **THEN** R12a is `not_applicable`

### Requirement: R12b past performance, currency and costs
ZASÓB R12b checks that the material warns about the effect of exchange-rate changes and states how commissions, fees and charges affect the results (art. 44 ust. 4). R12b SHALL apply to the past-performance sentences from the shared detector.

It has two parts:
- **Costs.** This part always applies. It is met by a fee-impact statement anywhere in the material: `po potrąceniu/odliczeniu/uwzględnieniu … opłat/prowizji/kosztów`, `nie uwzględnia… opłat/prowizji`, `wyniki netto/brutto`, `opłaty … obniżają/pomniejszają`, `net of fees`, `before/after/excluding fees`.
- **Currency.** This part applies only when a past-performance sentence gives the result in a currency other than PLN (`EUR`, `USD`, `CHF`, `GBP`, `€`, `$`, `w euro`, `w dolarach`), or when the material says that the product is denominated in a foreign currency (`denominowan… w`, `w walucie obcej`). This follows art. 44 ust. 4 lit. e. It is met by a currency warning anywhere: `zmian/wahań kursów walut`, `ryzyko walutowe`, `currency fluctuations`, `exchange rate`.

R12b SHALL produce:
- `fail` when an applicable part is not met. The evidence quotes the first past-performance sentence, or, for a currency failure, the foreign-currency sentence. The Polish explanation names each missing part.
- `pass` otherwise, quoting the first past-performance sentence.

It is rules-only.

#### Scenario: No fee statement
- **WHEN** the `eurotrade` mock is analyzed
- **THEN** R12b is `fail` and the explanation names the missing statement on fees and commissions only

#### Scenario: Fee statement, PLN figures
- **WHEN** the past performance is `Fundusz zarobił 8% w 2025 r.` and the material says `Wyniki uwzględniają opłatę za zarządzanie.`
- **THEN** R12b is `pass`

#### Scenario: Foreign currency without a warning
- **WHEN** the past performance is `Subfundusz USD zyskał 11% w 2025 r.`, with a fee statement and without a currency warning
- **THEN** R12b is `fail` quoting that sentence, and the explanation names the missing currency warning

#### Scenario: Foreign currency with a warning
- **WHEN** the same material adds `Zmiany kursów walut mogą zwiększyć lub zmniejszyć wynik.`
- **THEN** R12b is `pass`

#### Scenario: No past performance
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R12b is `not_applicable`

### Requirement: R15 forecasts of future performance
R15 SHALL recognize forecasts, check for a clear warning that a forecast is not a reliable indicator of future results, and report every detected forecast (ZASÓB R15, art. 44 ust. 6).

A forecast sentence has result vocabulary together with a forecast marker:
- **Result vocabulary:** `wynik…`, `zysk…`, `stopa zwrotu`, `zwrot…`, `rentown…`, `dochód`, `wzrost…`, a percentage that is not a fee or tax (R3's exclude list), `return`, `performance`, `growth`.
- **Strong forecast marker:** `prognoz…`, `spodziewa…`, `oczekuj…`, `przewidu…`, `szacuj…`, `w przyszłym/kolejnym/następnym roku`, `cel… zwrotu`, `expect…`, `forecast…`, `projected`, `target return`, or a year later than the `fetched_at` year.
- **Weak forecast marker:** `będzie`, `będą`, `może przynieść/osiągnąć`, `will`.

Sentences that match the forecast warning itself SHALL never count as forecasts.

A forecast warning, anywhere in the material, is one of these:
- `prognoz… … nie jest/są/stanowi… … wiarygodn…/gwarancj…`;
- `przyszłe wyniki … mogą się różnić / nie są gwarantowane`;
- `nie ma gwarancji osiągnięcia … prognoz…/zakładanych wyników`;
- `forecasts/projections are not a reliable indicator`.

The R14 past-performance disclaimer alone SHALL NOT satisfy R15.

R15 SHALL produce:
- `not_applicable` without a forecast sentence;
- `fail`, quoting the first forecast sentence, when a strong-marker forecast exists and there is no warning;
- `uncertain`, quoting the first candidate, when only weak-marker sentences exist, all of them without a figure, and there is no warning;
- a fail (not `uncertain`) for a weak marker together with a figure, as in `Fundusz będzie zarabiał 12% rocznie.`;
- `pass`, quoting the first forecast sentence, when a warning exists (see "Detection rules report a compliant detection").

Its `llm:` block (`when: uncertain`) SHALL ask whether the sentence forecasts future results.

#### Scenario: Forecast without a warning
- **WHEN** the `eurotrade` mock is analyzed (`W przyszłym roku spodziewamy się jeszcze lepszych wyników.`)
- **THEN** R15 is `fail` with that sentence as evidence

#### Scenario: Forecast with a warning
- **WHEN** `Prognozujemy stopę zwrotu 6% w 2027 roku.` is followed by `Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników.`
- **THEN** R15 is `pass` with the forecast sentence as evidence

#### Scenario: Weak marker with a figure
- **WHEN** the text is `Fundusz będzie zarabiał 12% rocznie.` with no warning
- **THEN** R15 is `fail`

#### Scenario: Weak marker without a figure
- **WHEN** the only candidate is `Wyniki będą zależeć od sytuacji rynkowej.` with no warning
- **THEN** R15 is `uncertain`

#### Scenario: Past-performance disclaimer does not cover a forecast
- **WHEN** a forecast is followed only by `Wyniki historyczne nie są gwarancją przyszłych wyników.`
- **THEN** R15 is `fail`

#### Scenario: Promotional imperative is not a forecast
- **WHEN** the `m2-alfa-landing` mock is analyzed (`Zarabiaj nawet do 18% rocznie…`)
- **THEN** R15 is `not_applicable`, and the missing risk warning stays R3's

#### Scenario: Warning sentence is not a forecast
- **WHEN** the only sentence is `Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników.`
- **THEN** R15 is `not_applicable`

### Requirement: R16 tax information
When the material refers to tax treatment, R16 SHALL check that it clearly says the treatment depends on the client's individual situation and may change (ZASÓB R16, art. 44 ust. 7).

A tax reference is any of these: `podat…`, `opodatkowan…`, `IKE`, `IKZE`, `Belk…`, `ulga podatkowa`, `zwolnieni… z podatku`, `odliczeni… od dochodu/podatku`, `PIT`, `tax…`. VAT mentions (`VAT`, `podatek od towarów i usług`) and the disclaimer sentences themselves SHALL NOT count as tax references.

The disclaimer has two parts:
- **Individual situation:** `zależy/uzależnion… od indywidualnej/osobistej sytuacji`, `individual circumstances`.
- **Possible change:** `może/mogą ulec zmianie / się zmienić`, `subject to change`, `may change`. To count, this part must be in the same sentence as the individual part, or in a sentence that mentions tax or `przepis…`.

R16 SHALL produce:
- `not_applicable` without a tax reference;
- `pass`, quoting the sentence with the individual part, when both parts are present;
- `fail` otherwise. The evidence quotes the first tax reference when neither part is present, or the partial disclaimer when only one is. The Polish explanation names each missing part.

It is rules-only.

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

#### Scenario: VAT is not tax treatment
- **WHEN** the only tax word is in `Cena zawiera podatek VAT.`
- **THEN** R16 is `not_applicable`

#### Scenario: No tax reference
- **WHEN** the `eurotrade` mock is analyzed
- **THEN** R16 is `not_applicable` with null evidence
