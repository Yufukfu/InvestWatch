# Follow-ups

| # | Source | Finding | Disposition |
|---|---|---|---|
| 1 | review | `.docs/analytics-plan.md` §2 row 1 says "normalize (Unicode NFKC, ...), dedup by `content_hash`", which reads as an NFKC hash; the file is Damian's | `new-item`: Damian adds "(NFKC for matching only; `content_hash` is NFC, ADR 0105)" together with the analytics change proposed in issue #31 |
| 2 | review | `analytics/` `content_hash` still NFKC (`preprocessing.py`) | `new-item`: issue #31, Damian |
| 3 | review | `assert content_hash(text) != content_hash(folded)` is redundant with the literal assertion | `wont-fix`: it states the intent (not folded) next to the literal; harmless |
