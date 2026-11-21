# 0101. Scraper fetch client

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by the human via the PR that merges `scraper-v1`

## Context

The scraper's fetch ladder (`iw-scraper-conventions`) needs an async client that looks like a real browser at the TLS, HTTP/2 and header level for most HTML and XHR requests. The `fetch(url, identity, proxy)` seam in `openspec/changes/scraper-v1/design.md` keeps the choice swappable, but Docker images, tests and proxy handling depend on it. Used by the `web-collection` capability.

## Options considered

Evidence read from packages installed into a scratch venv (Python 3.9.6): `noble-tls 0.1.9`, `curl_cffi 0.13.0`, `httpx 0.28.1`. No request to any live site was made, so fingerprint quality against real targets is **untested**.

1. **`noble-tls` 0.1.9**
   - API: `noble_tls.Session` with `async` `get/post/...` and `execute_request`; `Client` enum (`client_identifier`), `random_tls_extension_order`, `is_rotating_proxy`, `proxies` (a dict or string URL), `get_cookies`/`add_cookies`, `close`.
   - It is a ctypes wrapper over a Go `tls-client` shared library. The package ships only Python files under `noble_tls/c/`; `updater/file_fetch.py` downloads the library from GitHub releases (`api.github.com`) via `download_if_necessary()` / `update_if_necessary()`. A Docker image therefore needs network at build time or a vendored asset, and a first run offline fails.
   - Declares `httpx`, `distro` and `requests` as dependencies. README badge says Python 3.10.
2. **`curl_cffi` 0.13.0**
   - API: `curl_cffi.requests.AsyncSession` with `request(...)` taking `impersonate` (literals such as `chrome131`, `chrome136`, `safari184`), `proxy`, `proxy_auth`, `timeout`, `allow_redirects`, `http_version`, plus `ja3` and `akamai` overrides.
   - Requires Python >= 3.9. The libcurl-impersonate code is bundled with the wheel (needs `cffi`, `certifi`), so no runtime download was visible in the package.
   - Identity (UA, headers, TLS profile) is tied together by the single `impersonate` value, which matches the "one identity per session" rule.
3. **`httpx` 0.28.1**
   - Mature async client with no browser TLS impersonation: the TLS and HTTP/2 fingerprint is Python/OpenSSL's, so fingerprinting sites can tell it apart from a browser. Suitable only for sources that do not fingerprint, as the conventions already note.

4. **In-house evidence** (read in `hen68/cheaply-self-hosted`, `shared/src/cheaply_shared/http.py`, not run): a working Python module builds a `noble_tls.Session` with a Chrome identifier, random TLS extension order and an explicit `header_order` tuple, one fresh session per request, and its README excludes the module from lint because byte fidelity matters. `NeoPadel/neopadel` (JS) records that its tls-client native library is pre-warmed at deploy time with a rollback if the download fails, and that header order must be captured on the wire because DevTools shows headers alphabetised. Neither repo uses `curl_cffi`.

## Decision

Use **`noble-tls`** behind the `fetch(url, identity, proxy)` seam, porting the session and header-order pattern from the in-house module above, and pre-warm its native library in the Docker image build so the container needs no network at run time. The image pins Python 3.12; task 2.1 runs the test suite on it, since the evidence was read on 3.9.6 and the package README names 3.10. `curl_cffi` stays the fallback behind the same seam.

Rationale, from the evidence above: a working in-house Python implementation already exists for exactly the properties we need (explicit header order, fresh session per request, random extension order; our session is per run, which is a coarser version of the same pattern), so we port proven code instead of writing a wrapper from memory; the one drawback found, the runtime download of the Go library from GitHub (`updater/file_fetch.py`), has an in-house answer (pre-warm at build, fail the build if it fails). `curl_cffi` bundles its code and ties identity to one `impersonate` value, and no in-house code uses it. Neither package's API as read shows resolved-IP pinning, and for `noble-tls` the header-order parameter is evidenced only by the in-house code, so task 1.5 settles both before anything is built. `httpx` has no browser TLS fingerprint and remains a fallback for non-fingerprinting sources only.

## Consequences

- Task 1.5 is a spike on the installed package before any code is written: can `noble-tls` take an explicit header order, follow redirects manually, pin a resolved IP (or does that need a local pinning layer), and stream with a size cap. If it fails a hard requirement of the spec, this ADR is superseded by one choosing `curl_cffi`.
- The build needs network once (library download); a failed download fails the image build.
- Proxy credentials stay in env; `scrape_meta.proxy` holds an identifier only.
- Fingerprint quality against real targets is untested; task 3.1 includes a manual probe of the first target.
- The `scrape_meta.scraper` value for this client is open with C (task 1.3); the field is not required by the schema.
