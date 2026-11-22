## MODIFIED Requirements

### Requirement: M3 score and hard gate
The M3 score SHALL be `σ(bias + Σ wᵢ·xᵢ)` with `bias` and weights from `m3_signals.yaml` (`x` as for M1), rounded to 3 decimals, ranking the Art. 76 elements: personalization together with a recommendation of instruments strongest, a recommendation of instruments alone strong, personalization alone weak, general education low. When S3.4 is neither `fail` nor `uncertain`, the score SHALL be at most 0.4 and the summary SHALL say it was capped. An `uncertain` S3.4 lifts the gate;

#### Scenario: Personalized paid recommendations
- **WHEN** the mock document `007bbcee…` is analyzed without a judge
- **THEN** the score is at least 0.7 (the M3 default threshold)

#### Scenario: Instrument recommendation alone is strong
- **WHEN** a page by an unregistered Polish entity has S3.4 `fail` (as the LLM will confirm it) and S3.2, S3.3 and S3.5 `pass`
- **THEN** the score is at least 0.7

#### Scenario: Personalization alone is weak
- **WHEN** a page has S3.3 `fail` and S3.4 `pass`
- **THEN** the score is at most 0.4 and the summary mentions the cap

#### Scenario: Both elements are strongest
- **WHEN** the same page has S3.3 and S3.4 both `fail`
- **THEN** its score is higher than with S3.4 `fail` alone

#### Scenario: Educational article is capped
- **WHEN** the M3 signals of the mock document `72acbb3b…` are scored
- **THEN** the score is at most 0.4 (the pipeline returns no finding for it, since it has no offer signal; requirement "Routing to modules" in `document-analysis`)

#### Scenario: Gate caps strong non-advisory signals
- **WHEN** a page has S3.1, S3.2, S3.5 and S3.6 `fail` and S3.3 and S3.4 `pass`
- **THEN** the score is exactly `min(σ(…), 0.4)` and the summary mentions the cap

#### Scenario: Mass signals without the LLM
- **WHEN** the mock document `cdbf5306…` is analyzed without a judge
- **THEN** the score is above 0.4 and below the score of the same results with S3.4 `fail`

#### Scenario: M3 score and hard gate: further obligations
- **WHEN** this requirement is applied
- **THEN** S3.3 alone SHALL NOT.
