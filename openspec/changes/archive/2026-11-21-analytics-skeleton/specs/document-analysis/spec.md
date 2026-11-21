# Spec Delta

## Purpose
Turn one scraped document into explainable, contract-valid findings, without any infrastructure, so the same pure function can later sit behind the Redis worker.

## ADDED Requirements

### Requirement: Lenient input, strict output
Analytics SHALL accept any document that has the required `ScrapedDocument` v1 fields (`.docs/integration-plan.md` §3) and ignore unknown fields. Every `Finding` it emits SHALL validate against `contracts/schemas/finding.schema.json` v1.

#### Scenario: Contract mocks are accepted
- **WHEN** each document in `contracts/mocks/documents.json` is parsed
- **THEN** parsing succeeds for all of them

#### Scenario: Unknown field is ignored
- **WHEN** a document carries an extra top-level field not in the v1 schema
- **THEN** it is parsed and the extra field is dropped

#### Scenario: Missing required field
- **WHEN** a document has no `text` or a malformed `fetched_at`
- **THEN** parsing raises a validation error naming the field and no finding is produced

#### Scenario: Output is contract-valid
- **WHEN** the pipeline produces findings for the mock documents
- **THEN** `python contracts/validate.py finding <output>` exits 0

### Requirement: Preprocessing
Analytics SHALL normalize text (Unicode NFKC, collapsed whitespace) and split it into sentences. It SHALL compute `content_hash` as sha256 of the normalized text and guess the language as `pl` or `en`. Evidence quotes SHALL still be exact substrings of the original `text`.

#### Scenario: Equivalent texts hash the same
- **WHEN** two texts differ only in whitespace runs or Unicode composition
- **THEN** their content hashes are equal

#### Scenario: Sentence split keeps legal forms
- **WHEN** the text is `Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE.`
- **THEN** it splits into three sentences and `S.A.` does not end a sentence

#### Scenario: Language guess
- **WHEN** the text is Polish marketing copy, and separately an English risk warning
- **THEN** the guesses are `pl` and `en`

#### Scenario: Empty text
- **WHEN** `text` is empty or whitespace only
- **THEN** the pipeline returns no findings and logs the reason `empty_text`

### Requirement: Firm registry matching
Analytics SHALL load registered firms from the CSV at `REGISTRY_CSV`. It SHALL match a document to at most one firm by name or alias in the text, by the page domain, or by a fuzzy name match. The match SHALL have a confidence in 0-1.

#### Scenario: Name without legal form
- **WHEN** the text mentions `Alfa Inwestycje` and the registry holds `Alfa Inwestycje Dom Maklerski S.A.`
- **THEN** that firm is matched with confidence at least 0.9

#### Scenario: Domain match
- **WHEN** the document URL host is a subdomain of a firm's `website_domains` and its name is absent from the text
- **THEN** that firm is matched with confidence at least 0.8

#### Scenario: No match
- **WHEN** no name, alias, domain or fuzzy candidate reaches the threshold
- **THEN** no firm is matched

#### Scenario: Registry file missing or malformed
- **WHEN** `REGISTRY_CSV` points to a missing file or a file without the required columns
- **THEN** startup fails with an error naming the file, never silently with an empty registry

### Requirement: Routing to modules
Analytics SHALL run M2 for documents with `source_kind` `firm_own`. In this change it SHALL skip `third_party` and `unknown` documents with a logged reason, because M1 and M3 do not exist yet.

#### Scenario: Firm's own page
- **WHEN** a `firm_own` document is analyzed
- **THEN** exactly one M2 finding is returned

#### Scenario: Third-party post
- **WHEN** a `third_party` document is analyzed
- **THEN** no finding is returned and the log names the reason `module_not_implemented`

### Requirement: M2 finding assembly
The M2 finding SHALL list only the results of implemented rules. It SHALL carry the raw `score` (never `risk_level`), the matched firm (or `null`), a Polish title and summary, `status: new`, the `url` and `platform` copied from the document, `content_excerpt` of at most 500 characters, and `model.llm = null`. The score SHALL be `Σ(weight·fail) / Σ(weight·applicable)` with weights high 3, medium 2, low 1, where `uncertain` counts as half a fail and `not_applicable` is excluded. The score is 0 when no rule applies.

#### Scenario: Violating landing page
- **WHEN** the mock document `m2-alfa-landing` (id `a3c88321-…`) is analyzed
- **THEN** the finding has R1 `pass`, R2 `fail`, R3 `fail` and a score above 0.5

#### Scenario: Compliant material
- **WHEN** the mock document `m2-bank-ok` (id `5030107e-…`) is analyzed
- **THEN** no rule result is `fail` and the score is 0

#### Scenario: Unmatched firm on its own page
- **WHEN** a `firm_own` document matches no registry firm
- **THEN** the finding has `firm: null` and R1 `fail`
