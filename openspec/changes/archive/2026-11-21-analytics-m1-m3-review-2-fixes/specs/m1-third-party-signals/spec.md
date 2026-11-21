## MODIFIED Requirements

### Requirement: S1.6 author other than the firm
S1.6 SHALL be `fail` on every M1 finding that has an author or a non-social page host, quoting `author.handle`, else `author.name`, else the page host from `url` (a publisher that is the firm is routed to M2, never to M1). When the author handle equals the matched firm's name but no domain proves the account is the firm's, S1.6 SHALL be `uncertain`, quoting the handle. It SHALL be `not_applicable` when there is no author and the page host is a social platform.

#### Scenario: Finfluencer handle
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** S1.6 is `fail` with evidence `@inwestor_jan` from `author.handle`

#### Scenario: Social post without author
- **WHEN** a Polish Instagram `third_party` post names a firm and has no `author`
- **THEN** S1.6 is `not_applicable`

#### Scenario: Handle like the firm's name
- **WHEN** a third-party post about Alfa Inwestycje is by `@alfainwestycje` and nothing on the firm's domain backs it
- **THEN** S1.6 is `uncertain` with evidence `@alfainwestycje` and an explanation that the account is not confirmed as the firm's
