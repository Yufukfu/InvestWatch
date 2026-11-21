# Design

## Context

The `Ingestor` (spec `document-ingest`) already does everything after parsing: it takes a page dict with `html`, builds and validates the document, dedups by `(source_id, content_hash)`, uploads, inserts and announces. `parse_page(body, content_type, final_url)` turns saved HTML into the same fields a live fetch gives. `seed.py` is the precedent for a one-shot module with its own entry point and its own DB connection. The stored schema (`validate.py`) accepts only http(s) URLs, and `Source.collectable` is `active and platform == "web"`.

## Goals / Non-Goals

**Goals:**
- Match the brief: documents carry what each module's report needs (advertiser, text, exact URL), on-premise, one-command stack, JSON logs and no console output.
- Samples reach analytics and the dashboard through the same path as scraped pages, so what the jury sees is what the pipeline does.
- Rerunnable at the venue with a changed directory, no duplicates.
- No edit to `collect.py`, `app.py` or `__main__.py`.

**Non-Goals:**
- PDF and DOCX extraction, gold labels, rendering, fetching.

## Decisions

1. **Own entry module, not a subcommand.** `python -m iw_scraper.sample_import` mirrors `iw_scraper.seed` and leaves `__main__.py` and `app.py` (edited by `scraper-v2-social`, `scraper-v3-render`, `scraper-stack`) alone. It builds its own small wiring (asyncpg pool, `Storage`, a Redis client, `Ingestor`) from the same env variables as `app.runtime`, about fifteen lines. Reusing `app.runtime` was rejected: it also builds the proxy, rate limiter and collector the importer must not have.
2. **Reader by extension.** A dict `{".html": read_html, ".htm": read_html, ".txt": read_text, ".md": read_text}` returning the page dict the ingest expects (`text`, `title`, `canonical_url`, `links`, `html`). New formats are one function and one entry; an unknown extension is "skipped", never guessed. HTML goes through `parse_page` so a sample and a live page of the same HTML give identical text and `content_hash`. For text files `html` is the escaped text in a `<pre>`, because the ingest stores the HTML of every document and refuses a blank one.
3. **Manifest in TOML (`tomllib`, stdlib).** The brief's samples will be hand-curated, so a small file beats a CLI with ten flags; `--kind` and `--modules` exist only as the no-manifest minimum. Validation happens up front against the contract enums so a typo cannot create half a set. `source_kind` and `target_modules` decide routing in analytics, so they are never inferred.
4. **One inactive source per set.** `source_id` is required for the dedup scope and the dashboard's source filter. `active = false` keeps the set out of `collectable()` (hence out of the URL guard's allowed hosts) and out of the scheduler. Matched by URL like `seed.py`, never updated, so an operator's dashboard edits survive a rerun. The set URL is the manifest's `url` or `https://sample.invalid/{set}`.
5. **Document URL.** The sample's own `url` when the manifest has it (the page it was saved from, which the dashboard then shows as the exact location the brief asks for); otherwise `https://sample.invalid/{set}/{file}`, since `validate.py` rejects non-http(s) schemes and `.invalid` can never resolve.
6. **`fetched_at` is the import time**, `published_at` only from the manifest; `scrape_meta` is `{scraper: "httpx" (the ADR 0101 default of the ingest), client: "sample-import", sample_file: <name>}`, so a reader can tell an imported document from a fetched one.
7. **Failures are per file, reporting is JSON logs.** Each file's ingest result is counted (`inserted`, `duplicate`, `failed`); `skipped` covers unsupported and symlinked files. One log line per file (name, outcome, `document_id` when inserted) and a summary line go through `logging` and `configure_logging()`, never `print` (a jury check and a repo rule); the ids let Damian attach `gold_labels` without a second lookup. `Ingestor` already records `job_errors`; reader failures (decode, size) are recorded through `record_error` with `parse_error`.
8. **File safety.** `os.scandir` on the directory, regular files only, `follow_symlinks=False`; size checked with `stat` before reading, capped by `FETCH_MAX_BYTES`. Details use the file name only.

## Risks / Trade-offs

- **The real sample format is unknown until the hackathon.** If it is PDF or DOCX, a reader must be added on the day; the registry makes that one function, but it is not delivered here. Mitigation: ask the mentors early, and keep `.txt` as the universal fallback (a pasted text works).
- **`sample.invalid` URLs are not clickable.** A set without per-file URLs shows a dead link in the dashboard. Mitigation: the manifest `url` key, documented in the README.
- **Visual rules stay `not_applicable` for imported HTML.** `blocks` and screenshots need a browser render of a live URL; `scraper-v3-render` does not read local files. The M2 text rules (R1-R3, R9-R12) work; if the jury's samples need R4-R8, that is a follow-up on the renderer.
- **Author is trusted from the manifest.** A wrong `handle` mis-routes analytics' publisher match; the README says the operator must take it from the account, not the page.
- **Inactive sources appear in the dashboard's source list.** They carry no schedule and `last_run_status` stays empty; if Kacper prefers them hidden, that is a `web/` filter, not a change here.
- **Duplicated env reading** with `app.runtime`. Accepted to keep `app.py` untouched; a later refactor can extract it.

## Open Questions

- None blocking. Assumed and recorded: samples are HTML or text for now; the sample format to confirm at the UKNF stand.
