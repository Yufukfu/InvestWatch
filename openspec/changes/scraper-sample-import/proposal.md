# Proposal

## Why

The challenge brief (section 7) says sample data is handed out during the hackathon (a pendrive at the UKNF stand), and the jury (section 6) judges scraping success, classification accuracy and the calibration panel on a demo. Today the only way to get a document into the system is a live fetch of a seeded URL, so the samples cannot be fed in, the calibration gold set (the panel's FP/FN effect, brief section 3) has no documents to point at, and a demo depends on live sites, proxies and the venue's network. `scraper-stack` lists "sample import" as out of scope, and no other change owns it.

## What Changes

- A command `python -m iw_scraper.sample_import <dir>` (a module of its own, like `iw_scraper.seed`) that reads saved samples from a directory and sends each through the existing `Ingestor`: validation, dedup by `content_hash`, raw HTML in MinIO, a `documents` row, `XADD iw:documents`. Analytics and the dashboard see an imported document exactly like a scraped one.
- Readable sample files: `.html`/`.htm` (parsed with the same `parse_page` as a live page, so text and links match what a fetch would produce), `.txt` and `.md` (the file is the text). Other extensions are skipped and reported, not guessed. A reader is chosen by extension, so PDF or DOCX can be added once the real samples are seen.
- An optional `samples.toml` next to the files sets, for the whole set and per file: `name`, `url`, `source_kind`, `platform`, `target_modules`, `title`, `lang`, `published_at`, `author` (the data each module's report needs: advertiser, text, exact URL). Without it the CLI requires `--kind` and `--modules` (`platform` defaults to `web`), so nothing is routed by a guess.
- One `sources` row per sample set (created if its URL is not there yet, never updated), `active = false` and no schedule, so the scheduler and the collector never fetch it and the dashboard lists it as a source with its documents.
- Idempotent: running the same directory twice inserts nothing the second time (dedup by `content_hash` per source).
- A per-file failure (unreadable, empty text, schema-invalid) becomes a `job_errors` row and does not stop the rest; the command logs one JSON line per file (file name, outcome, `document_id` when inserted, so Damian can label the gold set) and one summary line, and exits non-zero when any file failed. Logs go through the scraper's JSON logger: no `print`, no `console.log`-style output, which the jury checks.
- `author` comes only from the manifest, written by the operator who knows the account; it is never read from a file's content or markup (the author-provenance rule, `.docs/integration-plan.md` §3).
- Out of scope: PDF and DOCX readers, OCR, `blocks` and screenshots for samples (so the visual M2 rules R4-R8 and R13 stay `not_applicable` for imported HTML), the calibration `gold_labels` table (Damian's), fetching anything, touching `collect.py`, `app.py` or `__main__.py` (other changes edit them), any new dependency, a bundled demo set (invented ad text would pass for real data).
- Owner: Adam's module (`scraper/`).
- Contracts: writes `ScrapedDocument` v1 fields only, through the existing ingest. No REST route, event, table or object key changes; it inserts `sources` rows with the existing columns. `scrape_meta` gets `client = "sample-import"` and `sample_file`.

## Capabilities

### New Capabilities
- `sample-import`: load saved samples from a directory into documents through the normal ingest, without any network access.

### Modified Capabilities
<!-- none: document-ingest's requirements are unchanged; the importer is a new caller of it -->

## Impact

- New: `scraper/src/iw_scraper/sample_import.py` (reader registry, manifest, runner), `scraper/tests/test_sample_import.py` and fixtures.
- Edited: `scraper/README.md` (how to import, flags), `scraper/CLAUDE.md` (module list), `.docs/status/scraper.md`, `.docs/INDEX.md` if it routes "how do I load samples", AI log row.
- No new dependency, so nothing new to scan (`tomllib` is stdlib in Python 3.12; `lxml` is in use). No compose change: the command runs in the same image and env as the scraper, with the sample directory mounted read-only (`docker compose run --rm -v <dir>:/samples:ro`), so it stays inside the one-command, on-premise stack the brief requires (section 5).
- Overlap: none with `scraper-v2-social`, `scraper-v3-render` or `scraper-stack` code; `scraper-stack`'s README and status edits touch the same docs files, a trivial rebase.
