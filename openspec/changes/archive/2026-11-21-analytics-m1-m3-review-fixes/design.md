## Context

Review fixes for PR #35 (`analytics-m1-m3`); the decisions of the archived change stand except where a review item below changes them. Kacper's items and the coordinator's rulings are in `proposal.md`; ADR 0308 records the M3 gate.

## Decisions

1. **Demonstration data is a property of the loaded registry**, not of a file path: `Registry.demo` is true when no firm has a `source_url`. The real KNF loader sets one per firm, so the "(dane demonstracyjne)" note disappears without a code change. A path check (`seed.csv`) was rejected because the image and tests point `REGISTRY_CSV` at other paths.
2. **The excerpt starts a quarter of its length before the earliest evidence in the text**, so it reads as the passage that triggered the finding; quotes from metadata (handles, links) have no position and are ignored; without any, the start of the text is used as before.
3. **Registered in Poland, for routing**, means `brokerage_house`, `brokerage_bank` and `foreign_branch`. A `foreign_no_branch` firm is reachable only through third-party ads (M1, with the Polish-marker filter); its own material is out of scope.

## Resolved Questions

- **Which firms' own material is M2?** Opis p.1: M2 covers materials "publikowanych bezpośrednio przez zarejestrowane w Polsce firmy inwestycyjne (w tym polskie oddziały firm zagranicznych)". So a branch's own page is M2 and a `foreign_no_branch` firm's own page is not (item 12, coordinator, on Damian's instruction).
- **Where does the Polish-language limit apply?** Opis p.1 names under M1 "polskojęzyczne reklamy zagranicznych firm inwestycyjnych działających w Polsce transgranicznie": cross-border firms, i.e. `foreign_no_branch`; branches are registered in Poland and are in M1 scope in any language (item 6, Kacper's reading, accepted by the coordinator).
- **Is M3 "advice" or "may indicate advice"?** "May indicate" (Opis "mogących wskazywać"); ADR 0308.
