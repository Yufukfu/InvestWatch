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
| 13 | iw-reviewer, group 3 | The shared S1.7/S3.6 currency regex missed `500 złotych`, `2 tys. zł`, `1000 zl` | `fix-here`: word forms, `tys./mln/mld` and `zl` matched; tests for each |
| 14 | iw-reviewer, group 3 | The "English ad of a Polish brokerage house" scenario used EuroTrade (a foreign branch) and did not check the score | `fix-here`: Alfa Inwestycje test, the score equals the score without S1.7 |
| 15 | iw-reviewer, group 3 | The evidence-in-declared-fields tests held by construction (the safety net nulls any other quote) | `fix-here`: replaced by tests that no metadata quote is demoted by the safety net |
| 16 | iw-reviewer, group 3, declined | `guess_language` returns `pl` on a 0/0 tie (emoji- or name-only text), so S1.7 keeps such a foreign-firm candidate | `wont-fix` for now: keeping a candidate is the safe side for an inventory; revisit with per-sentence language (skeleton follow-up 7) |
| 17 | iw-reviewer, group 3, declined | The S1.3 label `partner` also matches neutral uses (`partner Ekstraklasy`) | `new-item`: check on real posts; the label raises certainty only, it never creates an M1 candidate by itself |
| 18 | iw-reviewer, group 4 | S3.4 candidates on non-advice text: `akcja promocyjna`, `opcja roczna`, course `certyfikat`, descriptive `kupują` | `fix-here`: narrower instrument and verb patterns, negative tests |
| 19 | iw-reviewer, group 4 | Attribution saw only the first S3.3/S3.4 candidate | `fix-here`: `candidates()` on the rules; any candidate sentence without the firm name makes the offer the publisher's |
| 20 | iw-reviewer, group 4 | A bare `ankieta` (a broker's MiFID questionnaire) made S3.3 a candidate and filed M3 against the influencer | `fix-here`: `ankieta inwestycyjna` / `ankieta o Twoich celach` only |
| 21 | iw-reviewer, group 4 | A negation swallowed a later recommendation in the same sentence (`nie rekomendujemy X, ale kupuj ETF`) | `fix-here`: the negation span stops at `,` or `;` |
| 22 | iw-reviewer, group 4 | Common recommending forms missed (`sprzedajcie`, `trzymajcie`, `warto kupić`, `polecamy akcje`, `zainwestuj w`) | `fix-here`: added with tests; spec wording now "such as" |
| 23 | iw-reviewer, group 4 | `has_advisory` counts `fail`/`uncertain`, design decision 2 said "not `pass`" | `docs`: design text aligned with the code |
| 24 | iw-reviewer, group 4, declined | `Kupuj BTC. Akcje są nudne.` is an S3.4 candidate (an instrument noun in the next sentence) | `wont-fix` for now: the ±1 window is the spec; the LLM question on S3.4 refines it |
| 25 | iw-reviewer, group 4, declined | No English S3.4 dictionary (`buy … shares`) | `new-item`: add with the English dictionary review |
| 26 | iw-reviewer, group 4, declined | "Wynik ograniczony do 0,4" is printed even when the raw score is already below 0.4 | `wont-fix` for now: the spec asks the summary to say the gate applied; wording can soften later |
| 27 | iw-reviewer, group 4, declined | S3.1 on a social URL with no author has null evidence | `wont-fix`: the platform host is not the entity; null evidence with the explanation is the honest result |
