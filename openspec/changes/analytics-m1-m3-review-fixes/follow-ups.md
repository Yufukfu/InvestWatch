# Follow-ups

Kacper's review of PR #35 (6da4f1f) and the reviewer's out-of-scope notes on this change, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | Kacper, #35 item 1 | `preprocessing.py` `_BOUNDARY` (sentence split) is quadratic on long whitespace runs; every document goes through it before M1-M3 | `fix-here` in #26 (`analytics-worker`, commit d9770ce: linear lookahead, regression tests in `tests/test_redos.py`); #35 merges after #26 and gets it through the worker merge |
| 2 | Kacper, #35 item 2 | The registry claim was stated as fact on a 3-firm fictional registry | `fix-here`: "nie znaleziono w załadowanym rejestrze firm", "(dane demonstracyjne)" from `Registry.demo`; a ~30-firm CSV and the real KNF loader are stage 3 |
| 3 | Kacper, #35 item 11 | `.docs/security-audit.md` has no analytics entry | `fix-here` in #26 (item 3 of Kacper's #26 review) |
| 4 | this change | The S3.1 signal name changed from `Podmiot spoza rejestru` (as in the frozen mocks) to `Podmiot nieznaleziony w rejestrze` | `docs`: the mocks stay as they are (read-only test double); a mock difference like those in the archived `analytics-m1-m3` follow-ups rows 28-34 |
