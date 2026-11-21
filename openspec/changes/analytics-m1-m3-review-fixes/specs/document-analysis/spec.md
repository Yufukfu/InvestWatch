## MODIFIED Requirements

### Requirement: Routing to modules
Analytics SHALL route by publisher identity and registry result, not by `source_kind` alone (design decisions 1-2). The publisher is a registry firm when the author's `profile_url` host or a non-social page host is one of the firm's `website_domains` (equal or subdomain), or the normalized author handle equals a normalized name, core name or alias of the firm. Analytics SHALL run:
- M2 for the publisher firm when the publisher is a registry firm, whatever the `source_kind`;
- M2 for a `firm_own` document that the registry matches by text or page host;
- no module for the own material (either of the two cases above) of a foreign firm without a Polish branch (`foreign_no_branch`): M2 covers firms registered in Poland, including Polish branches of foreign firms, and such a firm is authorized, so it is not M3 either; the document SHALL produce no finding and log the reason `out_of_scope_m2_foreign_no_branch`;
- M1 for a `third_party` or `unknown` document whose publisher is not a registry firm and that mentions a registry firm by text or link host, unless the matched firm is a foreign firm without a Polish branch (`registry_type` `foreign_no_branch`) and the document does not target Poland (S1.7 `pass`), in which case it SHALL produce no finding and log the reason `not_targeting_poland`; a firm registered in Poland (`brokerage_house`, `brokerage_bank`, `foreign_branch`) stays in M1 scope whatever the language;
- M3 for a document whose publisher is not a registry firm and that the registry does not match, including an unmatched `firm_own` document, which SHALL never go to M2;
- M3 in addition to M1 when the M1 document carries an S3.3 or S3.4 candidate attributed to the publisher (requirement "M3 alongside M1" in `m3-unauthorized-advice-signals`).
An M3-only document whose advisory signals S3.2, S3.3, S3.4, S3.5 and S3.8 are all `pass` SHALL produce no finding and log the reason `no_signals`. A document SHALL produce at most one finding per module. The reason `module_not_implemented` SHALL no longer be logged.

#### Scenario: Firm's own page
- **WHEN** a `firm_own` document on a registered firm's domain is analyzed
- **THEN** exactly one M2 finding is returned

#### Scenario: Own material of a foreign firm without a branch
- **WHEN** a `firm_own` page on the domain of a `foreign_no_branch` firm, or a post by that firm's own account, is analyzed
- **THEN** no finding is returned and the log names the reason `out_of_scope_m2_foreign_no_branch`

#### Scenario: Third-party ad of a foreign firm without a branch
- **WHEN** a Polish third-party post advertises a `foreign_no_branch` firm
- **THEN** exactly one M1 finding is returned

#### Scenario: Own page of a foreign branch
- **WHEN** a `firm_own` page on the domain of a `foreign_branch` firm is analyzed
- **THEN** exactly one M2 finding is returned

#### Scenario: Firm's own page without a registry match
- **WHEN** a `firm_own` document matches no registry firm and has advisory vocabulary
- **THEN** exactly one M3 finding is returned and no M2 finding

#### Scenario: Unmatched own page without advisory signals
- **WHEN** a `firm_own` document matches no registry firm and has no advisory signal
- **THEN** no finding is returned and the log names the reason `no_signals`

#### Scenario: Firm's own social account
- **WHEN** a `third_party` Instagram post names Alfa Inwestycje and its author has handle `@alfainwestycje`
- **THEN** exactly one M2 finding for the Alfa firm is returned and no M1 finding

#### Scenario: Third-party post about a registered firm
- **WHEN** the mock document `3c41441c…` (`third_party`, names EuroTrade) is analyzed
- **THEN** exactly one finding is returned, with `module` M1

#### Scenario: Foreign firm's ad not aimed at Poland
- **WHEN** an English third-party post on a `.com` host names a `foreign_no_branch` firm and has no PLN amount, `+48` number or Polish text
- **THEN** no finding is returned and the log names the reason `not_targeting_poland`

#### Scenario: Foreign branch advertised in English
- **WHEN** the same English post names EuroTrade (`foreign_branch`)
- **THEN** exactly one M1 finding is returned

#### Scenario: Polish brokerage house advertised in English
- **WHEN** an English third-party post on a `.com` host names Alfa Inwestycje (`brokerage_house`) and has no Polish marker
- **THEN** exactly one M1 finding is returned, with S1.7 `pass`

#### Scenario: Unknown-source page of an unregistered entity
- **WHEN** the mock document `007bbcee…` (`unknown`, no registry firm) is analyzed
- **THEN** exactly one finding is returned, with `module` M3

#### Scenario: Unmatched post without advisory signals
- **WHEN** the mock document `8721cb75…` (`third_party`, educational, no registry firm) is analyzed
- **THEN** no finding is returned and the log names the reason `no_signals`

#### Scenario: Empty text is still skipped before routing
- **WHEN** a `third_party` document has whitespace-only `text`
- **THEN** no finding is returned and the log names the reason `empty_text`

### Requirement: Advertiser on M1 and M3 findings
M1 and M3 findings SHALL carry `advertiser` in the `Finding` v1 shape (`.docs/integration-plan.md` §4). `name` SHALL be `author.name`, else `author.handle`, else the page host unless it is a social platform host, in which case `name` SHALL be null. `handle` and `profile_url` SHALL come from `author`; a `profile_url` that is not an absolute http(s) URL SHALL become null without failing the finding. `website` SHALL be the page origin when the document has no author and the page host is not a social platform host, else null. Strings SHALL be trimmed and cut to 200 characters. `in_registry` SHALL be the publisher identity of the routing requirement, so it is false on every M1 and M3 finding. `on_warning_list` SHALL be null while S3.7 is not implemented. M2 findings SHALL keep `advertiser` null.

#### Scenario: Finfluencer advertiser
- **WHEN** the mock document `3c41441c…` is analyzed
- **THEN** `advertiser` is name `Jan Inwestor`, handle `@inwestor_jan`, profile URL `https://www.instagram.com/inwestor_jan/`, `in_registry` false

#### Scenario: Web page without an author
- **WHEN** the mock document `007bbcee…` is analyzed
- **THEN** `advertiser.name` is the page host, `website` is `https://zlotykapital-fo.example.com/`, `in_registry` false and `on_warning_list` null

#### Scenario: Malformed author profile URL
- **WHEN** a `third_party` document has `author.profile_url` `javascript:alert(1)`
- **THEN** the finding is produced with `advertiser.profile_url` null

#### Scenario: Very long author name
- **WHEN** `author.name` is 5000 characters long
- **THEN** `advertiser.name` has at most 200 characters

#### Scenario: Social post without an author
- **WHEN** an Instagram post about a registered firm has no author
- **THEN** `advertiser.name` and `advertiser.website` are null
