## MODIFIED Requirements

### Requirement: Firm registry matching
Analytics SHALL load registered firms from the CSV at `REGISTRY_CSV`. It SHALL match a document to at most one firm by name or alias in the text, by the page domain, or by a fuzzy name match. The match SHALL have a confidence in 0-1. When the page host is a registered firm's domain, that firm SHALL be matched even if the text names another firm. When the registry file cannot be read, the error SHALL tell the operator to set `REGISTRY_CSV`.

#### Scenario: Name without legal form
- **WHEN** the text mentions `Alfa Inwestycje` and the registry holds `Alfa Inwestycje Dom Maklerski S.A.`
- **THEN** that firm is matched with confidence at least 0.9

#### Scenario: Domain match
- **WHEN** the document URL host is a subdomain of a firm's `website_domains` and its name is absent from the text
- **THEN** that firm is matched with confidence at least 0.8

#### Scenario: Own domain beats another firm's name
- **WHEN** a page on `alfa-inwestycje.example.com` mentions only `Bank Przykładowy`
- **THEN** the Alfa firm is matched by domain

#### Scenario: Earliest name wins a tie
- **WHEN** a page on no registered domain names two registry firms
- **THEN** the firm named first in the text is matched, even if its full legal name appears only later
- **AND** among equally confident name matches, the firm whose name or alias appears first in the text SHALL win, then the one with the longest quote

#### Scenario: No match
- **WHEN** no name, alias, domain or fuzzy candidate reaches the threshold
- **THEN** no firm is matched

#### Scenario: Registry file missing or malformed
- **WHEN** `REGISTRY_CSV` points to a missing file or a file without the required columns
- **THEN** startup fails with an error naming the file, never silently with an empty registry

#### Scenario: Hyphenated firm name
- **WHEN** the registry holds `Alfa-Beta Inwestycje S.A.` and the text says `Alfa-Beta Inwestycji`
- **THEN** that firm is matched by fuzzy match
- **AND** the fuzzy match SHALL tokenize the firm name the same way as the text, so punctuation inside a name (`Alfa-Beta`) does not lower the ratio

#### Scenario: Firm name without word tokens
- **WHEN** a registry firm's name has no word tokens
- **THEN** that name SHALL never fuzzy-match

#### Scenario: Registry path not set
- **WHEN** `REGISTRY_CSV` points to a missing file
- **THEN** the error names the file and `REGISTRY_CSV`

### Requirement: M2 finding assembly
The M2 finding SHALL list only the results of implemented rules. It SHALL carry the raw `score` (never `risk_level`), the matched firm (or `null`), a Polish title and summary, `status: new`, the `url` and `platform` copied from the document, `content_excerpt` of at most 500 characters, and `model.llm = null`. The score SHALL be `Σ(weight·fail) / Σ(weight·applicable)` with weights high 3, medium 2, low 1, where `uncertain` counts as half a fail and `not_applicable` is excluded.

#### Scenario: Violating landing page
- **WHEN** the mock document `m2-alfa-landing` (id `a3c88321-…`) is analyzed
- **THEN** the finding has R1 `pass`, R2 `fail`, R3 `fail` and a score above 0.5

#### Scenario: Compliant material
- **WHEN** the mock document `m2-bank-ok` (id `5030107e-…`) is analyzed
- **THEN** no rule result is `fail` and the score is 0

#### Scenario: Unmatched firm on its own page
- **WHEN** a `firm_own` document matches no registry firm
- **THEN** the finding has `firm: null` and R1 `fail`

#### Scenario: Rule that does not apply
- **WHEN** R3 is `not_applicable`
- **THEN** the summary does not list R3 among the checked rules and says it does not apply
- **AND** the summary SHALL name as checked only the rules that applied, and name `not_applicable` rules separately
- **AND** the score is 0 when no rule applies

### Requirement: Command-line batch
The CLI SHALL validate each document of a batch on its own. An invalid document SHALL be logged with its index and the error locations and types, without input values, and skipped. The CLI SHALL exit 2 without writing to stdout when the input has documents and none is valid. If analyzing a valid document raises, the CLI SHALL log the document id and the exception type (no input values), skip that document, still write the findings of the others, and exit 1.

#### Scenario: One bad document in a batch
- **WHEN** a list holds one valid document and one without `text`
- **THEN** the CLI exits 0 with the finding of the valid document and logs the skipped index

#### Scenario: Nothing valid
- **WHEN** every document in the list is invalid
- **THEN** the CLI exits 2 and writes nothing to stdout

#### Scenario: Unreadable input or bad configuration
- **WHEN** the input cannot be read, or the configuration is bad
- **THEN** the CLI SHALL exit 2 without writing to stdout
- **AND** a catalogue whose root is not a mapping SHALL be bad configuration (exit 2)

#### Scenario: Log carries no document content
- **WHEN** an invalid document is logged
- **THEN** the log line does not contain the document's field values

#### Scenario: Analysis fails for one document
- **WHEN** a batch holds two valid documents and analyzing the first raises an unexpected error
- **THEN** the CLI writes the second document's finding, logs the first document's id and the exception type, and exits 1
