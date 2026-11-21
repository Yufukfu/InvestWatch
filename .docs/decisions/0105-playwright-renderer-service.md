# 0105. Playwright renderer as a separate, hardened service

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by: pending approval of the `scraper-v3-render` PR

## Context

Rules R4-R8 and R13 ([analytics-plan.md](../analytics-plan.md) §5) need `blocks` (font size, colour, position, visibility, region) and per-viewport screenshots of a firm's own page ([integration-plan.md](../integration-plan.md) §2-§3). The demo pages (XTB, mBank IKE) are static HTML of 300-600 KB whose layout cannot be recovered from text. Only a browser gives that, and a browser runs hostile page code. Spec: [`openspec/changes/scraper-v3-render/`](../../openspec/changes/scraper-v3-render/).

## Options considered

1. **A. Playwright and Chromium inside the scraper image.** One image and plain calls. The browser then runs next to `DATABASE_URL`, `REDIS_URL` and `MINIO_*`, and the 254 MB scraper image (`iw-scraper:rt`) grows by the browser.
2. **B. A separate image with a small HTTP service the scraper calls.** The browser holds no secrets, has its own base image, limits and update cadence. The scraper keeps rate limiting, `robots.txt` and the domain gate, because it calls once per viewport.
3. **C. A separate arq worker on a `render` queue.** Needs `REDIS_URL` inside the browser container, which is the exposure B avoids.

Measured on 2026-11-21 (Docker 29.6.1, `python:3.12-slim`, `playwright==1.59.0`, `playwright install --with-deps --only-shell chromium`, non-root uid 10001):

| Fact | Result |
|---|---|
| Image size | 360 MB total (`docker image inspect`); the headless shell is 327 MB on disk, ffmpeg 3.3 MB |
| Browser version | 1.59.0 launches `147.0.7727.0`; releases around it: 1.58.0 bundles 145.0.7632.6, 1.57.0 bundles 143.0.7499.4, 1.60.0 bundles 148.0.7778.96 (`playwright/driver/package/browsers.json`) |
| Match with `CHROME_VERSION` 146 | **No release bundles Chromium 146** (145 then 147) |
| Mobile emulation (`is_mobile`, `has_touch`, 390x844) and full-page PNG | works in the headless shell (11 KB PNG for a trivial page) |
| Default launch under `--read-only`, tmpfs `/tmp` and `$HOME`, `--cap-drop ALL`, `no-new-privileges`, `--shm-size 256m` | starts (Playwright adds `--no-sandbox` unless `chromium_sandbox=True`) |
| `chromium_sandbox=True` under the same settings and Docker's default seccomp profile | **fails**: "Target page, context or browser has been closed" |
| `chromium_sandbox=True` with `seccomp=unconfined` (diagnostic only) | starts |
| Checksum | `browsers.json` lists revision and version only, no digest; the pin is the exact `playwright` version (revision 1217) |

## Decision

Option B. The renderer is `scraper/src/iw_renderer/` with its own image target and compose service; the scraper stays Playwright-free.

- **Pin:** `playwright==1.59.0` (Chromium 147, the nearest release above 146; 1.58.0's 145 is older and unpatched longer). The headless shell only (`--only-shell`).
- **Identity:** the renderer builds the user agent and client hints from the browser's own version for every viewport (design decision 4, fallback); `mobile_variant` takes the version as a parameter. `CHROME_VERSION` stays 146: the fetch layer's TLS profile is tied to it and this change does not touch it. Chromium sends its own real TLS handshake, which differs from the `noble-tls` profile; accepted as a documented residual.
- **Sandbox:** `--no-sandbox` (Playwright's default), because the Chromium sandbox does not start under Docker's default seccomp profile and an unconfined profile would weaken the container more than the sandbox adds. This is acceptable only because the container holds no secrets, is on no `data` network and runs as non-root with all capabilities dropped; the browser is the exposed process, the container is the boundary.
- **Hardening:** non-root, read-only root filesystem with tmpfs, `no-new-privileges`, `cap_drop: [ALL]`, CPU and memory limits, `shm_size`, a fresh context per viewport, no `env_file`, no `DATABASE_URL`, `REDIS_URL` or `MINIO_*`.
- **Three navigations per document:** one fresh context and one page load per viewport (desktop, mobile, tablet), each a separate `POST /render` so the scraper applies the per-domain rate limit and the domain gate to each. R8 is about how the page looks on other screens; resizing one page does not make the browser honour `<meta name="viewport">`. Cost is about 15 s per document at 5 s spacing, bounded by `SCRAPER_RENDER_MAX_PER_HOUR`.

## Consequences

- **DNS rebinding:** Playwright cannot pin the resolved address per request as the TLS client does, so between our address check and Chromium's own resolution a hostile name could change. The request check narrows it; with no secrets and no `data` network the reachable surface is the internet and the `egress` peers. Residual, accepted.
- **Redirects are not intercepted:** Chromium follows a redirect inside its network stack, and Playwright's route handler is called for the first request only (probed 2026-11-21: a 302 to another host reached the server with no second `route` call). The renderer therefore checks every hop of the first navigation's chain after the load and fails the render (nothing of the landing page is kept), but the hop itself may already have been requested: a GET with no credentials whose answer is discarded. Same residual class as DNS rebinding.
- **Service workers:** `service_workers="block"` only stops a worker from intercepting requests; `register()` still resolved in the headless shell. A worker's own fetches would bypass the request policy, so the renderer removes `ServiceWorkerContainer` registration and `navigator.serviceWorker` with an init script in every frame. A page that reaches an unpatched realm is still confined by the container (no secrets, no `data` network).
- **Realtime network APIs:** WebRTC (UDP to STUN/ICE hosts) and WebTransport (QUIC) do not pass through Playwright's `route`, so a page could probe internal hosts or show the real egress address behind a proxy. The renderer removes `RTCPeerConnection`, `webkitRTCPeerConnection` and `WebTransport` from every frame and launches Chromium with `--force-webrtc-ip-handling-policy=disable_non_proxied_udp` and `--disable-quic`; the constructors are tested, the flags are not.
- **Reachability:** `egress` is shared with analytics and `ollama-pull`, so the renderer's port is reachable from those peers too. The browser reaching them is stopped by the private-address check, not by the network. With a run proxy the proxy resolves names, so the address check is advisory there.
- **No `--no-sandbox` for a container that gains secrets:** if the renderer ever receives credentials or joins `data`, this ADR must be superseded and a seccomp profile that allows user namespaces adopted.
- **Size:** the render service adds about 360 MB of image; a hardware line goes into `scraper/README.md`, and the image builds only with the stack's render service.
- **Chromium 146 absent:** the identity table's `CHROME_VERSION` and the browser differ by one major; the fallback above keeps the claimed version true. When a release with the matching major appears, or `CHROME_VERSION` is bumped with a TLS profile, the pin can follow.
