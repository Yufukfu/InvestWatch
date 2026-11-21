# Follow-ups

Out-of-scope reviewer findings, "declined to judge" items and differences from the frozen mocks, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | iw-reviewer, group 1 | `bias`/`weight` accepted `.nan` and `.inf` | `fix-here`: `_number` requires a finite value; cases in `test_malformed_signal_catalogue` |
| 2 | iw-reviewer, group 1 | S1.7 and S3.6 dictionaries are two copies in two files (a YAML anchor cannot cross files) | `fix-here`: the unused anchor is gone and `test_s17_and_s36_share_detection` keeps the copies equal |
| 3 | iw-reviewer, group 1 | Shipped-catalogue tests checked types only, not the weights or the `llm:` placement | `fix-here`: weights and bias pinned to design decision 10, `llm:` blocks pinned to S1.4, S1.5, S3.3, S3.4, integer YAML numbers cast to float |
| 4 | iw-reviewer, group 1, declined | An empty-string evidence passes the safety net (`"" in s`) | `wont-fix` for now: predates this change and no rule returns `""`; revisit if a rule ever builds evidence from a slice |
| 5 | iw-reviewer, group 1, declined | `generate_mocks.py` gives S1.5 severity `high` in one mock finding and `medium` in another; the catalogue uses `high` | `docs`: the mocks are a frozen test double (Damian's rule) and stay as they are; recorded here as a mock difference |
| 6 | iw-reviewer, group 2 | A page host of just `www.` built `website: https:///` and failed the whole finding | `fix-here`: `website` and `profile_url` go through `_url_or_none` (contract check, host check, length) |
| 7 | iw-reviewer, group 2 | `profile_url` was not bounded | `fix-here`: a URL longer than 200 characters becomes null (cutting would break it) |
| 8 | iw-reviewer, group 2, security | `urlsplit` reads `https://evil\@firm/` as host `firm`; browsers open `evil`, so a scraped profile or link could pose as the firm and route a scam post to M2 | `fix-here`: `http_host` rejects an authority with a backslash, whitespace or control characters |
| 9 | iw-reviewer, group 2 | `test_social_link_never_matches` could not fail, and `match_links` had no social filter | `fix-here`: `match_links` skips platform hosts; the test uses a firm that lists `instagram.com` |
| 10 | iw-reviewer, group 2 | Task 2.1 listed "`firm_own` ignores link hosts", which is routing | `fix-here`: moved to task 5.1 |
| 11 | iw-reviewer, group 2, declined | Handle matching on a short core name or alias could route an unrelated `@handle` to M2 | `new-item`: revisit with the real KNF loader (short or generic names) |
| 12 | iw-reviewer, group 2, declined | `_firm_by_handle` normalizes every firm on each call | `wont-fix` for now: three seed firms; cache the normalized names with the real KNF loader |
