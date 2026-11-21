## MODIFIED Requirements

### Requirement: Collect active sources only
A source SHALL be collectable only when its record has `active = true` and either `platform = web` or a `platform` that a registered social collector accepts for the host of its URL (`social-collection`). Selection is a pure function over source records (reading them from PostgreSQL and re-checking at job start belong to `scraper-orchestration`). A source with `schedule_cron = null` is manual only: it is never selected for scheduled runs.

#### Scenario: Inactive source is skipped
- **WHEN** a run starts and the source has `active = false`
- **THEN** no request is made to that source's URL

#### Scenario: Non-web source is skipped
- **WHEN** a run starts for an active source with a `platform` other than `web` and no social collector is registered for the host of its URL
- **THEN** no request is made and no job error is recorded for it

#### Scenario: Social source with a collector is selected
- **WHEN** a run starts for an active source with `platform = other` and a collector registered for its host
- **THEN** the source is collectable

#### Scenario: Manual-only source is not scheduled
- **WHEN** the scheduler plans runs and an active web source has `schedule_cron = null`
- **THEN** it is not selected for scheduled runs
