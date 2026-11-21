# finding-events Specification

## Purpose
Tell the API, and through it the dashboard, about new findings as they happen. Analytics publishes on Redis Pub/Sub `iw:events` (`.docs/integration-plan.md` §6). It emits `finding.high_risk` from the live threshold in Redis (ADR 0305) and never computes `risk_level`.
## Requirements
### Requirement: Contract-valid events
Every message analytics publishes on `iw:events` SHALL be a JSON `event` envelope from `contracts/schemas/events.schema.json`. Its `type` is `finding.created` or `finding.high_risk`, `emitted_at` is the UTC ISO-8601 publish time, and `data` is a `finding_brief` with `id`, `module`, `score`, `title`, `url` and `platform`, taken from the persisted finding. `data` SHALL NOT contain `risk_level`.

#### Scenario: Schema check
- **WHEN** the publisher's messages for the stored mock findings are collected
- **THEN** each validates against `contracts/schemas/events.schema.json` (when `CONTRACTS_DIR` is set) and none carries `risk_level`

#### Scenario: Persisted id is used
- **WHEN** a finding is reported `created` by the store
- **THEN** the event's `data.id` equals the id of the stored row, read from the save result, not from the pipeline output

### Requirement: Which events per stored finding
After the commit the worker SHALL publish, for each finding reported `created`, one `finding.created` event. When the finding's `score` is at or above the module threshold, it SHALL also publish one `finding.high_risk` event with the same `data`, after the `finding.created` one. A finding reported `updated` (a redelivered or re-analysed document) SHALL publish nothing (coordinator decision, design §"Resolved questions").

#### Scenario: Low score
- **WHEN** a new M2 finding has score 0.3 and the M2 threshold is 0.5
- **THEN** only `finding.created` is published

#### Scenario: Score equal to threshold
- **WHEN** a new M2 finding has score 0.5 and the M2 threshold is 0.5
- **THEN** `finding.created` and then `finding.high_risk` are published

#### Scenario: Re-scan update
- **WHEN** a finding is reported `updated`
- **THEN** no event is published for it

### Requirement: Thresholds read live from Redis
For every finding that may emit `finding.high_risk`, the publisher SHALL read the Redis key `iw:settings:thresholds` without caching. The key is a Redis string written by the API, holding a JSON object such as `{"M1":0.6,"M2":0.5,"M3":0.7}` with values in 0-1. When the key is missing, is not valid JSON, or lacks a valid value for the finding's module, the default for that module SHALL apply (M1 0.6, M2 0.5, M3 0.7), logged once per read at level `WARNING` with the reason.

#### Scenario: Slider moved
- **WHEN** the key changes from M2 0.5 to 0.7 between two new findings that both score 0.6
- **THEN** the first emits `finding.high_risk` and the second does not

#### Scenario: Key missing
- **WHEN** `iw:settings:thresholds` does not exist and a new M3 finding scores 0.7
- **THEN** `finding.high_risk` is published using the default 0.7, and a warning names the reason `thresholds_missing`

#### Scenario: Malformed key
- **WHEN** the key holds `{"M2": "high"}`
- **THEN** M2 uses the default 0.5, and a warning names the reason `thresholds_invalid`

### Requirement: Publishing failure does not lose findings
Events SHALL be published only after the findings are committed. If publishing fails because Redis is unreachable, the findings SHALL stay committed, the failure SHALL be logged with reason `publish_failed` and the finding ids, and the worker SHALL continue to XACK as Redis allows. Events are at most once: the redelivery that follows reports the findings `updated` and does not republish.

#### Scenario: Redis drops after commit
- **WHEN** the commit succeeds and the PUBLISH call raises a connection error
- **THEN** the finding row exists, the log carries `publish_failed` with its id, and no exception escapes the worker loop

### Requirement: No-op publisher
A no-op publisher with the same interface SHALL exist for the CLI and tests. It records the events it would have sent and sends nothing.

#### Scenario: Worker test without Redis Pub/Sub
- **WHEN** the worker runs with the in-memory store and the no-op publisher
- **THEN** the recorded events equal the events the Redis publisher would send for the same input

