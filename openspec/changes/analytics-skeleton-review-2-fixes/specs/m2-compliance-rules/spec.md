## MODIFIED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, a legal basis, its dictionaries and an `implemented` flag. Only implemented rules SHALL run. Loading SHALL validate every rule parameter the rules read (pattern lists and `negation_before` compile, `window` and `prominent_sentences` are non-negative integers, `labels` and `footnote_markers` are lists of strings) and the YAML root SHALL be a mapping, so a bad catalogue fails at load and never on the first document.

#### Scenario: Catalogue is complete
- **WHEN** the catalogue is loaded
- **THEN** it holds 19 entries whose ids match the contract `rule_id` pattern, and exactly R1, R2 and R3 are implemented

#### Scenario: Malformed catalogue
- **WHEN** an entry has an unknown severity or a duplicate id
- **THEN** loading fails with an error naming the entry

#### Scenario: Bad rule parameter
- **WHEN** `negation_before` is not a valid regex, or `prominent_sentences` is not an integer, or the root is a list
- **THEN** loading fails with a catalogue error naming the rule or the file

### Requirement: R2 ad labeling
R2 SHALL pass when the text contains an advertising label from its dictionary (for example `reklama`, `materiał marketingowy`, `informacja promocyjna`, `#reklama`), case-insensitively, in a prominent place: a hashtag label anywhere, or any label in the first or last two sentences. It SHALL quote the label. A label found only elsewhere SHALL give `uncertain` with that label as evidence. A label negated on the same line (`to nie jest reklama`, `nie reklama`, `not an ad`) SHALL NOT count; a hashtag label is never negated. Without a counting label it SHALL fail with null evidence. `nie tylko`, `jedynie`, `only`, `just` between the negation and the label cancel the negation (`to nie tylko reklama`).

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

#### Scenario: Negation on the previous line
- **WHEN** the text is a headline `Nie czekaj` and the next line is `Reklama`
- **THEN** R2 is `pass`

#### Scenario: Label buried mid-text
- **WHEN** the only label is in the third of six sentences and is not a hashtag
- **THEN** R2 is `uncertain` with the label as evidence

#### Scenario: Not only an ad
- **WHEN** the text is `To nie tylko reklama – to Twoja szansa.`
- **THEN** R2 is `pass`

### Requirement: R3 risk information next to return claims
R3 SHALL be `not_applicable` when the text makes no return claim (percent figures, or return vocabulary such as `zysk`, `zarob…`, `stopa zwrotu`). It SHALL pass when every return-claim sentence has a risk warning within the configured sentence window (default ±2). Otherwise it SHALL fail, quoting the first uncovered claim. A warning marked as a footnote (leading `*` or `¹`) SHALL NOT count as next to the claim. A loss denial (`bez ryzyka`, `nie stracisz`) SHALL NOT count as a warning, but a negated exclusion of loss (`nie jest wykluczona utrata`, `nie można wykluczyć straty`, `nie gwarantujemy braku strat`) SHALL. An affirmed exclusion (`wykluczamy straty`, `nie tylko wyklucza straty`, `gwarantujemy brak straty`) is a denial. A denial SHALL NOT swallow a warning that follows it: `bez opłat ryzyko utraty kapitału` still counts as a warning.

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

#### Scenario: Denial word before a warning
- **WHEN** `Zysk 10% rocznie, bez opłat ryzyko utraty kapitału.`
- **THEN** R3 is `pass`
