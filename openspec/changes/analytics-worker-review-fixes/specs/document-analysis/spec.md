# Spec Delta

## ADDED Requirements

### Requirement: Linear time on hostile text
Preprocessing and the rules-only checks SHALL run in time linear in the length of the text, because scraped text is untrusted. No regular expression on the analysis path may backtrack over a whitespace run, a digit run or a growing sentence prefix. Sentence boundaries and their offsets into the original text SHALL be the same as before for ordinary text.

#### Scenario: Long whitespace run
- **WHEN** the text is `"."` followed by 50 000 spaces, or `". "` + 40 000 spaces + `abc`
- **THEN** sentence splitting finishes in under a second

#### Scenario: Abbreviation chain
- **WHEN** the text repeats `S.A. Ab ` or `ok. 1 ` thousands of times
- **THEN** sentence splitting finishes in under a second, and `S.A.` still never ends a sentence

#### Scenario: Long digit run
- **WHEN** the text contains 50 000 digits with no `%`
- **THEN** the full M2 analysis finishes in under three seconds, and `Zarabiaj 12,5 % rocznie` is still an R3 claim

#### Scenario: Footnote marker followed by spaces
- **WHEN** a sentence ends and the next starts with `*` or `(*)` followed by up to three spaces and a capital
- **THEN** a new sentence starts at the marker
