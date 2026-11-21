# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owner:** Adam
- **Status:** document ingest is implemented (`scraper-ingest`: validate, dedup, store HTML in MinIO, announce on `iw:documents`, republish sweep, `job_errors`). Fetching, the queue and the scheduler are in `scraper-v1` and `scraper-orchestration`.

## Tests

`pytest` from `scraper/` (Python 3.12, `pip install -r requirements.txt -r requirements-dev.txt`). Pure-logic tests need nothing. The ingest tests need real PostgreSQL, Redis and MinIO, addressed by `IW_TEST_PG_DSN`, `IW_TEST_REDIS_URL`, `IW_TEST_MINIO_ENDPOINT`, `IW_TEST_MINIO_ACCESS_KEY` and `IW_TEST_MINIO_SECRET_KEY`; without them they are skipped, and with `CI` set they fail. The schema they run on is `tests/schema.sql`, a throwaway copy of Damian's `0001_initial`; the service itself never creates tables or the `iw-raw` bucket.
