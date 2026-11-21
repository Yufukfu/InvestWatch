## MODIFIED Requirements

### Requirement: Preprocessing
Analytics SHALL normalize text (Unicode NFKC, collapsed whitespace) and split it into sentences. It SHALL compute `content_hash` as sha256 of the normalized text and guess the language as `pl` or `en`. Evidence quotes SHALL still be exact substrings of the original `text`. Legal forms, titles and `<year> r.` SHALL NOT end a sentence; abbreviations that are also ordinary words (`ok.`, `tel.`, `art.` and similar) SHALL end one unless a digit follows, directly or after an opening bracket or quote.

#### Scenario: Equivalent texts hash the same
- **WHEN** two texts differ only in whitespace runs or Unicode composition
- **THEN** their content hashes are equal

#### Scenario: Sentence split keeps legal forms
- **WHEN** the text is `Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE.`
- **THEN** it splits into three sentences and `S.A.` does not end a sentence

#### Scenario: Ordinary word that is also an abbreviation
- **WHEN** the text is `Wszystko jest ok. Zysk 15% rocznie.`
- **THEN** it splits into two sentences, while `Zysk wynosi ok. 15% rocznie.` stays one

#### Scenario: Language guess
- **WHEN** the text is Polish marketing copy, and separately an English risk warning
- **THEN** the guesses are `pl` and `en`

#### Scenario: Language per sentence
- **WHEN** the `eurotrade` mock text is preprocessed
- **THEN** the sentence starting `Nasi klienci zarobili` is `pl` and the sentence starting `Risk warning:` is `en`
- **AND** each sentence SHALL carry its own language guess (`pl`, `en`, or none when it gives too little signal, for example fewer than three language markers)

#### Scenario: Too short to guess
- **WHEN** a sentence is `Ryzyko!`
- **THEN** its language guess is none

#### Scenario: Empty text
- **WHEN** `text` is empty or whitespace only
- **THEN** the pipeline returns no findings and logs the reason `empty_text`

### Requirement: M2 finding assembly
The M2 finding SHALL list only the results of implemented rules. It SHALL carry the raw `score` (never `risk_level`), the matched firm (or `null`), a Polish title and summary, `status: new`, the `url` and `platform` copied from the document, `content_excerpt` of at most 500 characters, and `model.llm`. The score SHALL be `Σ(weight·fail) / Σ(weight·applicable)` with weights high 3, medium 2, low 1, where `uncertain` counts as half a fail and `not_applicable` is excluded.

#### Scenario: Violating landing page
- **WHEN** the mock document `m2-alfa-landing` (id `a3c88321-…`) is analyzed rules-only
- **THEN** the finding has R1 `pass`, R2 `fail`, R3 `fail`, R4 `fail`, R6 `fail`, R18 `fail` and a score above 0.5

#### Scenario: Compliant material
- **WHEN** the mock document `m2-bank-ok` (id `5030107e-…`) is analyzed
- **THEN** no rule result is `fail`, R4 and R6 are `not_applicable`, and the score is 0

#### Scenario: Unmatched firm on its own page
- **WHEN** a `firm_own` document matches no registry firm
- **THEN** the finding has `firm: null` and R1 `fail`

#### Scenario: Rule that does not apply
- **WHEN** R3 is `not_applicable`
- **THEN** the summary does not list R3 among the checked rules and says it does not apply
- **AND** the summary SHALL name as checked only the rules that applied, and name `not_applicable` rules separately
- **AND** when no rule applies (every rule is `not_applicable`), the score is 0

#### Scenario: LLM used
- **WHEN** `m2-alfa-landing` is analyzed with a stub judge whose valid R17 verdict is merged and `LLM_MODEL=gemma3:4b`
- **THEN** `model.llm` is `gemma3:4b` and the summary names the model and R17
- **AND** `model.llm` SHALL be the configured `LLM_MODEL` only when at least one rule result of the finding has `method` `llm` or `hybrid`

#### Scenario: LLM configured but not used
- **WHEN** the judge is configured and the endpoint is down
- **THEN** `model.llm` is `null` and the summary says the check ran rules-only
- **AND** `model.llm` SHALL be `null` whenever the LLM is disabled, nothing was deferred, or the LLM failed
