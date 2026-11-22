# Follow-ups

## Rule results that differ from the mock findings

`contracts/mocks/findings.json` stays as the web test double and is never edited or regenerated (Damian's rule). Task 8.1 runs the CLI to check these rows and adds any new ones. Every row is `keep-mock`: the mock is illustrative, and the rule follows ZASÓB and the specs.

| # | Mock document | Mock | Expected from this change | Why |
|---|---|---|---|---|
| M1 | `eurotrade` (`c99e2a35`) | R15 `fail`, `method: llm` | R15 `fail`, `method: rule` | `spodziewamy się` together with `wyników` is a strong-marker forecast, a deterministic fail that is never deferred |
| M2 | `eurotrade` | no R12a, no R12b | R12a `fail` (sub-checks `5 lat / 12 mies.` and `źródło`), R12b `fail` (no fee statement; currency not required for PLN, art. 44 ust. 4 lit. e) | ZASÓB R12a/R12b; the R14 detector finds `zarobili średnio 34% w 2025 roku` |
| M3 | `eurotrade` | no R11, no R16 | R11, R16 `not_applicable` | no comparison, no tax reference |
| M4 | `m2-bank-ok` (`5030107e`) | no R16 | R16 `pass`, quoting `Traktowanie podatkowe zależy…` | IKE is a tax reference, and both parts of the disclaimer are present |
| M5 | `m2-bank-ok` | no R11, R12a, R12b, R15 | all `not_applicable` | no trigger |
| M6 | `m2-alfa-landing` (`a3c88321`) | no R11, R12a, R12b, R15, R16 | all `not_applicable` | `Zarabiaj nawet do 18%` is R3's return claim, not a forecast (resolved question 2) |
| M7 | all M2 mocks | score | it changes because more applicable rules are in the denominator; `eurotrade` gains two medium fails | follows from M1-M6 |

## Items for later

| # | Item | Disposition |
|---|---|---|
| F1 | R13 (dominance of past performance) needs `blocks` (font size, position in the viewport) | `new-item`: with the visual rules R5, R7 and R8 (#29) |
| F2 | R9 (comprehensibility) has no cheap rules signal | `new-item`: an LLM-first change; `not_applicable` with `brak informacji o ryzyku` without risk information (stage-2 convention) |
| F3 | Detections are reported only in `rules[]`; the Polish summary does not list `Wykryto: prognozę, porównanie` | `new-item`: after `analytics-llm-p0` archives (it changes the same M2 finding assembly requirement) |
| F4 | The preprocessing ReDoS that Kacper found is outside the catalogue lint | `new-item`: fixed where it was reported; the timing test here covers only `rules/` |
| F6 | The stage-2 catalogue comment on R11 says "report the detection even when compliant", which Damian's answer 3 reverses (violations only) | `fix-here`: done; the R11 entry (group 6) replaced the comment |
| F5 | Lexical source and assumption markers are lenient (`opracowanie własne`, `w okresie`) | `new-item`: calibrate with the gold set |
| F7 | R12a's short-period markers match a period that is not the result's, inside a past-performance sentence (`…zyskał 9%, przy 3-miesięcznym okresie wypowiedzenia` gives `fail`), group 4 review | `new-item`: lexical by design; measure on the gold set before narrowing |
