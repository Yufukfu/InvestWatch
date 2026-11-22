# Proposal

## Why

The dashboard works but looks like a default form page: system font, grey cards, no hierarchy between the high-risk findings and the rest, and a table whose risk column is the only cue. The jury scores a demo to a national supervisor, so it must read as a calm institutional tool, and an analyst should reach the highest-risk finding in one click. A design was agreed with the web owner (Kacper approved implementing it) on the Paper page "InvestWatch · Dashboard".

## What Changes

- **Design tokens and type** in `web/src/styles.css`: colour, spacing and radius custom properties, three self-hosted font families (Space Grotesk for headings and figures, Inter for text, Geist Mono for ids, scores and timestamps), and measured contrast: all text at least 4.5:1, no text under 12px.
- **Restyle of the existing sections**, keeping every data hook, view model and request unchanged: header with `NARZĘDZIE NADZORCZE` label and in-page anchor navigation (Przegląd, Zgłoszenia, Kalibracja), hero summary ("72 zgłoszenia, z czego 10 wysokiego ryzyka") with module counts, trend chart (M3 drawn teal so a series colour never reads as a risk level), filters, findings table (high-risk rows tinted, mono scores and dates, risk by text label plus colour), detail drawer (evidence and legal basis first), alert toast, calibration panel (a TP/FN/FP/TN proportion bar above the metrics).
- **Triage entry**: a hero button (no count: the summary counts high-risk findings of every status) that opens the findings list on `status=new`, `risk_level=high`, newest first, page 1, other filters cleared, with the first row's detail open.
- **Keyboard shortcuts** in the list and the detail: `J`/`K` next and previous finding, `1`-`5` set the status, `O` open the source, `/` focus search; `Esc` keeps its existing two-step behaviour; with a visible legend.
- Touches no contract, REST route or event. Uses only `GET /findings`, `GET /findings/{id}`, `PATCH /findings/{id}` and `GET /stats/summary` as today. The restyle changes no existing requirement of `web-findings`, `web-trend`, `web-alerts` or `web-calibration` (their detail, Escape and focus rules stay as specified).

Out of scope (need backend or a team decision, raised as an issue for Damian): bulk status change, report export, an aggregated M2 rule-coverage strip, a separate "Kolejka" route and a dark theme. Owner: `web/` (Kacper), implemented by Adam with Kacper's go-ahead.

## Capabilities

### New Capabilities
- `web-design-system`: the visual contract of the dashboard: tokens, self-hosted fonts, contrast and text-size floor, risk and module colour roles, and styling that the production CSP allows.
- `web-triage`: the one-click triage entry and the keyboard shortcuts for working through findings.

### Modified Capabilities
<!-- None: existing web-* requirements keep their behaviour; the restyle changes no requirement. -->

## Impact

- `web/src/styles.css` (tokens, all section styles), `web/index.html` and `web/src/main.tsx` (font imports), `web/package.json` (three font packages, scanned with `npm audit`).
- Components under `web/src/features/{summary,findings,trend,alerts,calibration}/components/` change markup and class names only where the design needs it; tests that query by role and text keep passing.
- Overlap: open branch `web/untrusted-text-plain` also edits `FindingsTable.tsx` (one line); whichever merges second rebases.
