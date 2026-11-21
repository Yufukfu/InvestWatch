# 0315. M2: one owner per art. 44 element, and a compliant detection is a pass that quotes it

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written (change `analytics-m2-p1-rules`, stage 3); accepted by Damian via the PR that applies `analytics-m2-p1-rules`

## Context

The challenge criteria (`doc/ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.docx`, ZASÓB) split art. 44 of Delegated Regulation 2017/565 into 18 rules. Several of those rules check different elements of the same paragraph:

- **R12a, R12b, R13 and R14** all check ust. 4 (past performance): the period and source, currency and fees, prominence, and the disclaimer.
- **R3, R6 and R14** can all see the same warning text.

Stage 2 (`analytics-llm-p0` design §1a, resolved questions 4 and 6) settled two cases: a missing risk warning is counted by R3 alone, and a footnote-only placement belongs to R6. It did not settle the general rule, or the ust. 4 split, which this stage builds.

ZASÓB also says that two rules report a detection. R15 says "Flaguje w raporcie wykrycie prognozy przyszłych wyników". R11 says "flaguje naruszenia w raporcie". `Finding` v1 (`contracts/schemas/finding.schema.json`) has one `rules[]` entry per rule, with `result ∈ {pass, fail, uncertain, not_applicable}` and `evidence`. Contracts are frozen (`CLAUDE.md`). The M2 score (`analytics/src/investwatch_analytics/modules/m2.py`) counts `uncertain` as half a fail.

## Options considered

Ownership:

1. **Each rule checks everything its ZASÓB line mentions.** R14 would also check the period, and R12a the disclaimer. Then one missing disclaimer fails two rules and is weighted twice in the score.
2. **One owner per element.** Rules that share a paragraph share one trigger detector, so they agree on applicability. Each rule checks only its own elements. Several missing elements inside one rule make one `fail` that lists them. This continues the stage-2 decisions.

Reporting a compliant detection:

1. **`uncertain` for every detection.** A lawful forecast becomes half a violation and lifts the page's score.
2. **A new result value or flag field.** This is a contract change after the freeze, and needs a version bump and the whole team.
3. **A line in the Polish summary.** This edits the M2 finding assembly requirement in `document-analysis`, which `analytics-llm-p0` is changing at the same time.
4. **`pass`, with `evidence` quoting the detected comparison or forecast, and an explanation that starts with `Wykryto…`.** This uses only v1 fields, and it shows in the dashboard's rule list.

## Decision

- **Ownership, option 2.** The owner map is in `openspec/changes/analytics-m2-p1-rules/design.md` decision 1. In short: R3 owns the risk warning next to a claim. R6 owns placement. R12a owns the 5 years, the 12-month basis, the reference period and the source. R12b owns currency and fees. R13 owns prominence. R14 owns the disclaimer. R15 owns the forecast warning. R11 owns the comparison source and assumptions. R16 owns the tax disclaimer. R12a, R12b and R14 share R14's past-performance detector.
- **Reporting, option 4,** for R11 and R15. With no detection the rule is `not_applicable` with null evidence.

The rationale for each option is above: options 1 double-weight a violation or inflate the score, option 2 of reporting breaks the frozen contract, and option 3 collides with an in-flight spec. Ownership option 2 and reporting option 4 fit the stage-2 principle and contract v1 as they stand.

## Consequences

- Each failing rule names one legal element, so the dashboard can explain a finding element by element, and the score weights each violation once.
- A compliant comparison or forecast slightly lowers the M2 score, because `pass` is applicable in the denominator. That is intended: a compliant page should not look riskier.
- Adding R13 later needs only the prominence check. The trigger is already shared.
- Revisit this if the team bumps the contract and adds a detection flag, or if Damian reads R11's "flaguje naruszenia" as flagging violations only (open question 3 in the change's design).
