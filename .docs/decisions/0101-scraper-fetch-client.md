# 0101. Scraper fetch client

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by the human via the PR that merges `scraper-v1`

## Context

The scraper's fetch ladder (`iw-scraper-conventions`) needs an async client that looks like a real browser at the TLS, HTTP/2 and header level for most HTML and XHR requests. The `fetch(url, identity, proxy)` seam in `openspec/changes/archive/2026-11-21-scraper-v1/design.md` keeps the choice swappable, but Docker images, tests and proxy handling depend on it. Used by the `web-collection` capability.

## Options considered

Evidence read from packages installed into a scratch venv (Python 3.9.6): `noble-tls 0.1.9`, `curl_cffi 0.13.0`, `httpx 0.28.1`. No request to any live site was made while the options were written, so fingerprint quality against real targets was untested then; the spike (task 1.4) and the probe of the first target (task 3.1) are in Consequences.

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

Rationale, from the evidence above: a working in-house Python implementation already exists for exactly the properties we need (explicit header order, fresh session per request, random extension order; our session is per run, which is a coarser version of the same pattern), so we port proven code instead of writing a wrapper from memory; the one drawback found, the runtime download of the Go library from GitHub (`updater/file_fetch.py`), has an in-house answer (pre-warm at build, fail the build if it fails). `curl_cffi` bundles its code and ties identity to one `impersonate` value, and no in-house code uses it. Neither package's API as read shows resolved-IP pinning, and for `noble-tls` the header-order parameter is evidenced only by the in-house code, so task 1.4 settles both before anything is built. `httpx` has no browser TLS fingerprint and remains a fallback for non-fingerprinting sources only.

## Consequences

- Spike result (task 1.4, `noble-tls 0.1.9` with `tls-client` 1.18.1, run on macOS arm64 and Python 3.9.6 against a local raw-socket server and `www.knf.gov.pl`; 2026-11-21):
  - **Header order: works.** `Session(header_order=[...])` sent `accept-language, user-agent, accept` in that order over HTTP/2 (seen on `tls.peet.ws`); headers not listed (`accept-encoding`) are appended at the end, so the identity table must list every header it wants.
  - **Manual redirects: works.** `allow_redirects=False` returned `302` with `Location`.
  - **IP pinning: works.** Connecting to `https://<ip>/` with `server_name_overwrite=<host>` and `request_host_override=<host>` returned 200; without the overrides certificate verification failed, so pinning stays safe.
  - **Size cap: cannot abort mid-stream.** `stream_output_path` writes the whole body to a file (300008 bytes for a 300000-byte body) and offers no early abort, so the cap is checked after the transfer, with the request timeout bounding it (spec adjusted).
  - **Fingerprint age matters.** KNF reset the connection (`EOF`) for the `CHROME_117` and `CHROME_131` profiles and answered 200 (807 KB page) for `CHROME_146_PSK`. The identity table must carry current profiles and a canary must catch staleness.
  - **The updater is unsafe for builds.** `download_if_necessary()` always asks `api.github.com` for the latest release (unpinned; unauthenticated calls got HTTP 403 here), so the Dockerfile must instead download a pinned release asset by tag, verify its sha256 and write the `.version` file itself, never calling the updater. Asset names differ per platform (`tls-client-linux-ubuntu-amd64-1.18.1.so`, `tls-client-linux-arm64-1.18.1.so`); `noble-tls` itself notes its Linux naming is untested, so task 2.1 verifies it in the image (Debian/Ubuntu base).
- Python 3.12: the spike ran on 3.9.6; the image and every test of `scraper-v1` run on 3.12 (task 2.1), and the charset and transport findings above were made there.
- Proxy credentials stay in env; `scrape_meta.proxy` holds an identifier only.
- Charset (task 3.1, Python 3.12, local stub server): the client **transcodes every body to UTF-8** when it finds a charset, from the `Content-Type` header first and a `<meta>` declaration second (windows-1250 and ISO-8859-2 bodies came back as UTF-8 while the header still said `windows-1250`). Valid UTF-8 with no declaration passes unchanged; a legacy-encoded body with no declaration is read as windows-1252 and garbled, as a browser would do. So `fetch()` reports `charset=utf-8` and the parser never decodes a second time.
- Transport errors (timeout, connection refused, DNS failure) all arrive as one `TLSClientException` whose message tells them apart: only "timeout" or "deadline exceeded" maps to `timeout`; the rest is `http_error` with the redacted message, because the closed reason set has no separate network reason.
- With a proxy the client always tunnels with `CONNECT`, even for `http://` targets, so a proxy must allow `CONNECT`.
- Manual probe of the first target (task 3.1, 2026-11-21, no proxy, profile `CHROME_146_PSK`, Chrome 146 header set): `https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne` answered 200 with 819294 bytes (the size of the saved fixture) in 4.3 s; the parser read the title, a canonical URL and 232215 characters of text. Fingerprint quality against other targets is still untested.
- `scrape_meta.scraper` for this client: the v1 enum is `playwright|httpx|api|manual` and the field is optional, so no contract change. The scraper writes `scraper: "httpx"` (the nearest value for an HTTP client) and `client: "noble-tls"` (`scrape_meta` allows extra keys), tested against the contract schema. A dedicated enum value (for example `http_tls`) stays an option for the next contract version; Damian owns `contracts/` and is told in the PR.
