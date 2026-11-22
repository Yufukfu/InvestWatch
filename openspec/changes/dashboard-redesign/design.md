# Design

## Context

- `web/src/styles.css` (about 230 lines) holds all styling with plain class names; components are presentational and take props (ADR 0204), so a restyle changes CSS and markup, not hooks or view models.
- Production serves with `style-src 'self'; font-src 'self'` (`web/security-headers.conf`): no inline `style` attributes written by our markup, no font from another origin. Recharts is the existing chart library (ADR 0203) and is kept.
- The reference is the Paper page "InvestWatch · Dashboard" in the Neopadel Paper file: desktop 1440, tablet 768, mobile 390, drawer with alert, calibration, and a components sheet. Its figures are placeholders; the app renders real backend data.
- Open web branches `web/untrusted-text-plain` and `web/vitest-build-timeouts` edit `FindingsTable.tsx`, fixtures and test setup; this change rebases over them.

## Goals / Non-Goals

**Goals:**
- One token-driven stylesheet that reproduces the Paper design at three width steps, with measured contrast and no horizontal scroll from 320px.
- Triage entry and keyboard shortcuts built only on the existing hooks and routes.
- Evidence that it works: screenshots of every section at 320, 375, 768, 1024, 1280 and 1440px saved in the repo, and a clean console in the production build.

**Non-Goals:**
- New routes, REST endpoints, events or contract fields; bulk actions, export and the M2 coverage strip (raised with Damian as an issue).
- A router: the "Przegląd / Zgłoszenia / Kalibracja" header links are in-page anchors.
- A CSS framework or component library.

## Decisions

1. **Tokens as CSS custom properties on `:root`, existing class names kept.** Replace the values in `styles.css` and add the new rules; rename a class only where the markup must change. Alternative: CSS modules or Tailwind. Rejected: it rewrites every component and its tests for no behavioural gain, and the deadline is hours away.
2. **Fonts through `@fontsource-variable/space-grotesk`, `@fontsource-variable/inter` and `@fontsource/geist-mono`**, imported in `main.tsx` so Vite bundles the files and serves them from `'self'`. Alternative: copy font files into `public/`. Rejected: no update path and no `npm audit` coverage. Only the `latin` and `latin-ext` subsets are imported (Polish needs `latin-ext`); `font-display: swap`. Each package passes `npm audit` before the PR.
3. **Responsive by CSS, not by JavaScript.** Layout steps use `@media (min-width: 600px)` and `(min-width: 1024px)` on top of a phone-first base; the table becomes cards through `display: block` and grid on the same DOM, so there is one markup and one set of tests, and nothing depends on `window.matchMedia`. The only scripted piece is the open/closed state of the phone filter panel: a button with `aria-expanded` controlling the filter region, with the active-filter count in its label.
4. **Detail drawer**: keep the existing portal and focus handling (PR #39 fixes); only layout and styling change, full-screen below 600px.
5. **Triage** sets the filters through the existing `findingsUrl` helpers: reset to `DEFAULT_FILTERS` (page 1, default page size, no module, platform, text, score or dates), then `status=new` and `risk_level=high`; the default sort stays out of the URL. A one-shot flag in the findings page opens the first row (sets `finding=<id>`) when that result arrives, and is cleared when it does or the result is empty or an error. The button is shown when the existing summary hook reports a high-risk count above 0 and shows no count, because that count spans all statuses.
6. **Shortcuts** live in one `useFindingShortcuts` hook in `features/findings/data/`, attached to `document`, which ignores events from inputs, selects, text areas and contenteditable, and any with Ctrl, Meta or Alt held. It calls the existing `useStatusChange`; `1`-`5` need a selected finding and skip a no-op status. `J`/`K` move within the loaded page only. `Esc` is not handled there: the detail's existing two-step Escape stays the only handler. The legend is a plain disclosure under the findings heading.
7. **Calibration proportion bar** is drawn from the TP/FP/FN/TN the API returns for the selected point; widths are proportions of those counts (layout), and nothing is recomputed (web/CLAUDE.md rule). Data-dependent widths (this bar, the existing score bar in `FindingsTable.tsx`) are set through React's `style` prop, which writes the CSSOM and is allowed by `style-src 'self'`; the static HTML has no `style` attribute.
8. **Evidence screenshots** are captured from the production build against the contract mock server (`contracts/mock-server`, run as in `web/README.md`: `docker run -p 127.0.0.1:8000:8000 iw-mock-server`) with Chrome DevTools at the six widths and saved under `.docs/screens/dashboard-redesign/`; the Paper desktop, tablet and mobile artboards are exported next to them in `design/` so the reviewer has the reference inside the repo. Visual review of those images is delegated to a subagent, not read in the main session.

## Risks / Trade-offs

- **Three font families add bundle weight** (about 100 kB of woff2 for the used weights). Mitigation: only the weights used (Space Grotesk 400/700, Inter 400/500/600/700, Geist Mono 400/600) and `latin`/`latin-ext`; check the build size and drop Geist Mono to the system monospace if the main chunk grows beyond what the demo network tolerates.
- **Table to cards with one DOM** can break table semantics for screen readers. Mitigation: keep a real `<table>` with `role` attributes restored on the phone layout, and test roles and names with Testing Library.
- **Existing tests query by class names or text**; some will need updating. Mitigation: each task group starts with the failing or updated test and runs the full web suite.
- **Merge overlap** with `web/untrusted-text-plain`: a one-line conflict in `FindingsTable.tsx`, resolved by rebasing whichever lands second.
- **Time**: hand-in is Sunday 10:30. The restyle (groups 1-5) is releasable on its own; triage and shortcuts (groups 6-7) are cut first if time runs short.
