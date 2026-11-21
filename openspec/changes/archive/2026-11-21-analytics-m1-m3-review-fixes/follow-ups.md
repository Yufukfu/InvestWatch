# Follow-ups

Kacper's review of PR #35 (6da4f1f) and the reviewer's out-of-scope notes on this change, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | Kacper, #35 item 1 | `preprocessing.py` `_BOUNDARY` (sentence split) is quadratic on long whitespace runs; every document goes through it before M1-M3 | `fix-here` in #26 (`analytics-worker`, commit d9770ce: linear lookahead, regression tests in `tests/test_redos.py`); #35 merges after #26 and gets it through the worker merge |
| 2 | Kacper, #35 item 2 | The registry claim was stated as fact on a 3-firm fictional registry | `fix-here`: "nie znaleziono w załadowanym rejestrze firm", "(dane demonstracyjne)" from `Registry.demo`; a ~30-firm CSV and the real KNF loader are stage 3 |
| 3 | Kacper, #35 item 11 | `.docs/security-audit.md` has no analytics entry | `fix-here` in #26 (item 3 of Kacper's #26 review) |
| 4 | this change, reviewer | The frozen mocks (`contracts/mocks/generate_mocks.py`, `findings.json`, `events.json`, the `web/` fixtures) still say `Podmiot spoza rejestru` (S3.1 name and M3 titles) and "Podmiot nie występuje w rejestrze firm inwestycyjnych KNF" (summary), while the pipeline now says `Podmiot nieznaleziony w rejestrze` and "nie znaleziono w załadowanym rejestrze firm" | `docs`: the mocks stay as they are (read-only test double); a mock difference like those in the archived `analytics-m1-m3` follow-ups rows 28-34 |
| 5 | reviewer | M1 texts stated the converse fact ("firma z rejestru KNF") on the demo registry | `fix-here`: "z załadowanego rejestru firm", with "(dane demonstracyjne)" in the M1 summary while the seed is loaded |
| 6 | reviewer, pre-existing | The CLI crashed with `UnicodeEncodeError` on Windows when stdout is redirected (an emoji in mock `3c41441c…`, cp1250) | `fix-here`: stdout is reconfigured to UTF-8 before the findings are written |
| 7 | reviewer | A web-page author with only a `profile_url` lost the page host as advertiser name | `fix-here`: the host fallback depends only on the page not being a platform page |
| 8 | reviewer, declined | `subscriptions?` in S3.5 also fires on a free newsletter subscription | `wont-fix` for now: mirrors the Polish `subskrypcja`; without S3.4 the M3 score stays at most 0.4 |
