# Spec Delta

## Purpose
Load saved samples (pages and texts handed out at the hackathon, or saved earlier) into the system through the normal ingest, with no network access, so they flow to analytics and the dashboard like scraped documents.

## ADDED Requirements

### Requirement: Import samples through the normal ingest
The scraper SHALL provide a command that reads every supported file of a directory and ingests each as a `ScrapedDocument` through the same validation, dedup, raw-HTML upload, insert and `iw:documents` announcement as a scraped page. It SHALL make no network request other than to PostgreSQL, Redis and MinIO.

#### Scenario: HTML sample
- **WHEN** a directory holds `oferta.html` and the command runs with its source settings
- **THEN** one `documents` row exists whose `text`, `title`, `canonical_url` and `links` equal what `parse_page` gives for that file, `html/{document_id}.html` exists in `iw-raw`, and `iw:documents` received the document id

#### Scenario: HTML sample without a declared charset
- **WHEN** an `.html` file is valid UTF-8 and has no `<meta charset>`
- **THEN** its `text` equals what `parse_page` gives for the same bytes as a fetched page (`charset=utf-8`), so Polish letters are kept; a file that is not valid UTF-8 is decoded by its `<meta charset>`

#### Scenario: Text sample
- **WHEN** a directory holds a plain-text file (`post.txt`) or a Markdown file (extension md)
- **THEN** one document is ingested whose `text` is the file content, with a non-blank `html` stored for it

#### Scenario: Unsupported file
- **WHEN** the directory holds `skan.pdf`
- **THEN** it is not ingested, the summary lists it as skipped, and the exit code is unaffected by it

#### Scenario: Files that are not samples
- **WHEN** the directory holds `samples.toml` and dotfiles such as `.DS_Store`
- **THEN** none of them is read, ingested or reported as skipped

#### Scenario: Rerun
- **WHEN** the same directory is imported twice
- **THEN** the second run inserts no row, publishes no event and reports every file as duplicate

### Requirement: Describe a sample set with an optional manifest
The command SHALL read `samples.toml` when present, with set-level defaults and per-file overrides for `name`, `url`, `source_kind`, `platform`, `target_modules`, `title`, `lang`, `published_at` and `author`, and SHALL validate every value against the contract before ingesting anything. Without a manifest it SHALL require `--kind` and `--modules` and SHALL NOT infer them from file names or content.

#### Scenario: Per-file override
- **WHEN** the manifest sets `source_kind = "third_party"` for the set and `source_kind = "firm_own"` for `xtb.html`
- **THEN** the document from `xtb.html` has `source_kind = firm_own` and the others `third_party`, each with `source_id` of the set's source

#### Scenario: Invalid manifest
- **WHEN** the manifest has `source_kind = "bank"`, an unparsable `published_at` or a `lang` that is not two lowercase letters
- **THEN** nothing is ingested, no `sources` row is created, the error names the key and the command exits non-zero

#### Scenario: Manifest entry for a missing file
- **WHEN** the manifest has an entry for `xtb.htm` and the directory holds only `xtb.html`
- **THEN** nothing is ingested, no `sources` row is created, the error names `xtb.htm` and the command exits non-zero

#### Scenario: No manifest and no routing flags
- **WHEN** the command runs on a directory without `samples.toml` and without `--kind` or `--modules`
- **THEN** it refuses with a usage error and ingests nothing

### Requirement: Take the author only from the manifest
The command SHALL set `author` on a document only from the manifest, passed through the `author` argument of the ingest and never through the page dict, and SHALL NOT derive it from a file's content or markup. A manifest author is supplied by the operator, not verified by a platform.

#### Scenario: Author in markup
- **WHEN** an HTML sample carries `<meta name="author" content="Jan">` and the manifest gives no author
- **THEN** the document has no `author`

#### Scenario: Author in the manifest
- **WHEN** the manifest gives `author = { name = "X", handle = "@x", profile_url = "https://example.com/x" }` for a file
- **THEN** that document's `author` equals it

### Requirement: Register the sample set as an inactive source
The command SHALL ensure one `sources` row for the set (matched by URL, never updated if present) with `active = false` and no `schedule_cron`, so that the scheduler and the collector never select it. Document URLs SHALL be the sample's own `url` when given, else `https://sample.invalid/{set}/{file}`, because the stored schema accepts only http(s) URLs.

#### Scenario: Source is never collected
- **WHEN** the set has been imported
- **THEN** its source row has `active = false` and `schedule_cron` NULL, and it is absent from the collectable sources

#### Scenario: Set name to URL
- **WHEN** the directory is named `Próbki UKNF 1` and the manifest gives no `url`
- **THEN** the source URL is `https://sample.invalid/pr-bki-uknf-1`, a valid http(s) URL

#### Scenario: Known set
- **WHEN** a source with the set's URL already exists
- **THEN** no second row is created and its fields are left unchanged

### Requirement: Isolate per-file failures
A file that cannot be read, decoded, parsed or validated SHALL be recorded as a `job_errors` row with a reason of the closed set and SHALL NOT stop the remaining files. The command SHALL log, as JSON on stdout, one line per file (file name, outcome, and the `document_id` when inserted) and one summary of counts (inserted, duplicate, skipped, failed), and SHALL exit non-zero when any file failed.

#### Scenario: Empty text
- **WHEN** one file of three has no text after parsing
- **THEN** the other two are ingested, a job error with reason `empty_text` is recorded for the empty one, the summary reads `inserted 2, duplicate 0, skipped 0, failed 1` and the exit code is non-zero

#### Scenario: Report for labelling
- **WHEN** a file is inserted
- **THEN** its log line carries the file name and the new `document_id`, so a label can be attached to that document

#### Scenario: Undecodable file
- **WHEN** a `.txt` file is not valid UTF-8
- **THEN** it is recorded as a failed file with reason `parse_error` and the run continues

### Requirement: Treat the directory as untrusted
The command SHALL read only regular files directly inside the given directory (no recursion, no symlink followed), SHALL refuse a file larger than `FETCH_MAX_BYTES`, SHALL never execute or fetch anything it reads (links are stored as pointers only), and SHALL NOT log file content or absolute paths in error details.

#### Scenario: Symlink out of the directory
- **WHEN** the directory holds a symlink to `/etc/passwd` named `x.txt`
- **THEN** it is not read and is reported as skipped

#### Scenario: Oversized file
- **WHEN** a file is larger than `FETCH_MAX_BYTES`
- **THEN** it is recorded as failed with reason `parse_error` and the next file is processed
