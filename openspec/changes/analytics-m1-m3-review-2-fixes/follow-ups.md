# Follow-ups

Kacper's second review of PR #35 (20:11Z) and this change's own notes, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | Kacper, #35 review 2, smaller | M3 can be suppressed by naming the registered firm in every sentence of the offer: `third_party` "Alfa Inwestycje: kupuj ETF. Alfa Inwestycje: sprzedaj akcje." gives only an M1 finding (0.378) and no M3, and puts the firm's name in an M1 finding | `wont-fix` for the rules: an accepted evasion of the sentence-level attribution (design decision 9 of `analytics-m1-m3`); the LLM stage re-judges attribution ("whose offer is it") through the S3.3/S3.4 questions |
| 2 | this change | Cyrillic and Greek confusables (`Аlfa`, `Αlfa`) are not folded, so they reach only the fuzzy match or none | `new-item`: a confusables map (Unicode `confusables.txt`) with the real KNF loader |
| 3 | this change | A zero-width character in place of the space (`Alfa\u200bInwestycje`) folds to one word, which neither the name nor the fuzzy match sees | `wont-fix` for now: it renders as one word; revisit with the confusables map |
| 4 | Kacper, #35 review 2 | `save_findings` never deletes a module a re-analysis stops producing | `docs`: follow-up 35 of `analytics-m1-m3` (keep the old finding; mark superseded findings in the API/UI or a v1.1 field) |
| 5 | Kacper, #35 review 2, item 8 | Real-scale registry matching (one combined alternation for ~300 firms) | `new-item`: the stage-3 `analytics-knf-registry` change; here only the 200 KB scan cap and the once-per-call core tokens, to avoid colliding in `registry.py` |
| 6 | this change | A handle equal to a firm's name no longer routes to M2; an official handle list per firm (a registry column) would allow it again | `new-item`: with the real KNF loader |
