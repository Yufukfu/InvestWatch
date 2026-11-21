# Follow-ups

## Rule results that differ from the mock findings

`contracts/mocks/findings.json` stays as the web test double and is never edited or regenerated (Damian's rule). The rows below are differences expected from the specs of this change. Task 13.0 checks them against the real CLI output and adds any new ones. Each row's disposition is `keep-mock`: the mock is illustrative, and the rule follows ZASÓB and the specs.

| # | Mock document | Mock result | Expected from this change | Why |
|---|---|---|---|---|
| 1 | `m2-alfa-landing` (`a3c88321`) | R3 `fail`, `method: hybrid` | R3 `fail`, `method: rule` | A footnote-only warning is never deferred to the LLM (R3 requirement; ZASÓB: the warning must "bezpośrednio towarzyszy" the claim). |
| 2 | `m2-alfa-landing` | R5 `fail`, R8 `fail` | not in `rules[]` | R5 and R8 are P1 and not implemented here. |
| 3 | `m2-alfa-landing` | R17 `fail`, `method: llm` | rules-only: R17 `pass`; with the LLM: whatever the judge decides (`hybrid`) | A bare "pod nadzorem KNF" is not a violation on its own (ZASÓB). Only the LLM classifies the use. |
| 4 | `m2-alfa-landing` | R18 `fail`, `method: llm` | R18 `fail`, `method: rule` | A safety word in the same sentence as the supervisor mention is a deterministic fail that is not deferred. |
| 5 | `eurotrade` (`c99e2a35`) | R3 `uncertain`, `method: llm` | rules-only R3 as the skeleton computes it; LLM only if the case is near-window | R3 is deferred only in the borderline proximity case. |
| 6 | `eurotrade` | R7 `fail`, R15 `fail` | not in `rules[]` | R7 and R15 are P1. |
| 7 | `eurotrade` | no R4, no R6 | R4 `not_applicable` (the risk block has `visible: false`, which is R5's concern); R6 `pass` (the risk block is in `region: main`) | R4 measures only visible risk blocks. R6 judges placement only, not visibility or interaction. |
| 8 | `m2-bank-ok` (`5030107e`) | R4, R6 `not_applicable` only; score 0.12 | also R10 `pass`, R14, R17, R18 `not_applicable`; score 0 | More rules are implemented, and none fails. |
| 9 | all M2 mocks | `model.llm: gemma3:4b`, `embedder: bge-m3` | `model.llm` is the configured model only when an LLM verdict was merged, otherwise `null`; `embedder: null` | `model.llm` reflects actual LLM use (M2 finding assembly requirement). There are no embeddings in this change. |

## Review findings

| # | Source | Item | Disposition |
|---|---|---|---|
| R1 | review group 1 | `_YEAR` read amounts like `2000 zł` as years | `fix-here`: a year counts only in a year context (`w/za/od 2025`, `2025 r.`, `2025 roku`) |
| R2 | review group 1 | Offer deadlines and imperative promises in the fetch year (`do końca 2026`, `Zyskaj 20% w 2026 roku`) read as past performance | `fix-here`: future markers `zyskaj`, `zarabiaj`, `możesz`, `nawet`, `ważn…`, `do (końca) <date/year>` |
| R3 | review group 1 | Non-return percentages (share of clients or accounts, bonuses, the ESMA CFD warning `74% rachunków…`) read as return figures | `fix-here`: R14-only `figure_extra_exclude_patterns` |
| R4 | review group 1 | The aliased R3 exclude list silently changes R14 | `fix-here`: comment on the anchor; R14-only excludes live in their own key |
| R5 | review group 1 | Disclaimers missed: `Osiągnięte w przeszłości wyniki nie gwarantują…`, `Past results / Historical returns are not indicative…` | `fix-here`: two disclaimer patterns (shared with R6) |
| R6 | review group 1 | No test with a past and a future marker in one sentence | `fix-here`: test added |
| R7 | review group 1 | tasks.md 1.2 named the wrong parameter keys | `fix-here` |
| R8 | review group 1, declined | `\bcel\w*\b` also matches `celowo`, `celny` | `wont-fix` for now: low impact, it only makes a year-only sentence not past performance |
| R9 | review group 1, declined | Absolute-amount past returns (`przyniósł 5 000 zł zysku`) are not return figures | `new-item`: decide with the gold set whether R14 needs amounts |
| R10 | review group 1, declined | R3 shares the percentage false positives (bonus, share of clients) | `new-item`: R3 claim excludes, outside this change's R3 scope |
| R11 | review group 2 | `_YEAR` still read an amount after a preposition (`od 2000 zł`, `z 2000 zł`, `za 2000 PLN`) as a year | `fix-here`: currency lookahead after the year |
| R12 | review group 2 | `ważn…` as a future marker hid real past performance (`Ważne: …12% w 2024 r.`) | `fix-here`: narrowed to `ważn… do`; `dał/dała…` added as past verbs |
| R13 | review group 2 | R6 (and R4) quoted the whole block, not the risk sentence | `fix-here`: `warning_quote` quotes the first warning sentence inside the located block |
| R14 | review group 2, declined | A current-year promotion (`Lokata 7% w 2026 r.` fetched in 2026) counts as past performance | `wont-fix` for now: follows the spec's "not later than the fetch year"; revisit with the gold set |
| R15 | review group 2, declined | A viewport with blocks but no risk block is skipped (warning missing on desktop, exposed on mobile gives `pass`) | `new-item`: a warning missing from a whole viewport is R8 (responsiveness, P1) |
| R16 | review group 2, declined | A footnote-marked block in the main region and in view on load passes R6 | `wont-fix`: follows the spec's AND rule (placement and not in view) |
| R17 | review group 2, declined | The `hiding_regions` default is in both the code and the YAML | `wont-fix`: the YAML is the source; the code default only guards a missing key |
| R18 | review group 2, can't verify | Whether the scraper fills `region` and `in_viewport_on_load`; without `region`, R6 passes | `new-item`: confirm with Adam when the `blocks` shape is settled |
| R19 | review group 3 | The currency lookahead `tys` also matched `tysiące`, so real past performance was missed | `fix-here`: `tys(?:\.|\b)` |
| R20 | review group 3 | A 0 px median forced the ratio to 1.0 (pass); negative sizes were measured | `fix-here`: blocks of 0 px or less never set the dominant size; a visible risk block with no positive size gives `uncertain` |
| R21 | review group 3 | The displayed ratio was rounded (`0,75×` on a fail against 0,75) | `fix-here`: truncated to 3 decimals |
| R22 | review group 3 | The R4 requirement said "the risk block's text" while the code quotes the warning sentence | `fix-here`: spec and design updated |
| R23 | review group 3, can't verify | Container blocks from the scraper (body plus warning in one block) make R4 pass on the container's size | `new-item`: with follow-up R18 (block granularity, Adam) |
| R24 | review group 3, declined | The lower weighted median makes R4 lenient on a 50/50 split | `wont-fix` for now: threshold policy for the gold set |
| R25 | review group 3, declined | The loader ignores unknown top-level YAML keys (`shared:` lists no rule references are never validated) | `wont-fix`: predates the change; `test_catalogue_is_complete` catches a mistyped `rules:` key |
