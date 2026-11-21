# Follow-ups

Out-of-scope reviewer findings and "declined to judge" items, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | Kacper, re-review | Narrow the `stra` stem in the denial exclusion (`strategia`, `straż`) | `wont-fix`: the exclusion ends on that word, which is never a risk word, so no R3 outcome changes (an equivalent mutant) |
| 2 | Kacper, re-review | Ship the seed registry inside the package (`importlib.resources`) | `wont-fix` for now: the seed is fictional test data; the error now says to set `REGISTRY_CSV` and images set it (follow-up #3 of `analytics-skeleton`) |
| 3 | iw-reviewer | `Nie ma ryzyka.` alone is now a denial (it was read as a warning before) | `docs`: intended, "there is no risk" denies risk; listed in the R3 tests |
| 4 | iw-reviewer, declined | Whether `ryzyka` as nominative plural after a denial word is ever a real warning | `wont-fix` for now: no realistic example; revisit with the gold set |
| 5 | iw-reviewer, declined | The CLI's "analysis failed" line drops the traceback | `wont-fix`: a traceback can carry scraped text; the type, the document id and exit 1 are enough to reproduce with the document |
| 6 | iw-reviewer, declined | English denials beyond `no risk` / `risk-free` (`without risk`) | `new-item`: add with the English dictionary review |
| 7 | iw-reviewer, can't verify | Real KNF rows with an empty or punctuation-only name core | `new-item`: check when the real KNF loader lands; such a name never fuzzy-matches now |
