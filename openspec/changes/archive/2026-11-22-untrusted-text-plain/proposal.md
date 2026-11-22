# Proposal

## Why

Since `analytics-llm-p0` merged, finding fields carry text written by a language model and quotes copied from scraped pages. Both are untrusted: a page can carry markup, Markdown links, bare URLs or Unicode bidi controls that end up in `rule_results[].explanation`, `rule_results[].evidence`, `summary`, `title` and `advertiser.name`/`handle` (issue #54, follow-up R55 of `analytics-llm-p0`).

An audit of `web/src` found that every one of these fields is already rendered as React text (no `dangerouslySetInnerHTML`, no Markdown, no auto-linking; oxlint `react/no-danger` is on), so markup cannot become a live element. Two gaps remain:

1. No field sets a base direction, so a quote in Arabic or Hebrew is laid out as left-to-right.
2. A right-to-left override (U+202E) in a field can reorder UI text that shares its line: the closing quote mark around the evidence, the ` – ` separator before a passed rule's explanation.

## What Changes

- Every element that shows one of these fields holds that field alone and carries `dir="auto"`; where a field shares a line with UI text, it is wrapped in its own `dir="auto"` span. An element with a `dir` attribute is a bidi isolate (HTML UA stylesheet), so an override inside it cannot reorder text outside it.
- Covered: findings table title; detail heading, summary, rule explanation (issues and the collapsed groups), evidence, advertiser name and handle, excerpt and full text; high-risk toast title.
- A test renders a finding whose fields contain `<img src=x onerror=alert(1)>`, `[link](javascript:alert(1))`, a bare `https://` URL and U+202E, and checks that no element or link is created from them, that the text is shown literally, and that each U+202E sits in a `dir="auto"` element holding only the untrusted value.

Out of scope: stripping or rewriting bidi controls (evidence is a verified exact substring and is shown verbatim); the visually hidden live-region announcement and `aria-label` strings (not laid out visually); firm name (from the KNF registry); rule `name` and `legal_basis` (rule catalogue, not model output).

Module: `web/` (Kacper). No contract, REST route or event changes (`contracts/schemas/finding.schema.json` unchanged).

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-findings`: adds a requirement on untrusted text in the table and detail.
- `web-alerts`: adds a requirement on the toast title's direction.

## Impact

- Code: `web/src/features/findings/components/FindingDetailPanel.tsx`, `FindingsTable.tsx`, `web/src/features/alerts/components/AlertToasts.tsx`, and their tests.
