## MODIFIED Requirements

### Requirement: Firm registry matching
Analytics SHALL load registered firms from the CSV at `REGISTRY_CSV`. It SHALL match a document to at most one firm by name or alias in the text, by the page domain, or by a fuzzy name match. The match SHALL have a confidence in 0-1. When the page host is a registered firm's domain, that firm SHALL be matched even if the text names another firm. Among equally confident name matches, the firm whose name or alias appears first in the text SHALL win, then the one with the longest quote. The fuzzy match SHALL tokenize the firm name the same way as the text, so punctuation inside a name (`Alfa-Beta`) does not lower the ratio, and a name with no word tokens SHALL never fuzzy-match. When the registry file cannot be read, the error SHALL tell the operator to set `REGISTRY_CSV`.

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

#### Scenario: No match
- **WHEN** no name, alias, domain or fuzzy candidate reaches the threshold
- **THEN** no firm is matched

#### Scenario: Registry file missing or malformed
- **WHEN** `REGISTRY_CSV` points to a missing file or a file without the required columns
- **THEN** startup fails with an error naming the file, never silently with an empty registry

#### Scenario: Hyphenated firm name
- **WHEN** the registry holds `Alfa-Beta Inwestycje S.A.` and the text says `Alfa-Beta Inwestycji`
- **THEN** that firm is matched by fuzzy match

#### Scenario: Registry path not set
- **WHEN** `REGISTRY_CSV` points to a missing file
- **THEN** the error names the file and `REGISTRY_CSV`

### Requirement: Command-line batch
The CLI SHALL validate each document of a batch on its own. An invalid document SHALL be logged with its index and the error locations and types, without input values, and skipped. The CLI SHALL exit 2 without writing to stdout when the input has documents and none is valid, or on unreadable input or bad configuration. If analyzing a valid document raises, the CLI SHALL log the document id and the exception type (no input values), skip that document, still write the findings of the others, and exit 1. A catalogue whose root is not a mapping SHALL be bad configuration (exit 2).

#### Scenario: One bad document in a batch
- **WHEN** a list holds one valid document and one without `text`
- **THEN** the CLI exits 0 with the finding of the valid document and logs the skipped index

#### Scenario: Nothing valid
- **WHEN** every document in the list is invalid
- **THEN** the CLI exits 2 and writes nothing to stdout

#### Scenario: Log carries no document content
- **WHEN** an invalid document is logged
- **THEN** the log line does not contain the document's field values

#### Scenario: Analysis fails for one document
- **WHEN** a batch holds two valid documents and analyzing the first raises an unexpected error
- **THEN** the CLI writes the second document's finding, logs the first document's id and the exception type, and exits 1
