# m2-compliance-rules Specification

## Purpose
Check investment-firm marketing material against the 18 UKNF rules (Art. 44 of Delegated Regulation (EU) 2017/565), deterministically first, each result explainable by an exact quote.

## Requirements

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

### Requirement: Evidence is an exact quote
Every rule result with non-null `evidence` SHALL quote a substring of the document's original `text`. Each result SHALL carry the catalogue's name, severity and legal basis, a Polish explanation, and `method`: `rule` for a rules-only result, `hybrid` or `llm` when an LLM verdict replaced it. Visual rules (R4, R6) SHALL add `evidence_locator` with the `viewport` and `bbox` of the block they judged.

#### Scenario: Evidence check
- **WHEN** all implemented rules run on every mock document, rules-only and with a stub judge
- **THEN** each non-null `evidence` is found verbatim in that document's `text`

#### Scenario: Method reflects the source
- **WHEN** R17 is decided by a valid LLM verdict and R2 is not deferred
- **THEN** R17 has `method: llm` or `hybrid` and R2 has `method: rule`
- **AND** `method` SHALL be `hybrid` when the replaced rules-only result had its own evidence, and `llm` when it had none

#### Scenario: Visual locator
- **WHEN** R4 fails on `m2-alfa-landing`
- **THEN** its `evidence_locator.viewport` is the viewport of the judged risk block and `bbox` is that block's `bbox`
- **AND** a block without a four-number `bbox` SHALL give a locator with `bbox: null`

### Requirement: R1 firm identification
R1 checks the official name of the investment firm (ZASÓB R1, "oficjalną nazwę firmy inwestycyjnej"). R1 SHALL pass when an official form of the matched firm appears in the text, quoting it: its registry `name`, a ` – ` line of it, or their core without legal forms. It SHALL be `uncertain` when only an entry of the `aliases` column appears. It SHALL fail when no firm is matched or no name or alias of it is in the text.

#### Scenario: Name present
- **WHEN** the text contains `Konto Premium Alfa Inwestycje` and the Alfa firm is matched
- **THEN** R1 is `pass` with evidence `Alfa Inwestycje`

#### Scenario: Matched by domain only
- **WHEN** the firm was matched only by the page domain and its name is absent from the text
- **THEN** R1 is `fail`

#### Scenario: Only a former or trade name used
- **WHEN** the registry holds `CERES DOM INWESTYCYJNY S.A.` with alias `EFIX DOM MAKLERSKI S.A.`, and the text names only `EFIX Dom Maklerski S.A.`
- **THEN** R1 is `uncertain` with evidence `EFIX Dom Maklerski S.A.`
- **AND** the explanation starts with `W materiale użyto nazwy nieoficjalnej/dawnej` and names `CERES DOM INWESTYCYJNY S.A.`

#### Scenario: Official name beats an alias in the same text
- **WHEN** the text names both the alias `Alfa Inwestycje DM` and the official `Alfa Inwestycje Dom Maklerski S.A.`
- **THEN** R1 is `pass` quoting the official form

#### Scenario: Bank brokerage unit line is official
- **WHEN** the registry holds `mBANK S.A. – Biuro Maklerskie mBank` and the text names `Biuro Maklerskie mBank`
- **THEN** R1 is `pass`

### Requirement: R2 ad labeling
R2 SHALL pass when the text contains an advertising label from its dictionary (for example `reklama`, `materiał marketingowy`, `informacja promocyjna`, `#reklama`), case-insensitively, in a prominent place: a hashtag label anywhere, or any label in the first or last two sentences. It SHALL quote the label. A label found only elsewhere SHALL give `uncertain` with that label as evidence. A label negated on the same line SHALL NOT count. Without a counting label it SHALL fail with null evidence.

#### Scenario: Labeled material
- **WHEN** the text starts with `Reklama.`
- **THEN** R2 is `pass` with evidence `Reklama`

#### Scenario: Unlabeled material
- **WHEN** the text contains no label from the dictionary
- **THEN** R2 is `fail`

#### Scenario: Label inside another word
- **WHEN** the only occurrence is inside a longer word such as `reklamacja`
- **THEN** R2 is `fail`

#### Scenario: Negated label
- **WHEN** the only occurrence is `To nie jest reklama, to edukacja.`
- **THEN** R2 is `fail`
- **AND** a label negated on the same line (`to nie jest reklama`, `nie reklama`, `not an ad`) SHALL NOT count; a hashtag label is never negated

#### Scenario: Negation on the previous line
- **WHEN** the text is a headline `Nie czekaj` and the next line is `Reklama`
- **THEN** R2 is `pass`

#### Scenario: Label buried mid-text
- **WHEN** the only label is in the third of six sentences and is not a hashtag
- **THEN** R2 is `uncertain` with the label as evidence

#### Scenario: Not only an ad
- **WHEN** the text is `To nie tylko reklama – to Twoja szansa.`
- **THEN** R2 is `pass`
- **AND** `nie tylko`, `jedynie`, `only`, `just` between the negation and the label cancel the negation

### Requirement: R3 risk information next to return claims
R3 SHALL be `not_applicable` when the text makes no return claim (percent figures, or return vocabulary such as `zysk`, `zarob…`, `stopa zwrotu`). It SHALL pass when every return-claim sentence has a risk warning within the configured sentence window (default ±2). Otherwise it SHALL fail, quoting the first uncovered claim. A warning marked as a footnote (leading `*` or `¹`) SHALL NOT count as next to the claim. A loss denial (`bez ryzyka`, `nie stracisz`) SHALL NOT count as a warning.

#### Scenario: No return claim
- **WHEN** the text is `Otwórz IKE i inwestuj długoterminowo.`
- **THEN** R3 is `not_applicable`

#### Scenario: Warning next to claim
- **WHEN** a sentence promising `8% rocznie` is directly followed by `Inwestowanie wiąże się z ryzykiem utraty kapitału.`
- **THEN** R3 is `pass` with the warning as evidence

#### Scenario: Warning only in a footnote
- **WHEN** the claim `Zarabiaj nawet do 18% rocznie na portfelu ETF!` is followed four sentences later by `*Inwestowanie wiąże się z ryzykiem…`
- **THEN** R3 is `fail` with the claim as evidence
- **AND** the warning SHALL directly accompany each claim (ZASÓB: "bezpośrednio towarzyszy"); a warning elsewhere on the page SHALL NOT satisfy R3

#### Scenario: No warning at all
- **WHEN** the text has a return claim and no risk vocabulary
- **THEN** R3 is `fail`

#### Scenario: Negated exclusion of loss
- **WHEN** `Zarabiaj 8% rocznie.` is followed by `Nie jest wykluczona utrata kapitału.`
- **THEN** R3 is `pass`
- **AND** a negated exclusion of loss (`nie jest wykluczona utrata`, `nie można wykluczyć straty`, `nie gwarantujemy braku strat`) SHALL count as a warning

#### Scenario: Affirmed exclusion of loss
- **WHEN** `Zarabiaj 12% rocznie.` is followed by `Nasz fundusz nie tylko wyklucza straty, ale daje spokój.`
- **THEN** R3 is `fail`
- **AND** an affirmed exclusion (`wykluczamy straty`, `nie tylko wyklucza straty`, `gwarantujemy brak straty`) is a denial

#### Scenario: Plural and nie ma denials
- **WHEN** `Zarabiaj 12% rocznie.` is followed by `Zero ryzyk.` or `Nie ma ryzyka utraty kapitału.`
- **THEN** R3 is `fail`
- **AND** plural and `nie ma` denials (`zero ryzyk`, `nie ma ryzyka straty`, `nie istnieje ryzyko utraty`) SHALL NOT count as warnings

#### Scenario: Denial word before a warning
- **WHEN** `Zysk 10% rocznie, bez opłat ryzyko utraty kapitału.`
- **THEN** R3 is `pass`
- **AND** a denial SHALL NOT swallow a warning that follows it: `bez opłat ryzyko utraty kapitału` still counts as a warning

#### Scenario: Near-window case goes to the LLM
- **WHEN** `Zarabiaj 9% rocznie.` is followed by two neutral sentences and then `Inwestowanie wiąże się z ryzykiem utraty kapitału.` (distance 3, window 2), and the judge answers R3 `pass` with a verified quote
- **THEN** R3 is `pass` with `method: hybrid`
- **AND** R3 SHALL defer to the LLM only when, for every uncovered claim, the nearest non-footnote warning is between `window + 1` and `window + borderline_margin` sentences away (default margin 2); a valid verdict then replaces the rules-only result, including `fail` to `pass`

#### Scenario: Warning absent is never deferred
- **WHEN** the text has `Zysk 15% rocznie.` and no risk vocabulary anywhere, with a judge configured that would answer `pass`
- **THEN** R3 is `fail` with `method: rule` and no request is sent for R3

#### Scenario: Footnote-only warning is not deferred
- **WHEN** the footnote-only text above is analyzed with a judge configured
- **THEN** R3 is `fail` with `method: rule` and no request is sent for R3
- **AND** a warning farther than the margin SHALL NOT be deferred either

#### Scenario: Borderline without the LLM
- **WHEN** the near-window text is analyzed and the LLM is unavailable
- **THEN** R3 is `fail` with `method: rule`, as rules-only

### Requirement: R4 risk font size
R4 SHALL compare the risk warning's font size with the dominant font size of the material (ZASÓB: "przeważająca wielkość czcionki materiału"): per viewport, the largest visible risk block's `font_size_px` against the length-weighted median `font_size_px` of the visible blocks, failing below `min_ratio` (default 0.75). The worst viewport SHALL decide. R4 SHALL be `not_applicable` without `blocks` and never `pass` without them.

#### Scenario: Small footer warning
- **WHEN** `m2-alfa-landing` (blocks 44 px, 20 px and a 9 px risk block on desktop) is analyzed
- **THEN** R4 is `fail`, the explanation names 9 px, 20 px and 0,45, and the evidence is the risk sentence
- **AND** the evidence SHALL be the first risk-warning sentence inside the risk block, located in the document `text`, or null if the block cannot be found there
- **AND** the displayed ratio SHALL be truncated, never rounded up, so it cannot contradict the verdict

#### Scenario: Readable warning
- **WHEN** the risk block is 18 px and the weighted median is 20 px
- **THEN** R4 is `pass`

#### Scenario: No blocks
- **WHEN** a document has an empty `blocks` list (`m2-bank-ok`)
- **THEN** R4 is `not_applicable`

#### Scenario: No risk information
- **WHEN** blocks exist and the material contains no risk warning at all (R3's warning dictionary, denials excluded)
- **THEN** R4 is `not_applicable` with the explanation `brak informacji o ryzyku`

#### Scenario: Risk text only in an invisible block
- **WHEN** the only risk block has `visible: false`
- **THEN** R4 is `not_applicable`, because visibility is R5's concern

#### Scenario: Unreadable sizes
- **WHEN** the visible blocks include 0 px blocks, or the only visible risk block is 0 px
- **THEN** 0 px blocks do not set the dominant size, and a visible risk block with no positive size makes R4 `uncertain`

#### Scenario: Worst viewport decides
- **WHEN** the desktop ratio is 0.9 and the mobile ratio is 0.5
- **THEN** R4 is `fail` and `evidence_locator.viewport` is `mobile`
- **AND** R4 SHALL be measured on `desktop`, `mobile` and, when present, `tablet`

### Requirement: R6 hidden risk information
R6 (ZASÓB "ryzyko ukryte w przypisach") SHALL fail when, in a viewport, every risk block is hidden by placement: its `region` is in `hiding_regions` (default `footer`, `legal`) or its text starts with a footnote marker, and `in_viewport_on_load` is `false`. The worst viewport SHALL decide. R6 SHALL be `not_applicable` without `blocks` and SHALL never pass on missing data.

#### Scenario: Footer only, below the fold
- **WHEN** `m2-alfa-landing` is analyzed (risk block in `footer`, `in_viewport_on_load: false`, on desktop and mobile)
- **THEN** R6 is `fail` with the risk sentence as evidence
- **AND** R6 SHALL be evaluated on `desktop`, `mobile` and, when present, `tablet`

#### Scenario: Warning in the main region
- **WHEN** the only risk block is in `region: main`, even with `in_viewport_on_load: false`
- **THEN** R6 is `pass`
- **AND** `visible` and `requires_interaction` SHALL NOT affect R6 (they belong to R5 and R7)

#### Scenario: Footer warning visible on load
- **WHEN** the only risk block is in `footer` with `in_viewport_on_load: true`
- **THEN** R6 is `pass`

#### Scenario: Unknown viewport position
- **WHEN** the only risk block is in `legal` and has no `in_viewport_on_load`
- **THEN** R6 is `uncertain`
- **AND** R6 SHALL be `uncertain` whenever every risk block of a viewport is hidden or possibly hidden and at least one is possibly hidden

#### Scenario: No blocks
- **WHEN** the document has no `blocks`
- **THEN** R6 is `not_applicable`

#### Scenario: Blocks without rendering metadata
- **WHEN** the risk block has `region: null` and `in_viewport_on_load: null` (the scraper does not render pages yet)
- **THEN** R6 is `not_applicable` with the explanation `brak metadanych renderowania`, never `pass`
- **AND** when hidden blocks sit next to blocks without metadata, R6 SHALL be `uncertain`

#### Scenario: No risk block
- **WHEN** blocks exist and none is a risk warning
- **THEN** R6 is `not_applicable` with the explanation `brak informacji o ryzyku`

### Requirement: R14 past-performance disclaimer
R14 SHALL pass when a sentence presents past performance and a clear past-performance disclaimer (`wyniki historyczne nie są gwarancją…`, `past performance is not a reliable indicator…`) appears anywhere in the material, with no proximity requirement (ZASÓB: "obecność wyraźnego zastrzeżenia"). It SHALL fail, quoting the first past-performance sentence, when there is no disclaimer, and be `not_applicable` without past performance.

#### Scenario: Past returns without warning
- **WHEN** the `eurotrade` mock is analyzed (`Nasi klienci zarobili średnio 34% w 2025 roku.`)
- **THEN** R14 is `fail` with that sentence as evidence
- **AND** a past-performance sentence SHALL hold a return figure and a past marker: a past-tense return verb (`zarobili`, `wypracował`, `osiągnął`, `przyniósł`), `historyczn…`, `w ostatnich N latach/miesiącach`, or a year not later than the `fetched_at` year

#### Scenario: Disclaimer next to past returns
- **WHEN** `Fundusz wypracował 12% w 2024 roku.` is followed by `Wyniki historyczne nie są gwarancją przyszłych wyników.`
- **THEN** R14 is `pass` with the warning as evidence

#### Scenario: Past returns as an amount
- **WHEN** the text is `Nasi klienci zarobili 5 000 zł.` or `Zysk 1200 PLN w 2025 roku.` with no disclaimer
- **THEN** R14 is `fail`
- **AND** a return figure SHALL be a percentage, or an amount next to return vocabulary (`zysk`, `zarobili`, `przyniósł`): past results in any unit

#### Scenario: Amount without a past return
- **WHEN** the text is `Bonus 500 zł na start w 2025 roku.`
- **THEN** R14 is `not_applicable`

#### Scenario: Forecast is not past performance
- **WHEN** the only figure is in `W 2026 roku spodziewamy się 10% zysku.` and `fetched_at` is in 2026
- **THEN** R14 is `not_applicable`
- **AND** a year SHALL NOT be a past marker in a sentence with a future marker (`spodziewa`, `prognoz`, `będzie`, `expected`, `will`)

#### Scenario: Disclaimer far from the claim
- **WHEN** `Fundusz wypracował 12% w 2024 roku.` is the first sentence and `Wyniki historyczne nie są gwarancją przyszłych wyników.` is the tenth
- **THEN** R14 is `pass`
- **AND** the distance between the claim and the disclaimer SHALL NOT affect R14

#### Scenario: Disclaimer only as a footnote
- **WHEN** the only disclaimer is `*Wyniki historyczne nie są gwarancją przyszłych wyników.`, and the document's `blocks` show it as the only risk block, in `footer` with `in_viewport_on_load: false`
- **THEN** R14 is `pass` with the footnote as evidence and R6 is `fail`
- **AND** a footnote-only placement SHALL be left to R6 ("ryzyko ukryte w przypisach") so one violation is counted once; a non-footnote disclaimer, when there is one, SHALL be the evidence

### Requirement: R17 implying supervisory approval
Stating supervision alone SHALL NOT be a violation: R17 covers a supervisor mention used to suggest approval of the product or service (ZASÓB). R17 SHALL fail, quoting the sentence, when an approval word is in the same sentence as a mention; otherwise its rules-only result SHALL be `pass`, deferred to the LLM (`llm.when: always`). Without a mention it SHALL be `not_applicable`.

#### Scenario: Negated approval or prospectus statement
- **WHEN** the text is `Komisja Nadzoru Finansowego nie zatwierdza materiałów reklamowych.` or `Zatwierdzenie prospektu przez KNF nie powinno być rozumiane jako poparcie…`
- **THEN** R17 is `pass` rules-only
- **AND** a negated approval and the lawful prospectus statement SHALL NOT be a rules-only fail

#### Scenario: Supervisory board is not a supervisor
- **WHEN** the text is `Rada Nadzorcza zatwierdziła wypłatę dywidendy.`
- **THEN** R17 and R18 are `not_applicable`
- **AND** a mention SHALL be `KNF`, `UKNF`, `Komisja Nadzoru Finansowego`, `ESMA`, `nadzór`/`nadzorowany`, `regulowany przez`, a `licencja` of a supervisor or for brokerage activity, `supervised` or `regulated by`, never a company's `rada nadzorcza` or `nadzorowany przez` someone who is not a supervisor

#### Scenario: Explicit approval
- **WHEN** the text contains `Produkt zatwierdzony przez KNF.`
- **THEN** R17 is `fail` with `method: rule` and is not sent to the LLM
- **AND** an approval word SHALL be `zatwierdzon…`, `zaaprobowan…`, `aprobat…`, `rekomendowan… przez`, a `certyfikat` of the supervisor, `approved by` or `endorsed by`

#### Scenario: Bare mention goes to the LLM
- **WHEN** `m2-alfa-landing` is analyzed and the judge answers R17 `fail` quoting `Działamy pod nadzorem KNF – Twoje środki są bezpieczne.`
- **THEN** R17 is `fail` with that evidence and `method: hybrid`

#### Scenario: Bare mention without the LLM
- **WHEN** `m2-alfa-landing` is analyzed rules-only
- **THEN** R17 is `pass` with `method: rule`, quoting the first mention

#### Scenario: No supervisor mentioned
- **WHEN** `m2-bank-ok` is analyzed
- **THEN** R17 is `not_applicable`

### Requirement: R18 supervision as a safety argument
R18 (ZASÓB: supervision "używane do sugerowania bezpieczeństwa inwestycji") SHALL fail, quoting the sentence and without deferring, when a safety word is in the same sentence as a supervisor mention (R17's dictionary). A safety word only in a neighbouring sentence SHALL give `uncertain`, deferred to the LLM. Otherwise R18 SHALL pass, and without a mention be `not_applicable`.

#### Scenario: Same sentence
- **WHEN** `m2-alfa-landing` is analyzed (`Działamy pod nadzorem KNF – Twoje środki są bezpieczne.`)
- **THEN** R18 is `fail` with that sentence as evidence and `method: rule`
- **AND** a safety word SHALL be `bezpieczn…`, `bezpieczeństwo`, `gwarant…`, `pewna`/`pewne`/`pewny`/`pewność`, `chronion…`, `bez ryzyka`, `safe`, `secure`, `guaranteed` or `protected`

#### Scenario: Neighbouring sentence goes to the LLM
- **WHEN** the text is `Jesteśmy nadzorowani przez KNF. Twoje pieniądze są u nas bezpieczne.` and the judge answers R18 `fail` with a verified quote
- **THEN** R18 is `fail` with `method: hybrid`

#### Scenario: Neighbouring sentence without the LLM
- **WHEN** the same text is analyzed rules-only
- **THEN** R18 is `uncertain`, quoting the mention sentence

#### Scenario: ZASÓB example
- **WHEN** the text contains `Inwestycja w pełni bezpieczna – spełniamy rygorystyczne wymogi nadzorcze KNF.`
- **THEN** R18 is `fail` with that sentence as evidence

#### Scenario: Compensation-scheme fact
- **WHEN** the text is `Fundusz nadzorowany przez KNF, środki chronione przez system rekompensat.`
- **THEN** R18 is `pass`
- **AND** the mandatory investor-compensation-scheme fact and a negated guarantee (`nie gwarantuje bezpieczeństwa`) SHALL NOT count as safety words

#### Scenario: Neutral legal footer
- **WHEN** the only mention is `Dom Maklerski podlega nadzorowi Komisji Nadzoru Finansowego.` with no safety word nearby
- **THEN** R18 is `pass`

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
