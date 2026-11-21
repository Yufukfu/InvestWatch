# 0101. Scraper fetch client

- Status: proposed
- Date: 2026-11-21
- Deciders: (human, Adam's module; to be filled in)

Agent draft: Context, Options and evidence only. The decision and its rationale are for a human.

## Context

The scraper's fetch ladder (`iw-scraper-conventions`) needs an async client that looks like a real browser at the TLS, HTTP/2 and header level for most HTML and XHR requests. The `fetch(url, identity)` seam in `openspec/changes/scraper-v1/design.md` keeps the choice swappable, but Docker images, tests and proxy handling depend on it. Used by the `web-collection` capability.

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

## Decision

(to be written by a human)

## Consequences

(to be written by a human)

Contract note: `scrape_meta.scraper` in `contracts/schemas/scraped-document.schema.json` allows `playwright|httpx|api|manual`, and none describes a TLS-impersonating client (`noble-tls` or `curl_cffi`), so whichever is chosen needs a value agreed with Damian (task 1.3 of `scraper-v1`).

Points a decider may want checked before choosing: that the target sources accept each client in a short manual probe, how the image gets the `noble-tls` binary in an offline demo, and which Python version `scraper/` pins.
