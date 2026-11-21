# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owner:** A
- **Status:** web collection (`scraper-v1`: fetch, parse, politeness, guards) is implemented as a library; storage, queue and schedule follow in `scraper-ingest` and `scraper-orchestration`; the first social platform is `scraper-v2`.

## Run the tests

Python 3.12 and the native TLS library are only in the image. From the repository root:

```bash
docker build -f scraper/Dockerfile --target test -t iw-scraper:test .
docker network create iw-scraper-test
docker run -d --name iw-scraper-test-redis --network iw-scraper-test redis:7
docker run --rm --network iw-scraper-test -e REDIS_URL=redis://iw-scraper-test-redis:6379/0 iw-scraper:test
```

## Configuration

Environment only; defaults in `scraper/.env.example`. `config.py` reads and validates each variable; the run that joins the pieces (`scraper-orchestration`) passes the values on, so until it exists the library takes them as parameters. Proxy URLs may hold credentials: they are never logged, only a `proxy-xxxxxxxx` identifier is.

| Variable | Default | Meaning |
|---|---|---|
| `PROXY_LIST` | empty (direct) | comma-separated `http`, `https` or `socks5` proxy URLs |
| `PROXY_ROTATION` | `per_request` | `per_request` or `per_session` |
| `PROXY_COOLDOWN_SECONDS` | `90` | how long a proxy that answered 407 is skipped |
| `REDIS_URL` | `redis://localhost:6379/0` | shared rate limit, deferrals and domain pause |
| `DOMAIN_MIN_INTERVAL_SECONDS` | `5` | minimum gap between request starts per domain, all workers |
| `MAX_RETRY_AFTER_SECONDS` | `300` | cap on a `Retry-After` wait |
| `DOMAIN_FAILURE_THRESHOLD` | `5` | consecutive failure outcomes before a domain is paused |
| `DOMAIN_PAUSE_SECONDS` | `600` | length of that pause |
| `FETCH_TIMEOUT_SECONDS` | `20` | per-request timeout |
| `FETCH_MAX_BYTES` | `5242880` | response size cap (5 MiB) |
| `ALLOWED_PORTS` | `80,443` | ports the scraper may request |
| `COMPOSE_INTERNAL_HOSTS` | empty | extra host names refused as internal (bare names are always refused) |
| `FETCH_EXTRA_HOSTS` | empty | hosts allowed for redirects and scraped links besides the active sources |
| `CONTRACTS_DIR` | `<repo>/contracts` | JSON Schemas used for validation |
