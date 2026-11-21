## MODIFIED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, a legal basis, its dictionaries, an `implemented` flag and an optional `llm:` block (see the `llm-analysis` capability). Only implemented rules SHALL run. Loading SHALL validate every rule parameter the rules read (pattern lists and `negation_before` compile, `window` and `prominent_sentences` are non-negative integers, `min_ratio` is a number in (0, 1], `labels` and `footnote_markers` are lists of strings, `hiding_regions` is a list of strings) `labels` SHALL be non-empty, unknown parameter keys SHALL be rejected, and the YAML root SHALL be a mapping, so a bad catalogue fails at load and never on the first document. Shared dictionaries MAY be written once with YAML anchors and reused by several rules.

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
R3 SHALL be `not_applicable` when the text makes no return claim (percent figures, or return vocabulary such as `zysk`, `zarob…`, `stopa zwrotu`). It SHALL pass when every return-claim sentence has a risk warning within the configured sentence window (default ±2). Otherwise it SHALL fail, quoting the first uncovered claim. A warning marked as a footnote (leading `*` or `¹`) SHALL NOT count as next to the claim. A loss denial (`bez ryzyka`, `nie stracisz`) SHALL NOT count as a warning, but a negated exclusion of loss (`nie jest wykluczona utrata`, `nie można wykluczyć straty`, `nie gwarantujemy braku strat`) SHALL. An affirmed exclusion (`wykluczamy straty`, `nie tylko wyklucza straty`, `gwarantujemy brak straty`) is a denial. A denial SHALL NOT swallow a warning that follows it: `bez opłat ryzyko utraty kapitału` still counts as a warning. Plural and `nie ma` denials (`zero ryzyk`, `nie ma ryzyka straty`, `nie istnieje ryzyko utraty`) SHALL NOT count as warnings. R3 SHALL defer to the LLM only in borderline cases: a rules-only `fail` while a warning exists outside the window or only as a footnote, or a rules-only `fail` whose uncovered claim sentences all matched return vocabulary without a percent figure. In those cases a valid LLM verdict SHALL replace the rules-only result; in every other case, and whenever no valid verdict arrives, the rules-only result SHALL stand.

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

#### Scenario: Footnote case goes to the LLM
- **WHEN** the footnote-only text above is analyzed with a judge and the judge answers R3 `uncertain` with a verified quote
- **THEN** R3 is `uncertain` with `method: hybrid`

#### Scenario: Vocabulary-only claim goes to the LLM
- **WHEN** the only claim sentence is `Zyskaj dostęp do platformy w 5 minut.` with no warning, and the judge answers R3 `not_applicable`
- **THEN** R3 is `not_applicable` with `method: hybrid`

#### Scenario: Clear fail is not deferred
- **WHEN** the text has `Zysk 15% rocznie.` and no risk vocabulary anywhere, with a judge configured
- **THEN** R3 is `fail` with `method: rule` and no request is sent for R3

#### Scenario: Borderline without the LLM
- **WHEN** the footnote-only text is analyzed and the LLM is unavailable
- **THEN** R3 is `fail` with `method: rule`, as rules-only

## ADDED Requirements

### Requirement: R4 risk font size
R4 SHALL be `not_applicable` when the document has no `blocks`, or no visible block whose text is a risk warning (R3's warning dictionary, denials excluded); it SHALL never be `pass` without `blocks`. For each viewport present it SHALL compare the largest visible risk block's `font_size_px` with the length-weighted median `font_size_px` of the visible blocks of that viewport (weight = text length), and fail when the ratio is below `min_ratio` (default 0.75). The worst viewport SHALL decide the result. The explanation SHALL state both sizes and the ratio; the evidence SHALL be the risk block's text located in the document `text` (or null if it cannot be found there).

#### Scenario: Small footer warning
- **WHEN** `m2-alfa-landing` (blocks 44 px, 20 px and a 9 px risk block on desktop) is analyzed
- **THEN** R4 is `fail`, the explanation names 9 px, 20 px and 0,45, and the evidence is the risk sentence

#### Scenario: Readable warning
- **WHEN** the risk block is 18 px and the weighted median is 20 px
- **THEN** R4 is `pass`

#### Scenario: No blocks
- **WHEN** a document has an empty `blocks` list (`m2-bank-ok`)
- **THEN** R4 is `not_applicable`

#### Scenario: Blocks without a risk block
- **WHEN** blocks exist but none contains a risk warning
- **THEN** R4 is `not_applicable`

#### Scenario: Worst viewport decides
- **WHEN** the desktop ratio is 0.9 and the mobile ratio is 0.5
- **THEN** R4 is `fail` and `evidence_locator.viewport` is `mobile`

### Requirement: R6 hidden risk information
R6 SHALL be `not_applicable` without `blocks` or without a risk block; it SHALL never be `pass` without `blocks`. In a viewport a risk block is hidden by placement when its `region` is in `hiding_regions` (default `footer`, `legal`) or its text starts with a footnote marker, and `in_viewport_on_load` is `false`; with that placement and `in_viewport_on_load` missing it is possibly hidden. Per viewport R6 SHALL fail when every risk block is hidden, be `uncertain` when every risk block is hidden or possibly hidden and at least one is possibly hidden, and pass otherwise. The worst viewport SHALL decide. `visible` and `requires_interaction` SHALL NOT affect R6 (they belong to R5 and R7).

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

### Requirement: R10 language consistency
R10 SHALL be `not_applicable` when the text has no risk-warning sentence (R3's warning dictionary, denials excluded). The main language SHALL be the length-weighted majority language of the non-warning sentences whose language is known, or the document language guess when none is known. R10 SHALL pass when at least one warning sentence is in the main language, fail quoting the first warning sentence when warnings exist and none is in the main language, and be `uncertain` when no warning sentence has a known language.

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
- **THEN** R10 is `not_applicable`

#### Scenario: Language unknown
- **WHEN** the only warning sentence is `Ryzyko!` (too short for a language guess)
- **THEN** R10 is `uncertain`

### Requirement: R14 warning next to past performance
R14 SHALL be `not_applicable` when no sentence presents past performance: a return figure together with a past marker (a past-tense return verb such as `zarobili`, `wypracował`, `osiągnął`, `przyniósł`; `historyczn…`; `w ostatnich N latach/miesiącach`; or a year not later than the document's `fetched_at` year without a future marker such as `spodziewa`, `prognoz`, `będzie`, `expected`, `will`). It SHALL pass when a past-performance warning (`wyniki historyczne nie są gwarancją / wiarygodnym wskaźnikiem…`, `past performance is not a reliable indicator…`) is within `window` sentences (default 2) of every such sentence and is not footnote-marked, quoting the warning; otherwise it SHALL fail quoting the first uncovered past-performance sentence.

#### Scenario: Past returns without warning
- **WHEN** the `eurotrade` mock is analyzed (`Nasi klienci zarobili średnio 34% w 2025 roku.`)
- **THEN** R14 is `fail` with that sentence as evidence

#### Scenario: Warning next to past returns
- **WHEN** `Fundusz wypracował 12% w 2024 roku.` is followed by `Wyniki historyczne nie są gwarancją przyszłych wyników.`
- **THEN** R14 is `pass` with the warning as evidence

#### Scenario: Forecast is not past performance
- **WHEN** the only figure is in `W 2026 roku spodziewamy się 10% zysku.` and `fetched_at` is in 2026
- **THEN** R14 is `not_applicable`

#### Scenario: Warning only as a footnote
- **WHEN** the past-performance sentence is followed by `*Wyniki historyczne nie są gwarancją przyszłych wyników.`
- **THEN** R14 is `fail`

### Requirement: R17 implying supervisory approval
R17 SHALL be `not_applicable` when the text does not mention a supervisor (`KNF`, `UKNF`, `Komisja Nadzoru Finansowego`, `ESMA`, `nadzór`/`nadzorowany`, `regulowany`, `licencja`, `supervised`, `regulated by`). It SHALL fail, quoting the sentence, when an approval word (`zatwierdzon…`, `zaaprobowan…`, `aprobat…`, `rekomendowan… przez`, `certyfikat…`, `approved by`, `endorsed by`) is in the same sentence as a mention. Otherwise its rules-only result SHALL be `pass`, quoting the first mention, and it SHALL be deferred to the LLM (`llm.when: always`), which judges whether the wording suggests that the supervisor approves the product.

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
R18 SHALL be `not_applicable` without a supervisor mention (same dictionary as R17). It SHALL fail, quoting the sentence, when a safety word (`bezpieczn…`, `gwarantowan…`, `pewna`/`pewne`/`pewny`/`pewność`, `chronion…`, `bez ryzyka`, `safe`, `secure`, `guaranteed`, `protected`) is in the same sentence as a mention; this verdict SHALL NOT be deferred. When a safety word is only within one sentence of a mention, the rules-only result SHALL be `uncertain`, quoting the mention sentence, and it SHALL be deferred to the LLM. Otherwise R18 SHALL pass.

#### Scenario: Same sentence
- **WHEN** `m2-alfa-landing` is analyzed (`Działamy pod nadzorem KNF – Twoje środki są bezpieczne.`)
- **THEN** R18 is `fail` with that sentence as evidence and `method: rule`

#### Scenario: Neighbouring sentence goes to the LLM
- **WHEN** the text is `Jesteśmy nadzorowani przez KNF. Twoje pieniądze są u nas bezpieczne.` and the judge answers R18 `fail` with a verified quote
- **THEN** R18 is `fail` with `method: hybrid`

#### Scenario: Neighbouring sentence without the LLM
- **WHEN** the same text is analyzed rules-only
- **THEN** R18 is `uncertain`

#### Scenario: Neutral legal footer
- **WHEN** the only mention is `Dom Maklerski podlega nadzorowi Komisji Nadzoru Finansowego.` with no safety word nearby
- **THEN** R18 is `pass`
