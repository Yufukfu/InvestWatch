## MODIFIED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, the legal basis that ZASÓB gives it, its dictionaries, an `implemented` flag and an optional `llm:` block (see `llm-analysis`). Only implemented rules SHALL run. Shared dictionaries MAY be written once with YAML anchors.

#### Scenario: Catalogue is complete
- **WHEN** the catalogue is loaded
- **THEN** it holds 19 entries whose ids match the contract `rule_id` pattern, and exactly R1, R2, R3, R4, R5, R6, R7, R8, R11, R12a, R12b, R13, R14, R15, R16, R17 and R18 are implemented

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

#### Scenario: Bad visual parameter
- **WHEN** `min_contrast` is below 1 or above 21, or `min_font_px` is not a positive number
- **THEN** loading fails with a catalogue error naming the rule and the key

### Requirement: Past performance is detected once
R12a, R12b, R13 and R14 SHALL share R14's past-performance detector. Without a past-performance sentence, R12a, R12b and R14 SHALL be `not_applicable` with `Materiał nie prezentuje wyników historycznych.`

Each SHALL check only its own element of art. 44 ust. 4:
- R12a: period, 12-month basis, reference period, source;
- R12b: currency and costs;
- R13: prominence;
- R14: the disclaimer.

A closed year range (`2021-2025`) whose end year is at or before the fetch year SHALL count as a past marker.

#### Scenario: No past performance
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R12a, R12b and R14 are `not_applicable` with the same explanation

#### Scenario: A missing disclaimer fails only R14
- **WHEN** the past performance is given for 5 full years, with a source and a fee statement, and with no disclaimer
- **THEN** R14 is `fail`, and R12a and R12b are `pass`

#### Scenario: Forecast is not past performance
- **WHEN** the only figure is in `W 2026 roku spodziewamy się 10% zysku.` and `fetched_at` is in 2026
- **THEN** R12a, R12b and R14 are `not_applicable`

#### Scenario: Past year range
- **WHEN** `Portfel 2021-2025: łączna stopa zwrotu 120%.` is analyzed with `fetched_at` in 2026
- **THEN** it is a past-performance sentence, and `Prognoza na lata 2026-2030: 8% rocznie.` is not

## ADDED Requirements

### Requirement: R5 risk exposure and contrast
R5 (ZASÓB "kontrastu, przesłonięcia przez inne elementy oraz czytelności") SHALL judge each viewport's risk blocks: a block fails when `visible` is `false` or its WCAG contrast ratio of `color` on `background_color` is below `min_contrast` (default 4.5). A viewport passes when one of its risk blocks passes. The worst viewport SHALL decide. R5 SHALL be `not_applicable` without `blocks` and never `pass` on unknown colours.

#### Scenario: Low contrast
- **WHEN** gold `m2-r5-low-contrast` is analyzed (risk text `#d0d0d0` on `#ffffff`)
- **THEN** R5 is `fail`, the explanation names the ratio and 4,5, and the evidence is the risk sentence with `evidence_locator.viewport` set

#### Scenario: Hidden warning
- **WHEN** every risk block of a viewport has `visible: false`
- **THEN** R5 is `fail`

#### Scenario: Readable warning
- **WHEN** the risk block is `#222222` on `#ffffff` on every viewport
- **THEN** R5 is `pass`

#### Scenario: Unknown colours
- **WHEN** the only visible risk block has `color: null` or `background_color: null`
- **THEN** R5 is `uncertain`

#### Scenario: No blocks or no risk information
- **WHEN** the document has no `blocks`, or blocks exist and none is a risk warning
- **THEN** R5 is `not_applicable`, with the explanation `brak informacji o ryzyku` in the second case

### Requirement: R7 one-click availability
R7 (ZASÓB "wymaga rozwinięcia, kliknięcia linku lub przejścia na inną warstwę") SHALL fail a viewport whose every risk block has `requires_interaction: true`, and pass it when one risk block has `requires_interaction: false`. The worst viewport SHALL decide. R7 SHALL be `not_applicable` without `blocks`, without a risk block, or when no risk block carries `requires_interaction`.

#### Scenario: Warning behind a click
- **WHEN** gold `m2-r7-risk-behind-click` is analyzed
- **THEN** R7 is `fail` with the risk sentence as evidence

#### Scenario: Warning on the page
- **WHEN** the risk block has `requires_interaction: false`
- **THEN** R7 is `pass`

#### Scenario: Missing interaction metadata
- **WHEN** every risk block has `requires_interaction: null`
- **THEN** R7 is `not_applicable` with the explanation `brak metadanych renderowania`
- **AND** when one viewport's risk blocks are all `true` or `null` with at least one `null`, R7 is `uncertain`

#### Scenario: No blocks
- **WHEN** the document has no `blocks`
- **THEN** R7 is `not_applicable`

### Requirement: R8 responsiveness
R8 (ZASÓB "czy tekst nie jest ucinany lub skalowany poniżej czytelności" on desktop, tablet and phone) SHALL fail a rendered viewport that has no visible risk block while another viewport has a risk block, or whose visible risk blocks are all clipped (`overflow_clipped: true`) or below `min_font_px` (default 12). The worst viewport SHALL decide. With one rendered viewport a clean result SHALL be `uncertain`. R8 SHALL be `not_applicable` without `blocks` or without a risk block.

#### Scenario: Missing on mobile
- **WHEN** gold `m2-r8-risk-missing-on-mobile` is analyzed (risk block on desktop only)
- **THEN** R8 is `fail` with `evidence_locator.viewport` `mobile`

#### Scenario: Too small to read
- **WHEN** the risk block is 9 px on mobile (gold `m2-r4-small-risk-font`)
- **THEN** R8 is `fail` and the explanation names 9 px and 12 px

#### Scenario: Clipped warning
- **WHEN** the only mobile risk block has `overflow_clipped: true`
- **THEN** R8 is `fail`

#### Scenario: Responsive warning
- **WHEN** the risk block is visible, unclipped and at least 12 px on desktop and mobile
- **THEN** R8 is `pass`

#### Scenario: One viewport only
- **WHEN** only desktop blocks exist and the risk block is readable
- **THEN** R8 is `uncertain`

#### Scenario: No blocks
- **WHEN** the document has no `blocks`
- **THEN** R8 is `not_applicable`

### Requirement: R13 dominance of past performance
R13 (ZASÓB "czy wyniki historyczne nie stanowią najbardziej wyeksponowanego elementu informacji") SHALL fail a viewport where a visible past-performance block has the largest font (ties included), or is the first block and above the length-weighted median font size. A block presents past performance when it holds a detector sentence or restates a return figure of one. The worst viewport SHALL decide.

#### Scenario: Headline restates a past return
- **WHEN** gold `m2-r13-past-performance-dominates` is analyzed (56 px `+120% w 5 lat!` restating `łączna stopa zwrotu 120%`)
- **THEN** R13 is `fail`, the evidence is `+120% w 5 lat!` and `evidence_locator.viewport` is set

#### Scenario: Past performance in body text
- **WHEN** gold `m2-r12-past-performance-compliant` is analyzed (past returns in an 18 px paragraph under a 32 px heading without figures)
- **THEN** R13 is `pass`

#### Scenario: No past performance
- **WHEN** the material has no past-performance sentence, or has no `blocks`
- **THEN** R13 is `not_applicable`
