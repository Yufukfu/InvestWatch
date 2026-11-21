# Tasks

Kacper's second review of PR #35 (20:11Z). Branch `analytics/analytics-m1-m3` (pushed: merge only). `contracts/` and `web/` stay untouched.

## 1. Host parsing and bounded registry cost (items 7, 8)

- [x] 1.1 Failing tests: `https://attacker.net\@alfa-inwestycje.example.com/` matches no firm by domain on the M1 path and the `firm_own`/M2 path, and `page_host` gives no host for it; 1 MB of `"1,"` and of zero-width characters go through `analyze` within the budget; evidence found past the cap is not quoted, evidence before it is a substring of the original text
- [x] 1.2 `registry.py` (host via `http_host`, core tokens once per call), `modules/advertiser.py` (`page_host`), `pipeline.py` (`SCAN_MAX`, capped document for routing and M1/M3); tests green
- [x] 1.3 Mutation check; `mutations: 6 tried, 5 caught`, 1 equivalent (an empty-host guard: an empty host never equals or ends with a firm domain; removed). The no-cap mutant is caught by the 1 MB growth test exceeding its budget (the runner stopped it at 300 s); two first survivors got tests (the 1 MB growth check, M2 seeing the whole text)

## 2. Handle identity and confusables

- [x] 2.1 Failing tests: `@alfainwestycje` on TikTok gives M1 (not M2) with S1.6 `uncertain` and "nie potwierdzono, że konto należy do firmy"; a profile host on the firm's domain still gives M2; `Ａｌｆａ Inwestycje` and `Alfa​ Inwestycje` match by name with evidence quoted from the original text; Cyrillic stays unmatched
- [x] 2.2 `modules/advertiser.py` (`publisher_firm` by hosts only), `rules/m1.py` (S1.6), `registry.py` (normalized name matching with an offset map); tests green
- [x] 2.3 Mutation check; `mutations: 9 tried, 9 caught` (three first survivors, a handle naming another firm, a fullwidth registry name and a zero-width character inside a fuzzy name, got their own tests)

## 3. Robust ReDoS tests

- [x] 3.1 `tests/test_redos.py`: absolute budget plus a 2x growth check; `"a." + " " * 100_000 + "x"`; `negation_before`, the S1.2 query regexes, `word_patterns`; the fuzzy ratio at exactly 88 matches and below it does not
- [x] 3.2 Mutation check; `mutations: 4 tried, 4 caught`: unbounded lookback in R2 and in S1.3, the old unbounded number prefix in S3.5, and an unanchored S1.2 query key (no measurable slowdown at the tested size; caught by `test_m1.py::test_s12_key_must_be_a_whole_query_key`). Two tests first needed inputs that reach the pattern (an S1.3 label in the negation text, an href body without `&`)

## 4. Closing

- [x] 4.1 Spec deltas within 500 characters per requirement; `follow-ups.md` (M3 suppression by naming the firm, Cyrillic/Greek confusables, the glued `AlfaInwestycje`); `analytics/README.md`, your own `.docs/status/platform.md` line; the iw-ai-log row; `docs-check` and OpenSpec 2.1.1 strict clean
- [x] 4.2 Run the iw-pr-review skill (one reviewer pass with `focus: security`) and fix real findings (registry lookups capped at 200 000 characters, `text_truncated` logged, aliases that fold to nothing skipped; `mutations: 3 tried, 3 caught`)
