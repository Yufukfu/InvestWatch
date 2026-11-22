# 0315. M2: one owner per art. 44 element; R15 reports every forecast, R11 only violations

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written (change `analytics-m2-p1-rules`, stage 3); accepted by Damian via the PR that applies `analytics-m2-p1-rules`

## Context

The challenge criteria (`doc/ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.docx`, ZASÓB) split art. 44 of Delegated Regulation 2017/565 into 18 rules. Several of those rules check different elements of the same paragraph:

- **R12a, R12b, R13 and R14** all check ust. 4 (past performance): the period and source, currency and fees, prominence, and the disclaimer.
- **R3, R6 and R14** can all see the same warning text.

Stage 2 (`analytics-llm-p0` design §1a, resolved questions 4 and 6) settled two cases: a missing risk warning is counted by R3 alone, and a footnote-only placement belongs to R6. It did not settle the general rule, or the ust. 4 split, which this stage builds.

ZASÓB uses different reporting wording for two rules. R15 says "Flaguje w raporcie wykrycie prognozy przyszłych wyników", so the detection itself is flagged. R11 says "flaguje naruszenia w raporcie", so only violations are flagged. Damian confirmed this reading on 2026-11-21. `Finding` v1 (`contracts/schemas/finding.schema.json`) has one `rules[]` entry per rule, with `result ∈ {pass, fail, uncertain, not_applicable}` and `evidence`. Contracts are frozen (`CLAUDE.md`). The M2 score (`analytics/src/investwatch_analytics/modules/m2.py`) counts `uncertain` as half a fail.

## Options considered

Ownership:

1. **Each rule checks everything its ZASÓB line mentions.** R14 would also check the period, and R12a the disclaimer. Then one missing disclaimer fails two rules and is weighted twice in the score.
2. **One owner per element.** Rules that share a paragraph share one trigger detector, so they agree on applicability. Each rule checks only its own elements. Several missing elements inside one rule make one `fail` that lists them. This continues the stage-2 decisions.

Reporting a compliant forecast (R15):

1. **`uncertain` for every detection.** A lawful forecast becomes half a violation and lifts the page's score.
2. **A new result value or flag field.** This is a contract change after the freeze, and needs a version bump and the whole team.
3. **A line in the Polish summary.** This edits the M2 finding assembly requirement in `document-analysis`, which `analytics-llm-p0` is changing at the same time.
4. **`pass`, with `evidence` quoting the detected forecast, and an explanation that starts with `Wykryto prognozę`.** This uses only v1 fields, and it shows in the dashboard's rule list.

## Decision

- **Ownership, option 2.** The owner map is in `openspec/changes/analytics-m2-p1-rules/design.md` decision 1. In short: R3 owns the risk warning next to a claim. R6 owns placement. R12a owns the 5 years, the 12-month basis, the reference period and the source. R12b owns currency and fees. R13 owns prominence. R14 owns the disclaimer. R15 owns the forecast warning. R11 owns the comparison source and assumptions. R16 owns the tax disclaimer. R12a, R12b and R14 share R14's past-performance detector.
- **Reporting, option 4, for R15 only.** R11 flags only violations, so a compliant comparison is a plain `pass`: it stores the quoted comparison as `evidence`, and its explanation is not a `Wykryto…` flag. With no detection, either rule is `not_applicable` with null evidence.

The rationale for each option is above: options 1 double-weight a violation or inflate the score, option 2 of reporting breaks the frozen contract, and option 3 collides with an in-flight spec. Ownership option 2 and reporting option 4 fit the stage-2 principle and contract v1 as they stand.

## Consequences

- Each failing rule names one legal element, so the dashboard can explain a finding element by element, and the score weights each violation once.
- A compliant comparison or forecast slightly lowers the M2 score, because `pass` is applicable in the denominator. That is intended: a compliant page should not look riskier.
- Adding R13 later needs only the prominence check. The trigger is already shared.
- Revisit this if the team bumps the contract and adds a detection flag field.
