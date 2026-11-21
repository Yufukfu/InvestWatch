# scraper (Adam's module)

Collects web and social-media content and writes `ScrapedDocument` rows (contract v1, `.docs/integration-plan.md` §3) plus HTML and screenshots to MinIO. Downstream, `analytics` consumes the Redis Stream `iw:documents`; the scraper knows nothing about analytics.

Run `iw-scraper-conventions` before writing any fetch or parse code. Team decision: start with **one** social platform, add more only if time allows.

## Stack

- Python, async-first. Fetch with a **TLS-impersonating client** (noble-tls or similar; chosen via ADR after reading the real API) so requests look like a browser. Playwright only as a fallback and for sources that need `blocks`/`screenshots`.
- Job queue and schedule: open-source, decided via ADR. Storage: PostgreSQL + MinIO + Redis from `docker-compose.yml`.
- Tests: pytest, saved real responses in `tests/fixtures/`, no live network in unit tests.

## Ingest (`src/iw_scraper/ingest/`)

`Ingestor.ingest` is the one entry point: validate, dedup pre-check, upload HTML, insert, then `XADD`; `sweep` republishes rows whose announcement was lost. Spec `scraper-ingest` (capability `document-ingest`), reasoning in [ADR 0104](../.docs/decisions/0104-ingest-order-and-republish-sweep.md). Rules that bite: the schema belongs to Damian's module (Alembic in `api/`, never create or alter a table here); `iw-raw` is created by `minio-init`, the service only checks it (`Storage.check_bucket`); the conflict target of the insert is named and must match Damian's partial unique index; `job_errors.detail` is redacted but must still never be given credentials. Nothing calls these yet: the wiring (sink adapter, `page` dict with `html`, `check_bucket` at startup, the scheduled sweep) is still to be assigned between `scraper-v1` and `scraper-orchestration`. Tests need PostgreSQL, Redis and MinIO (`IW_TEST_*`, see [`README.md`](README.md)); a mutation check goes on every guard (`iw-commit-cycle`).

## Done means

Schema-valid documents land in `documents`, an `XADD iw:documents` follows, a rerun dedups by `content_hash`, and a block or parse failure is logged as a job error instead of an empty document.
