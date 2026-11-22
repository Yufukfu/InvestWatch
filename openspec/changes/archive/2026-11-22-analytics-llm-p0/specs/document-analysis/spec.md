## MODIFIED Requirements

### Requirement: M2 finding assembly
The M2 finding SHALL list only the results of implemented rules. It SHALL carry the raw `score` (never `risk_level`), the matched firm (or `null`), a Polish title and summary, `status: new`, the `url` and `platform` copied from the document, `content_excerpt` of at most 500 characters, and `model.llm`. The score SHALL be `Σ(weight·fail) / Σ(weight·applicable)` with weights high 3, medium 2, low 1, where `uncertain` counts as half a fail and `not_applicable` is excluded.

#### Scenario: Violating landing page
- **WHEN** the mock document `m2-alfa-landing` (id `a3c88321-…`) is analyzed rules-only
- **THEN** the finding has R1 `pass`, R2 `fail`, R3 `fail`, R4 `fail`, R6 `fail`, R18 `fail` and a score above 0.5

#### Scenario: Compliant material
- **WHEN** the mock document `m2-bank-ok` (id `5030107e-…`) is analyzed
- **THEN** no rule result is `fail`, R4 and R6 are `not_applicable`, and the score is 0

#### Scenario: Builder without a firm match
- **WHEN** the M2 builder is called directly with a context that has no firm match
- **THEN** the finding has `firm: null` and R1 `fail`
- **AND** the pipeline never produces an M2 finding with `firm: null`, because routing sends only registered firms to M2

#### Scenario: Firm matched by domain only
- **WHEN** a `firm_own` page on the Alfa domain does not name the firm in its text
- **THEN** the M2 finding has the Alfa firm and R1 `fail`

#### Scenario: Rule that does not apply
- **WHEN** R3 is `not_applicable`
- **THEN** the summary does not list R3 among the checked rules and says it does not apply
- **AND** the summary SHALL name as checked only the rules that applied, and name `not_applicable` rules separately
- **AND** when no rule applies (every rule is `not_applicable`), the score is 0

#### Scenario: LLM used
- **WHEN** `m2-alfa-landing` is analyzed with a stub judge whose valid R17 verdict is merged and `LLM_MODEL=gemma3:4b`
- **THEN** `model.llm` is `gemma3:4b` and the summary names the model and R17
- **AND** `model.llm` SHALL be the configured `LLM_MODEL` only when at least one rule result of the finding has `method` `llm` or `hybrid`

#### Scenario: LLM configured but not used
- **WHEN** the judge is configured and the endpoint is down
- **THEN** `model.llm` is `null` and the summary says the check ran rules-only
- **AND** `model.llm` SHALL be `null` whenever the LLM is disabled, nothing was deferred, or the LLM failed
