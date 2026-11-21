## Why

Kacper's second review of PR #35 (20:11Z, on 6da4f1f) adds two required security items and five smaller ones, each reproduced on the current tip: a page URL with a backslash authority (`https://attacker.net\@alfa-inwestycje.example.com/`) still matches the firm's domain in `Registry.match`, so a `firm_own` page becomes M2 at 1.0 for a page the firm does not own; `Registry.match` takes 22 s on 1 MB of `"1,"`; a handle equal to a firm's name on any platform makes the author the registered firm (M2 at 1.0); a fullwidth or zero-width variant of a firm name reaches only the fuzzy match. `analytics-m1-m3-review-fixes` is already archived, so these go into this second review-fix change.

## What Changes

- **Host parsing (item 7):** `Registry.match` takes the page host through `http_host`, as `match_links` and `publisher_firm` already do; a URL `http_host` rejects (backslash, whitespace, control characters in the authority) has no domain match, and `page_host` returns no host for it.
- **Bounded registry cost (item 8):** routing and the M1/M3 rules see at most the first 200 000 characters of the text (`SCAN_MAX`); evidence quotes stay substrings of the original text, because the scanned text is its prefix. The fuzzy match tokenizes each firm's core name once per call instead of once per text segment. M2 rules still see the whole text. Real-scale matching (one combined alternation for ~300 firms) comes with the stage-3 `analytics-knf-registry` change, not here.
- **Handle identity (smaller item):** a handle alone no longer makes the publisher a registered firm; the profile host or the page host must be one of the firm's domains. A handle equal to the matched firm's name routes as third-party (M1), with S1.6 `uncertain` ("nie potwierdzono, że konto należy do firmy").
- **Confusables (smaller item):** names and the text are compared after NFKC and removal of zero-width and soft-hyphen characters; the evidence quote is mapped back to the original text. Cyrillic and Greek confusables are a follow-up.
- **`test_redos.py` (smaller item):** budgets become a generous absolute limit plus a 2x-input growth check; new cases for `"a." + " " * 100_000 + "x"` (the `_BOUNDARY` fix from #26, merged at 9bd27e8), the R2/S1.3 `negation_before`, the S1.2 query regexes, `word_patterns`, 1 MB of `"1,"` and of zero-width characters through the pipeline; a test pins the fuzzy ratio boundary at 88.
- **Follow-ups:** M3 suppression by naming the firm in every offer sentence is an accepted evasion for the rules (the LLM stage re-judges attribution); `save_findings` never deleting is follow-up 35 of `analytics-m1-m3`.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `document-analysis`: "Firm registry matching" (normalized names, host through `http_host`), "Routing to modules" (handle no longer identity), "Linear time on hostile text" (scan cap).
- `m1-third-party-signals`: "S1.6 author other than the firm" (`uncertain` for a handle-only match).

## Impact

- Owner: Damian (`analytics/`). No contract, REST route or event change; output still validates against `finding.schema.json` v1. Branch `analytics/analytics-m1-m3` (PR #35), merge only.
- Code: `registry.py` (small, additive: host via `http_host`, normalized matching, pre-tokenized fuzzy core; the stage-3 session is told), `modules/advertiser.py`, `modules/router.py`, `pipeline.py`, `rules/m1.py`, tests.
- Docs: `analytics/README.md`, `.docs/status/platform.md`, the AI log row.
