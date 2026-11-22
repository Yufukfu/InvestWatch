# Tasks

## 1. Untrusted text: plain text, own direction

- [x] 1.1 Write failing tests: a detail whose evidence, explanation (issue and collapsed rule), summary, title and advertiser name/handle contain `<img src=x onerror=alert(1)>`, `[link](javascript:alert(1))`, a bare URL and U+202E creates no `img` and no extra link, shows the text literally, and keeps each U+202E in a `dir="auto"` element holding only that value; same for the table title and the toast title. Verify they fail first.
- [x] 1.2 Add `dir="auto"` (and a span where a value shares a line with UI text) in `FindingDetailPanel.tsx`, `FindingsTable.tsx`, `AlertToasts.tsx`. Verify tests, lint, typecheck, build.
- [x] 1.3 Mutation check; list every mutant and result on this line. Mutants, each run against `untrustedText.test.tsx` and `AlertToasts.test.tsx`: `dir` dropped from the evidence span; evidence unwrapped from its span; closing quote moved inside the evidence span; evidence rendered with `dangerouslySetInnerHTML`; evidence auto-linked (`<a href={evidence}>`); `dir` dropped from the issue explanation, the collapsed explanation, summary, heading title, advertiser name, handle link, handle text, excerpt, full text, table title button and toast title; the ` – ` separator and the collapsed explanation in one `dir="auto"` span. A first variant of the last one (outer span given `dir` with the inner span kept) survived and is equivalent: the inner span still isolates the value; replaced by the variant above. mutations: 17 tried, 17 caught.

## 2. Closing

- [ ] 2.1 Apply `iw-docs-update` (docs, `.docs/status/dashboard.md`, ADRs) and add the `iw-ai-log` row.
- [ ] 2.2 Run `iw-pr-review` and fix real findings.
