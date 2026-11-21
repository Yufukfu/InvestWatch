## MODIFIED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, a legal basis, its dictionaries, an `implemented` flag and an optional `llm:` block (see the `llm-analysis` capability). Only implemented rules SHALL run. Loading SHALL validate every rule parameter the rules read (pattern lists and `negation_before` compile, `window` and `prominent_sentences` are non-negative integers, `min_ratio` is a number in (0, 1], `labels` and `footnote_markers` are lists of strings, `hiding_regions` is a list of strings, `borderline_margin` is a non-negative integer) `labels` SHALL be non-empty, unknown parameter keys SHALL be rejected, and the YAML root SHALL be a mapping, so a bad catalogue fails at load and never on the first document. Shared dictionaries MAY be written once with YAML anchors and reused by several rules.

#### Scenario: Catalogue is complete
- **WHEN** the catalogue is loaded
- **THEN** it holds 19 entries whose ids match the contract `rule_id` pattern, and exactly R1, R2, R3, R4, R6, R10, R14, R17 and R18 are implemented

#### Scenario: LLM-refined rules declare it
- **WHEN** the catalogue is loaded
- **THEN** R3, R17 and R18 have an `llm:` block and no other M2 entry has one

#### Scenario: Malformed catalogue
- **WHEN** an entry has an unknown severity or a duplicate id
- **THEN** loading fails with an error naming the entry

#### Scenario: Bad rule parameter
- **WHEN** `negation_before` is not a valid regex, or `prominent_sentences` is not an integer, or `min_ratio` is 0 or above 1, or the root is a list
- **THEN** loading fails with a catalogue error naming the rule or the file

### Requirement: Evidence is an exact quote
Every rule result with non-null `evidence` SHALL quote a substring of the document's original `text`. Each result SHALL carry the catalogue's name, severity and legal basis, a Polish explanation, and `method`: `rule` for a rules-only result, `hybrid` when an LLM verdict replaced a rules-only result that had its own evidence, `llm` when it replaced one without evidence. Visual rules (R4, R6) SHALL add `evidence_locator` with the `viewport` and `bbox` of the block they judged, when the block has a `bbox`.

#### Scenario: Evidence check
- **WHEN** all implemented rules run on every mock document, rules-only and with a stub judge
- **THEN** each non-null `evidence` is found verbatim in that document's `text`

#### Scenario: Method reflects the source
- **WHEN** R17 is decided by a valid LLM verdict and R2 is not deferred
- **THEN** R17 has `method: llm` or `hybrid` and R2 has `method: rule`

#### Scenario: Visual locator
- **WHEN** R4 fails on `m2-alfa-landing`
- **THEN** its `evidence_locator.viewport` is the viewport of the judged risk block and `bbox` is that block's `bbox`

### Requirement: R3 risk information next to return claims
R3 SHALL be `not_applicable` when the text makes no return claim (percent figures, or return vocabulary such as `zysk`, `zarob…`, `stopa zwrotu`). It SHALL pass when every return-claim sentence has a risk warning within the configured sentence window (default ±2). Otherwise it SHALL fail, quoting the first uncovered claim. A warning marked as a footnote (leading `*` or `¹`) SHALL NOT count as next to the claim. A loss denial (`bez ryzyka`, `nie stracisz`) SHALL NOT count as a warning, but a negated exclusion of loss (`nie jest wykluczona utrata`, `nie można wykluczyć straty`, `nie gwarantujemy braku strat`) SHALL. An affirmed exclusion (`wykluczamy straty`, `nie tylko wyklucza straty`, `gwarantujemy brak straty`) is a denial. A denial SHALL NOT swallow a warning that follows it: `bez opłat ryzyko utraty kapitału` still counts as a warning. Plural and `nie ma` denials (`zero ryzyk`, `nie ma ryzyka straty`, `nie istnieje ryzyko utraty`) SHALL NOT count as warnings. The warning must directly accompany each claim (ZASÓB: "bezpośrednio towarzyszy"); a warning elsewhere on the page SHALL NOT satisfy R3. R3 SHALL defer to the LLM only in the borderline proximity case: a rules-only `fail` where, for every uncovered claim, the nearest non-footnote warning is between `window + 1` and `window + borderline_margin` sentences away (default margin 2). In that case a valid LLM verdict SHALL replace the rules-only result, including `fail` to `pass`. An absent warning, a footnote-only warning, a warning farther than the margin, and every other case SHALL NOT be deferred, and whenever no valid verdict arrives the rules-only result SHALL stand.

#### Scenario: No return claim
- **WHEN** the text is `Otwórz IKE i inwestuj długoterminowo.`
- **THEN** R3 is `not_applicable`

#### Scenario: Warning next to claim
- **WHEN** a sentence promising `8% rocznie` is directly followed by `Inwestowanie wiąże się z ryzykiem utraty kapitału.`
- **THEN** R3 is `pass` with the warning as evidence

#### Scenario: Warning only in a footnote
- **WHEN** the claim `Zarabiaj nawet do 18% rocznie na portfelu ETF!` is followed four sentences later by `*Inwestowanie wiąże się z ryzykiem…`
- **THEN** R3 is `fail` with the claim as evidence

#### Scenario: No warning at all
- **WHEN** the text has a return claim and no risk vocabulary
- **THEN** R3 is `fail`

#### Scenario: Negated exclusion of loss
- **WHEN** `Zarabiaj 8% rocznie.` is followed by `Nie jest wykluczona utrata kapitału.`
- **THEN** R3 is `pass`

#### Scenario: Affirmed exclusion of loss
- **WHEN** `Zarabiaj 12% rocznie.` is followed by `Nasz fundusz nie tylko wyklucza straty, ale daje spokój.`
- **THEN** R3 is `fail`

#### Scenario: Plural and nie ma denials
- **WHEN** `Zarabiaj 12% rocznie.` is followed by `Zero ryzyk.` or `Nie ma ryzyka utraty kapitału.`
- **THEN** R3 is `fail`

#### Scenario: Denial word before a warning
- **WHEN** `Zysk 10% rocznie, bez opłat ryzyko utraty kapitału.`
- **THEN** R3 is `pass`

#### Scenario: Near-window case goes to the LLM
- **WHEN** `Zarabiaj 9% rocznie.` is followed by two neutral sentences and then `Inwestowanie wiąże się z ryzykiem utraty kapitału.` (distance 3, window 2), and the judge answers R3 `pass` with a verified quote
- **THEN** R3 is `pass` with `method: hybrid`

#### Scenario: Warning absent is never deferred
- **WHEN** the text has `Zysk 15% rocznie.` and no risk vocabulary anywhere, with a judge configured that would answer `pass`
- **THEN** R3 is `fail` with `method: rule` and no request is sent for R3

#### Scenario: Footnote-only warning is not deferred
- **WHEN** the footnote-only text above is analyzed with a judge configured
- **THEN** R3 is `fail` with `method: rule` and no request is sent for R3

#### Scenario: Borderline without the LLM
- **WHEN** the near-window text is analyzed and the LLM is unavailable
- **THEN** R3 is `fail` with `method: rule`, as rules-only

## ADDED Requirements

### Requirement: R4 risk font size
R4 SHALL be `not_applicable` when the document has no `blocks`; it SHALL never be `pass` without `blocks`. When the material has no risk information (R3's warning dictionary, denials excluded) R4 SHALL be `not_applicable` with the explanation `brak informacji o ryzyku`; when risk text exists but no visible block carries it, R4 SHALL be `not_applicable` (visibility is R5). The benchmark is the dominant font size of the material (ZASÓB: "przeważająca wielkość czcionki materiału"). For `desktop`, `mobile` and, when present, `tablet` it SHALL compare the largest visible risk block's `font_size_px` with the length-weighted median `font_size_px` of the visible blocks of that viewport (weight = text length), and fail when the ratio is below `min_ratio` (default 0.75). The worst viewport SHALL decide the result. The explanation SHALL state both sizes and the ratio; the evidence SHALL be the first risk-warning sentence inside the risk block, located in the document `text` (or null if the block cannot be found there). Blocks with a `font_size_px` of 0 or less SHALL NOT set the dominant size; a visible risk block with no positive size SHALL make R4 `uncertain`. The displayed ratio SHALL be truncated, never rounded up, so it cannot contradict the verdict.

#### Scenario: Small footer warning
- **WHEN** `m2-alfa-landing` (blocks 44 px, 20 px and a 9 px risk block on desktop) is analyzed
- **THEN** R4 is `fail`, the explanation names 9 px, 20 px and 0,45, and the evidence is the risk sentence

#### Scenario: Readable warning
- **WHEN** the risk block is 18 px and the weighted median is 20 px
- **THEN** R4 is `pass`

#### Scenario: No blocks
- **WHEN** a document has an empty `blocks` list (`m2-bank-ok`)
- **THEN** R4 is `not_applicable`

#### Scenario: No risk information
- **WHEN** blocks exist and the material contains no risk warning at all
- **THEN** R4 is `not_applicable` with the explanation `brak informacji o ryzyku`

#### Scenario: Risk text only in an invisible block
- **WHEN** the only risk block has `visible: false`
- **THEN** R4 is `not_applicable`

#### Scenario: Worst viewport decides
- **WHEN** the desktop ratio is 0.9 and the mobile ratio is 0.5
- **THEN** R4 is `fail` and `evidence_locator.viewport` is `mobile`

### Requirement: R6 hidden risk information
R6 SHALL be `not_applicable` without `blocks`, and `not_applicable` with the explanation `brak informacji o ryzyku` without a risk block; it SHALL never be `pass` without `blocks`. R6 SHALL be evaluated on `desktop`, `mobile` and, when present, `tablet`. In a viewport a risk block is hidden by placement when its `region` is in `hiding_regions` (default `footer`, `legal`) or its text starts with a footnote marker, and `in_viewport_on_load` is `false`; with that placement and `in_viewport_on_load` missing it is possibly hidden. Per viewport R6 SHALL fail when every risk block is hidden, be `uncertain` when every risk block is hidden or possibly hidden and at least one is possibly hidden, and pass otherwise. The worst viewport SHALL decide. `visible` and `requires_interaction` SHALL NOT affect R6 (they belong to R5 and R7). R6 SHALL never pass on missing data: a risk block in view on load is exposed, but a block with no `region` that is not footnote-marked has no rendering metadata; when no risk block has metadata R6 SHALL be `not_applicable` with the explanation `brak metadanych renderowania`, and when hidden blocks sit next to blocks without metadata it SHALL be `uncertain`.

#### Scenario: Footer only, below the fold
- **WHEN** `m2-alfa-landing` is analyzed (risk block in `footer`, `in_viewport_on_load: false`, on desktop and mobile)
- **THEN** R6 is `fail` with the risk sentence as evidence

#### Scenario: Warning in the main region
- **WHEN** the only risk block is in `region: main`, even with `in_viewport_on_load: false`
- **THEN** R6 is `pass`

#### Scenario: Footer warning visible on load
- **WHEN** the only risk block is in `footer` with `in_viewport_on_load: true`
- **THEN** R6 is `pass`

#### Scenario: Unknown viewport position
- **WHEN** the only risk block is in `legal` and has no `in_viewport_on_load`
- **THEN** R6 is `uncertain`

#### Scenario: No blocks
- **WHEN** the document has no `blocks`
- **THEN** R6 is `not_applicable`

#### Scenario: Blocks without rendering metadata
- **WHEN** the risk block has `region: null` and `in_viewport_on_load: null` (the scraper does not render pages yet)
- **THEN** R6 is `not_applicable` with the explanation `brak metadanych renderowania`, never `pass`

#### Scenario: No risk block
- **WHEN** blocks exist and none is a risk warning
- **THEN** R6 is `not_applicable` with the explanation `brak informacji o ryzyku`

### Requirement: R10 language consistency
R10 checks that risk information is not given in a language other than the main message (ZASÓB). It SHALL be `not_applicable` with the explanation `brak informacji o ryzyku` when the text has no risk-warning sentence (R3's warning dictionary, denials excluded). The main language SHALL be the dominant language of the headline and body, excluding legal and footer content: with `blocks`, the length-weighted majority language of the visible non-warning blocks whose `region` is not `footer` or `legal` (desktop viewport if present, else the first present); without `blocks`, that of the non-warning sentences whose language is known; in both cases the document language guess when none is known. R10 SHALL pass when at least one warning sentence is in the main language, fail quoting the first warning sentence when warnings exist and none is in the main language, and be `uncertain` when no warning sentence has a known language.

#### Scenario: English warning on a Polish page
- **WHEN** the `eurotrade` mock is analyzed (Polish copy, warning `Risk warning: CFDs are complex instruments…`)
- **THEN** R10 is `fail` with evidence starting `Risk warning: CFDs are complex instruments`

#### Scenario: Polish warning on a Polish page
- **WHEN** `m2-bank-ok` is analyzed
- **THEN** R10 is `pass`

#### Scenario: Bilingual warnings
- **WHEN** a Polish page has both a Polish and an English risk warning
- **THEN** R10 is `pass`

#### Scenario: No warning
- **WHEN** the text has no risk warning
- **THEN** R10 is `not_applicable` with the explanation `brak informacji o ryzyku`

#### Scenario: English legal footer does not set the main language
- **WHEN** blocks hold a Polish headline and body, a Polish risk warning in `main`, and a long English legal text in `region: legal`
- **THEN** the main language is `pl` and R10 is `pass`

#### Scenario: Language unknown
- **WHEN** the only warning sentence is `Ryzyko!` (too short for a language guess)
- **THEN** R10 is `uncertain`

### Requirement: R14 past-performance disclaimer
R14 SHALL be `not_applicable` when no sentence presents past performance: a return figure (a percentage, or an amount such as `5 000 zł` or `1200 PLN` next to return vocabulary such as `zysk`, `zarobili`, `przyniósł`; past results in any unit) together with a past marker (a past-tense return verb such as `zarobili`, `wypracował`, `osiągnął`, `przyniósł`; `historyczn…`; `w ostatnich N latach/miesiącach`; or a year not later than the document's `fetched_at` year without a future marker such as `spodziewa`, `prognoz`, `będzie`, `expected`, `will`). ZASÓB requires a clear disclaimer to be present, with no proximity requirement. R14 SHALL pass when a past-performance disclaimer (`wyniki historyczne nie są gwarancją / wiarygodnym wskaźnikiem…`, `past performance is not a reliable indicator…`) appears anywhere in the material, including only as a footnote, quoting the first non-footnote occurrence if there is one, else the footnote. A footnote-only placement SHALL be left to R6 (ZASÓB: "ryzyko ukryte w przypisach"), so one violation is counted once. It SHALL fail, quoting the first past-performance sentence, when there is no disclaimer. Distance between the claim and the disclaimer SHALL NOT affect R14.

#### Scenario: Past returns without warning
- **WHEN** the `eurotrade` mock is analyzed (`Nasi klienci zarobili średnio 34% w 2025 roku.`)
- **THEN** R14 is `fail` with that sentence as evidence

#### Scenario: Disclaimer next to past returns
- **WHEN** `Fundusz wypracował 12% w 2024 roku.` is followed by `Wyniki historyczne nie są gwarancją przyszłych wyników.`
- **THEN** R14 is `pass` with the warning as evidence

#### Scenario: Past returns as an amount
- **WHEN** the text is `Nasi klienci zarobili 5 000 zł.` or `Zysk 1200 PLN w 2025 roku.` with no disclaimer
- **THEN** R14 is `fail`

#### Scenario: Amount without a past return
- **WHEN** the text is `Bonus 500 zł na start w 2025 roku.`
- **THEN** R14 is `not_applicable`

#### Scenario: Forecast is not past performance
- **WHEN** the only figure is in `W 2026 roku spodziewamy się 10% zysku.` and `fetched_at` is in 2026
- **THEN** R14 is `not_applicable`

#### Scenario: Disclaimer far from the claim
- **WHEN** `Fundusz wypracował 12% w 2024 roku.` is the first sentence and `Wyniki historyczne nie są gwarancją przyszłych wyników.` is the tenth
- **THEN** R14 is `pass`

#### Scenario: Disclaimer only as a footnote
- **WHEN** the only disclaimer is `*Wyniki historyczne nie są gwarancją przyszłych wyników.`, and the document's `blocks` show it as the only risk block, in `footer` with `in_viewport_on_load: false`
- **THEN** R14 is `pass` with the footnote as evidence and R6 is `fail`

### Requirement: R17 implying supervisory approval
Stating supervision alone SHALL NOT be a violation; R17 covers a mention used to suggest approval of the product or service (ZASÓB). R17 SHALL be `not_applicable` when the text does not mention a supervisor (`KNF`, `UKNF`, `Komisja Nadzoru Finansowego`, `ESMA`, `nadzór`/`nadzorowany`, `regulowany przez`, a `licencja` of a supervisor or for brokerage activity, `supervised`, `regulated by`); a company's supervisory board (`rada nadzorcza`) and `nadzorowany przez` someone who is not a supervisor SHALL NOT count as a mention. It SHALL fail, quoting the sentence, when an approval word (`zatwierdzon…`, `zaaprobowan…`, `aprobat…`, `rekomendowan… przez`, a `certyfikat` of the supervisor, `approved by`, `endorsed by`) is in the same sentence as a mention. A negated approval (`KNF nie zatwierdza…`) and the lawful prospectus statement (`zatwierdzenie prospektu przez KNF…`) SHALL NOT be a rules-only fail. Otherwise its rules-only result SHALL be `pass`, quoting the first mention, and it SHALL be deferred to the LLM (`llm.when: always`), which judges whether the wording suggests that the supervisor approves the product.

#### Scenario: Negated approval or prospectus statement
- **WHEN** the text is `Komisja Nadzoru Finansowego nie zatwierdza materiałów reklamowych.` or `Zatwierdzenie prospektu przez KNF nie powinno być rozumiane jako poparcie…`
- **THEN** R17 is `pass` rules-only

#### Scenario: Supervisory board is not a supervisor
- **WHEN** the text is `Rada Nadzorcza zatwierdziła wypłatę dywidendy.`
- **THEN** R17 and R18 are `not_applicable`

#### Scenario: Explicit approval
- **WHEN** the text contains `Produkt zatwierdzony przez KNF.`
- **THEN** R17 is `fail` with `method: rule` and is not sent to the LLM

#### Scenario: Bare mention goes to the LLM
- **WHEN** `m2-alfa-landing` is analyzed and the judge answers R17 `fail` quoting `Działamy pod nadzorem KNF – Twoje środki są bezpieczne.`
- **THEN** R17 is `fail` with that evidence and `method: hybrid`

#### Scenario: Bare mention without the LLM
- **WHEN** `m2-alfa-landing` is analyzed rules-only
- **THEN** R17 is `pass` with `method: rule`

#### Scenario: No supervisor mentioned
- **WHEN** `m2-bank-ok` is analyzed
- **THEN** R17 is `not_applicable`

### Requirement: R18 supervision as a safety argument
R18 SHALL be `not_applicable` without a supervisor mention (same dictionary as R17). It SHALL fail, quoting the sentence, when a safety word (`bezpieczn…`, `bezpieczeństwo`, `gwarant…`, `pewna`/`pewne`/`pewny`/`pewność`, `chronion…`, `bez ryzyka`, `safe`, `secure`, `guaranteed`, `protected`; a negated guarantee such as `nie gwarantuje bezpieczeństwa` and the mandatory investor-compensation-scheme fact `środki chronione przez system rekompensat` SHALL NOT count) is in the same sentence as a mention; this verdict SHALL NOT be deferred. When a safety word is only within one sentence of a mention, the rules-only result SHALL be `uncertain`, quoting the mention sentence, and it SHALL be deferred to the LLM. Otherwise R18 SHALL pass.

#### Scenario: Same sentence
- **WHEN** `m2-alfa-landing` is analyzed (`Działamy pod nadzorem KNF – Twoje środki są bezpieczne.`)
- **THEN** R18 is `fail` with that sentence as evidence and `method: rule`

#### Scenario: Neighbouring sentence goes to the LLM
- **WHEN** the text is `Jesteśmy nadzorowani przez KNF. Twoje pieniądze są u nas bezpieczne.` and the judge answers R18 `fail` with a verified quote
- **THEN** R18 is `fail` with `method: hybrid`

#### Scenario: Neighbouring sentence without the LLM
- **WHEN** the same text is analyzed rules-only
- **THEN** R18 is `uncertain`

#### Scenario: ZASÓB example
- **WHEN** the text contains `Inwestycja w pełni bezpieczna – spełniamy rygorystyczne wymogi nadzorcze KNF.`
- **THEN** R18 is `fail` with that sentence as evidence

#### Scenario: Compensation-scheme fact
- **WHEN** the text is `Fundusz nadzorowany przez KNF, środki chronione przez system rekompensat.`
- **THEN** R18 is `pass`

#### Scenario: Neutral legal footer
- **WHEN** the only mention is `Dom Maklerski podlega nadzorowi Komisji Nadzoru Finansowego.` with no safety word nearby
- **THEN** R18 is `pass`
