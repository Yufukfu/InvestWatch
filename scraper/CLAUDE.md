# scraper (module A)

Collects web and social-media content and writes `ScrapedDocument` rows (contract v1, `.docs/integration-plan.md` §3) plus HTML and screenshots to MinIO. Downstream, `analytics` consumes the Redis Stream `iw:documents`; the scraper knows nothing about analytics.

Run `iw-scraper-conventions` before writing any fetch or parse code. Team decision: start with **one** social platform, add more only if time allows.

## Stack

- Python, async-first. Fetch with a **TLS-impersonating client** (noble-tls or similar; chosen via ADR after reading the real API) so requests look like a browser. Playwright only as a fallback and for sources that need `blocks`/`screenshots`.
- Job queue and schedule: open-source, decided via ADR. Storage: PostgreSQL + MinIO + Redis from `docker-compose.yml`.
- Tests: pytest, saved real responses in `tests/fixtures/`, no live network in unit tests.

## Done means

Schema-valid documents land in `documents`, an `XADD iw:documents` follows, a rerun dedups by `content_hash`, and a block or parse failure is logged as a job error instead of an empty document.
