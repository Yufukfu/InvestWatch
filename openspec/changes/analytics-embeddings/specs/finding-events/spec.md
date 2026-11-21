## MODIFIED Requirements

### Requirement: Which events per stored finding
After the commit the worker SHALL publish, for each finding reported `created`, one `finding.created` event. When the finding's `score` is at or above the module threshold, it SHALL also publish one `finding.high_risk` event with the same `data`, after the `finding.created` one, unless the alert is suppressed for a near-duplicate.

A finding reported `updated` (a redelivered or re-analysed document) SHALL publish nothing (coordinator decision, design §"Resolved questions").

**Near-duplicate alerts.** When the finding's document belongs to a near-duplicate group (document-analysis "Near-duplicate detection and grouping"), the publisher SHALL claim the group's alert for that module with an atomic Redis `SET iw:neardup:v1:alerted:{group_id}:{module} NX`, with TTL `NEARDUP_TTL_S`, before sending `finding.high_risk`:
- If the claim succeeds, it SHALL publish `finding.high_risk` as usual.
- If the key already exists, it SHALL NOT publish `finding.high_risk`. It SHALL log `high_risk_suppressed` with reason `neardup`, the finding id and the group id. The `finding.created` event and the stored finding, with its own `url`, are unchanged.
- If the claim raises a Redis error, the alert SHALL be published (fail open: no alert is lost).

Suppression is per module, so an M1 alert does not suppress an M3 alert for the same group. A document with no group, or a worker with no near-dup index, behaves as before.

#### Scenario: Low score
- **WHEN** a new M2 finding has score 0.3 and the M2 threshold is 0.5
- **THEN** only `finding.created` is published

#### Scenario: Score equal to threshold
- **WHEN** a new M2 finding has score 0.5 and the M2 threshold is 0.5
- **THEN** `finding.created` and then `finding.high_risk` are published

#### Scenario: Re-scan update
- **WHEN** a finding is reported `updated`
- **THEN** no event is published for it

#### Scenario: Near-duplicate of an alerted document
- **WHEN** a repost joins the group of an original whose M1 finding already fired `finding.high_risk`, and the repost's new M1 finding also scores above the M1 threshold
- **THEN** only `finding.created` is published for the repost, the log has `high_risk_suppressed` with reason `neardup`, and the stored repost finding keeps its own `url`

#### Scenario: Near-duplicate of a low-score original
- **WHEN** the original's finding scored below the threshold (no alert claimed) and its near-duplicate scores above it
- **THEN** the near-duplicate publishes `finding.high_risk`, and later members of the group do not

#### Scenario: Other module not suppressed
- **WHEN** a group has an alerted M1 finding and a member produces its first M3 finding above the M3 threshold
- **THEN** `finding.high_risk` is published for the M3 finding

#### Scenario: Claim fails open
- **WHEN** the Redis `SET … NX` for the claim raises a connection error
- **THEN** `finding.high_risk` is still published

#### Scenario: No near-dup index
- **WHEN** the worker runs without a near-dup index and two near-identical documents score above the threshold
- **THEN** each publishes `finding.high_risk`
