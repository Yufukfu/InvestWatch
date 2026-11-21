## MODIFIED Requirements

### Requirement: Deduplicate by content hash
The scraper SHALL compute `content_hash` as the sha256 (lowercase hex, of the UTF-8 bytes) of the normalised text (Unicode NFC, every run of whitespace collapsed to one space, leading and trailing whitespace removed; case is preserved; compatibility characters such as ligatures, superscripts and full-width forms are NOT folded, which NFKC would do) and SHALL NOT insert a second document with the same `content_hash` for the same `source_id`.

#### Scenario: Rerun of unchanged page
- **WHEN** the same page is collected twice with identical text
- **THEN** `documents` holds one row for it and no second stream event is published

#### Scenario: Whitespace-only difference
- **WHEN** two pages have the texts `"Zysk  do 20%\n"` and `"Zysk do 20%"`
- **THEN** both have `content_hash` equal to the sha256 of `Zysk do 20%`

#### Scenario: Case difference
- **WHEN** two pages differ only in letter case
- **THEN** their `content_hash` values differ

#### Scenario: Changed page
- **WHEN** the page text changes between two runs
- **THEN** a second row is inserted with a different `content_hash`

#### Scenario: Duplicate leaves no stray object
- **WHEN** an unchanged page is collected again and the document is a duplicate
- **THEN** no object is added to `iw-raw` (any object uploaded before the duplicate was detected is removed)

#### Scenario: Insert fails for another reason
- **WHEN** the HTML was uploaded and the insert then fails with an error other than a duplicate
- **THEN** a job error with reason `storage_error` is recorded, and the uploaded object is removed if the insert certainly did not commit; if the insert may have committed (a dropped connection, a timeout, a cancellation) the object is kept and logged as `possible_orphan`, so that no document row points at a missing object

#### Scenario: Compatibility characters are kept
- **WHEN** a page has the text `"ﬁnanse"`, `"m²"` or `"１２３%"` (ligature, superscript, full-width digits)
- **THEN** its `content_hash` is the sha256 of exactly that text, which differs from the hash of `"finanse"`, `"m2"` or `"123%"`

#### Scenario: Canonically equivalent text
- **WHEN** two pages differ only in composed versus decomposed form (`"é"` and `"é"`)
- **THEN** their `content_hash` values are equal
