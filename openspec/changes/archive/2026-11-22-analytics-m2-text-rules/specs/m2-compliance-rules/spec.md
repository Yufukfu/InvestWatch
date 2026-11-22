## MODIFIED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, the legal basis that ZASÓB gives it, its dictionaries, an `implemented` flag and an optional `llm:` block (see `llm-analysis`). Only implemented rules SHALL run. Shared dictionaries MAY be written once with YAML anchors.

#### Scenario: Catalogue is complete
- **WHEN** the catalogue is loaded
- **THEN** it holds 19 entries whose ids match the contract `rule_id` pattern, and exactly R1, R2, R3, R4, R6, R9, R10, R11, R12a, R12b, R14, R15, R16, R17 and R18 are implemented

#### Scenario: LLM-refined rules declare it
- **WHEN** the catalogue is loaded
- **THEN** R3, R9, R11, R12a, R15, R17 and R18 have an `llm:` block and no other M2 entry has one

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

### Requirement: R10 language consistency
R10 SHALL fail, quoting the first risk warning, when every risk warning has a known language and none is in the language of the main message (ZASÓB R10; art. 44 ust. 2 lit. f). It SHALL pass when at least one warning is in the main language, be `uncertain` when a language is unknown and no warning matches, and be `not_applicable` with `brak informacji o ryzyku` without a warning. R10 is rules-only.

#### Scenario: English warning on a Polish ad
- **WHEN** the `eurotrade` text is analyzed (Polish copy, `Risk warning: CFDs are complex instruments …`)
- **THEN** R10 is `fail` with the English warning as evidence and `method` `rule`

#### Scenario: Polish warning on a Polish ad
- **WHEN** the `m2-bank-ok` mock is analyzed
- **THEN** R10 is `pass`

#### Scenario: Bilingual warning
- **WHEN** a Polish ad has a Polish warning and an extra English one
- **THEN** R10 is `pass` with the Polish warning as evidence

#### Scenario: No warning
- **WHEN** the material has no risk warning
- **THEN** R10 is `not_applicable` and its explanation says `brak informacji o ryzyku`

#### Scenario: English legal block does not set the main language
- **WHEN** a document's `blocks` hold a Polish headline and body, a long English block with `region: legal`, and a Polish warning
- **THEN** the main language is `pl` and R10 is `pass`

#### Scenario: Unknown language
- **WHEN** the only warning is `Ryzyko!`
- **THEN** R10 is `uncertain`

### Requirement: R9 comprehensibility of the risk warning
R9 SHALL judge whether the risk warning is written in language an average member of the target group understands (ZASÓB R9; art. 44 ust. 2 lit. d). Rules-only, a raised signal SHALL give `uncertain` quoting the warning with the most jargon, no signal SHALL give `pass`, and R9 SHALL never fail. Without a warning R9 SHALL be `not_applicable` with `brak informacji o ryzyku`.

#### Scenario: Jargon-heavy warning, rules-only
- **WHEN** the warning is `Ekspozycja na ryzyko bazowe instrumentu implikuje asymetryczny profil wypłaty, a zmienność implikowana i ryzyko kredytowe kontrahenta mogą skutkować deprecjacją wartości rynkowej poniżej poziomu partycypacji.` and no judge is configured
- **THEN** R9 is `uncertain` with that sentence as evidence and the explanation names the jargon hits

#### Scenario: Plain warning
- **WHEN** the warning is `Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału.`, or the standard CFD warning
- **THEN** R9 is `pass` and the LLM is not asked

### Requirement: R10 main language
The main language SHALL be the length-weighted majority language of the visible non-`footer`, non-`legal`, non-warning blocks of the `desktop` viewport (else the first viewport present) when the document has `blocks`, otherwise of the non-warning sentences with a known language, falling back to the document guess.

#### Scenario: Main language from body sentences
- **WHEN** a document without `blocks` has two Polish body sentences and one English warning
- **THEN** the main language is `pl`

### Requirement: R9 rules signal
The R9 signal SHALL be raised over the warning sentences when their average length in words is above `max_avg_sentence_words`, their jargon share (hits from `jargon_patterns` per word) is at least `max_jargon_share`, or they have at least `min_jargon_hits` jargon hits. The explanation SHALL state the three measurements.

#### Scenario: Long warning sentence
- **WHEN** the only warning has more than `max_avg_sentence_words` words and no jargon
- **THEN** R9 is `uncertain`

### Requirement: R9 LLM rating
R9's `llm:` block (`when: uncertain`) SHALL ask for a 1-5 rating stated as `Ocena: N/5` with a verbatim quote. R9 SHALL be `fail` only when the model answers `fail` with a rating of 2 or lower and a verified quote, and `pass` from the model only with a rating of 4 or higher; any other answer SHALL be `uncertain`.

#### Scenario: Model rates the warning incomprehensible
- **WHEN** the jargon warning is deferred and the model answers `fail`, quoting the warning, with `Ocena: 1/5`
- **THEN** R9 is `fail` with `method` `hybrid`

#### Scenario: Model fails without a low rating
- **WHEN** the model answers `fail` with `Ocena: 3/5`, or with no rating
- **THEN** R9 is `uncertain`

#### Scenario: Model quote not in the document
- **WHEN** the model answers `fail` with `Ocena: 1/5` and a quote that is not in the text
- **THEN** R9 is `uncertain` and has no evidence

#### Scenario: No warning
- **WHEN** the material has no risk warning
- **THEN** R9 is `not_applicable` with `brak informacji o ryzyku`
