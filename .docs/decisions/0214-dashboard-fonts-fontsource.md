# 0214. Dashboard fonts: self-hosted static `@fontsource` packages

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written from the Paper mockup's font choice (Space Grotesk, Inter, Geist Mono); accepted by: pending approval of the PR

## Context

The dashboard redesign (OpenSpec change `dashboard-redesign`, `web-design-system`) follows a Paper mockup that sets headings and figures in Space Grotesk, body text in Inter and ids, scores and times in Geist Mono. Production serves with `font-src 'self'` and `style-src 'self'` (`web/security-headers.conf`), the system is on-premise, and the jury checks the browser console. Polish text needs the Latin Extended subset (`ąćęłńóśźż`). A new dependency must be open source, pass `npm audit` and be recorded here when it is a new choice ([`.claude/rules/web-dashboard.md`](../../.claude/rules/web-dashboard.md)).

## Options considered

1. **Static `@fontsource/space-grotesk`, `@fontsource/inter`, `@fontsource/geist-mono`** (5.3.0 each, OFL-1.1). One CSS file per weight and subset; Vite bundles the woff2 files and serves them from the app's own origin.
2. **`@fontsource-variable/*`**. Read from the installed packages: each ships a single `wght.css` that declares every subset (Cyrillic, Greek and Vietnamese included) and no per-subset file, so limiting the download to Latin and Latin Extended cannot be expressed.
3. **Font files copied into `web/public/`.** No update path and no `npm audit` coverage.
4. **A font CDN (for example Google Fonts).** Blocked by `font-src 'self'` and against the on-premise requirement.

Evidence (this change, built with `npm run build`): `npm audit` reports 0 vulnerabilities; the build emits 16 woff2 files (`latin` and `latin-ext`; Space Grotesk 400 and 700, Inter 400, 500, 600 and 700, Geist Mono 400 and 600) totalling 324,940 bytes, plus 16 `woff` fallbacks (430,472 bytes) that current browsers do not request. Under the production Content-Security-Policy header the console showed no message at 320, 375, 768, 1024, 1280 and 1440px.

## Decision

Option 1. The three static packages are dependencies of `web/`, only the `latin` and `latin-ext` files of the weights the stylesheet uses are imported in `web/src/main.tsx`, and `font-display: swap` applies. `web/src/styles.test.ts` fails on a font import that is not a `latin` or `latin-ext` file and on a font stack that does not end in a generic family.

Rationale: it is the only option that is self-hosted, scanned by `npm audit`, and able to limit subsets, which is what the CSP and the Polish text need.

## Consequences

- About 325 kB of woff2 is added to what the browser can fetch (not all of it on every visit: the browser requests only the weights and subsets the page uses). `design.md` estimated about 100 kB; the measured size is larger, so if the demo network is slow, drop Geist Mono to the system monospace first.
- Adding a family is a deliberate edit of `main.tsx` and the style test; a new weight is an edit of `main.tsx` only, so check the size when adding one.
- The licence is OFL-1.1; the fonts are bundled unmodified and each package carries its licence file.
