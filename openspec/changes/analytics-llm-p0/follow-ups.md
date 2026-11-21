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
