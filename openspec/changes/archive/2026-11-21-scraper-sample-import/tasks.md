# Tasks

## 1. Readers and manifest (pure logic)

- [x] 1.1 Write `scraper/tests/test_sample_import.py` first for the readers and the manifest: HTML equals `parse_page` output, `.txt`/`.md` become text with a non-blank `html`, an unknown extension is skipped, a symlink is skipped, an oversized or non-UTF-8 file is a `parse_error`, per-file manifest overrides win over set defaults, an invalid enum, `lang` or `published_at` is refused before anything is read, `author` comes only from the manifest (a `<meta name="author">` in the HTML is ignored); run it and see it fail for the missing module
- [x] 1.2 Implement `scraper/src/iw_scraper/sample_import.py`: reader registry, directory scan (regular files, no symlinks, size cap), manifest parsing and validation, page-dict building with the default `https://sample.invalid/{set}/{file}` URL
- [x] 1.3 Mutation check of the symlink, size and manifest-validation guards; record `mutations: N tried, N caught`: `mutations: 14 tried, 14 caught`
- [x] 1.4 Commit

## 2. Source row and ingest run (needs PostgreSQL, Redis, MinIO)

- [x] 2.1 Extend the tests (the `IW_TEST_*` stack): a directory of three files inserts three documents, objects and stream events; a rerun inserts nothing and reports duplicates; the source row is `active = false` with no cron and is absent from `collectable()`; an existing source with the URL is not changed; one empty file gives `empty_text` and the others still land, summary `inserted 2, duplicate 0, skipped 0, failed 1`; run and see them fail
- [x] 2.2 Implement `ensure_source`, the runner, the per-file and summary JSON log lines (`logging`, no `print`), the exit code and `main()` (own wiring from the env of `app.runtime`, no import of `app.py`)
- [x] 2.3 Mutation check of the `active = false` insert and the duplicate path; record `mutations: N tried, N caught` (1.3: mutations: 14 tried, 14 caught)
- [x] 2.4 Commit

## 3. Usage and a rehearsal

- [x] 3.1 Test the usage errors: no manifest and no `--kind`/`--modules`, a missing directory, an invalid manifest creates no source row (`mutations: 5 tried, 5 caught`)
- [x] 3.2 Rehearsed once in the image, as `scraper-stack` is not merged and the human chose to skip the full stack: `python -m iw_scraper.sample_import` on two saved pages from `scraper/tests/fixtures/` (scratch directory mounted read-only) against real PostgreSQL, Redis and MinIO: inserted 2, rerun duplicate 2, exit 0; no flags and no manifest exit 2; inactive source with no cron; 2 entries on `iw:documents`. Analytics findings and the dashboard alert were not exercised; record that in the PR body
- [x] 3.3 Commit

## 4. Closing

- [x] 4.1 Apply the `iw-docs-update` skill: `scraper/README.md` (short: the command, flags, `samples.toml` keys, the author rule, no filler), `.docs/security-audit.md` only if a dependency changed (none expected), `scraper/CLAUDE.md` module list, `.docs/status/scraper.md`, `.docs/INDEX.md` if it routes sample loading; add the `iw-ai-log` row; `docs-check` prints `docs-check: ok`
- [x] 4.2 Run the `iw-pr-review` skill and fix real findings
