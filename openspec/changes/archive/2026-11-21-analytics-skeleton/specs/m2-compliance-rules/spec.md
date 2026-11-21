# Spec Delta

## Purpose
Check investment-firm marketing material against the 18 UKNF rules (Art. 44 of Delegated Regulation (EU) 2017/565), deterministically first, each result explainable by an exact quote.

## ADDED Requirements

### Requirement: Rule catalogue
The rule engine SHALL load the catalogue of all 18 UKNF rules (R1-R18, with R12a/R12b) from `m2_rules.yaml`. Each entry has a Polish name, a severity, a legal basis, its dictionaries and an `implemented` flag. Only implemented rules SHALL run.

#### Scenario: Catalogue is complete
- **WHEN** the catalogue is loaded
- **THEN** it holds 19 entries whose ids match the contract `rule_id` pattern, and exactly R1, R2 and R3 are implemented

#### Scenario: Malformed catalogue
- **WHEN** an entry has an unknown severity or a duplicate id
- **THEN** loading fails with an error naming the entry

### Requirement: Evidence is an exact quote
Every rule result with non-null `evidence` SHALL quote a substring of the document's original `text`. Each result SHALL carry `method: rule`, the catalogue's name, severity and legal basis, and a Polish explanation.

#### Scenario: Evidence check
- **WHEN** R1-R3 run on every mock document
- **THEN** each non-null `evidence` is found verbatim in that document's `text`

### Requirement: R1 firm identification
R1 SHALL pass when the name or an alias of the matched registry firm appears in the text, quoting it. It SHALL fail when no registry firm is matched or its name is absent from the text.

#### Scenario: Name present
- **WHEN** the text contains `Konto Premium Alfa Inwestycje` and the Alfa firm is matched
- **THEN** R1 is `pass` with evidence `Alfa Inwestycje`

#### Scenario: Matched by domain only
- **WHEN** the firm was matched only by the page domain and its name is absent from the text
- **THEN** R1 is `fail`

### Requirement: R2 ad labeling
R2 SHALL pass when the text contains an advertising label from its dictionary (for example `reklama`, `materiał marketingowy`, `informacja promocyjna`, `#reklama`), case-insensitively, quoting the label. Otherwise it SHALL fail with null evidence.

#### Scenario: Labeled material
- **WHEN** the text starts with `Reklama.`
- **THEN** R2 is `pass` with evidence `Reklama`

#### Scenario: Unlabeled material
- **WHEN** the text contains no label from the dictionary
- **THEN** R2 is `fail`

#### Scenario: Label inside another word
- **WHEN** the only occurrence is inside a longer word such as `reklamacja`
- **THEN** R2 is `fail`

### Requirement: R3 risk information next to return claims
R3 SHALL be `not_applicable` when the text makes no return claim (percent figures, or return vocabulary such as `zysk`, `zarob…`, `stopa zwrotu`). It SHALL pass when every return-claim sentence has a risk warning within the configured sentence window (default ±2). Otherwise it SHALL fail, quoting the first uncovered claim. A warning marked as a footnote (leading `*` or `¹`) SHALL NOT count as next to the claim.

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
