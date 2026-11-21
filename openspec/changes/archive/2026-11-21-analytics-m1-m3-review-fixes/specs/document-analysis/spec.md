## MODIFIED Requirements

### Requirement: Routing to modules
Analytics SHALL route by publisher identity and registry result, not by `source_kind` alone (design decisions 1-2). The publisher is a registry firm when the author's `profile_url` host or a non-social page host is one of the firm's `website_domains` (equal or subdomain), or the author handle (plain ASCII, leading `@` removed, separators kept) equals a name, core name or alias of the firm with diacritics folded and whitespace removed.

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

#### Scenario: Routing to modules: which module runs
- **WHEN** a document with text is routed
- **THEN** M2 SHALL run for the publisher firm when the publisher is a registry firm, whatever the `source_kind`, and for a `firm_own` document that the registry matches by text or page host
- **AND** no module SHALL run for the own material of a foreign firm without a Polish branch (`foreign_no_branch`), which SHALL produce no finding and log the reason `out_of_scope_m2_foreign_no_branch`: M2 covers firms registered in Poland, including Polish branches of foreign firms, and such a firm is authorized, so it is not M3 either
- **AND** M1 SHALL run for a `third_party` or `unknown` document whose publisher is not a registry firm and that mentions a registry firm by text or link host
- **AND** an M1 candidate whose firm is `foreign_no_branch` and that does not target Poland (S1.7 `pass`) SHALL produce no finding and log the reason `not_targeting_poland`, while a firm registered in Poland (`brokerage_house`, `brokerage_bank`, `foreign_branch`) stays in M1 scope whatever the language
- **AND** M3 SHALL run for a document whose publisher is not a registry firm and that the registry does not match, including an unmatched `firm_own` document, which SHALL never go to M2
- **AND** M3 SHALL also run alongside M1 when the M1 document carries an S3.3 or S3.4 candidate attributed to the publisher (requirement "M3 alongside M1" in `m3-unauthorized-advice-signals`)
- **AND** an M3-only document whose advisory signals S3.2, S3.3, S3.4, S3.5 and S3.8 are all `pass` SHALL produce no finding and log the reason `no_signals`
- **AND** a document SHALL produce at most one finding per module, and the reason `module_not_implemented` SHALL no longer be logged

### Requirement: Advertiser on M1 and M3 findings
M1 and M3 findings SHALL carry `advertiser` in the `Finding` v1 shape (`.docs/integration-plan.md` §4). `name` SHALL be `author.name`, else `author.handle`, else the page host unless it is a social platform host, in which case `name` SHALL be null. `handle` and `profile_url` SHALL come from `author`; a `profile_url` that is not an absolute http(s) URL SHALL become null without failing the finding.

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

#### Scenario: Advertiser on M1 and M3 findings: further obligations
- **WHEN** this requirement is applied
- **THEN** `website` SHALL be the page origin when the document has no author and the page host is not a social platform host, else null.
- **AND** Strings SHALL be trimmed and cut to 200 characters.
- **AND** `in_registry` SHALL be the publisher identity of the routing requirement, so it is false on every M1 and M3 finding.
- **AND** `on_warning_list` SHALL be null while S3.7 is not implemented.
- **AND** M2 findings SHALL keep `advertiser` null.

### Requirement: Signal catalogue
Analytics SHALL load the M1 and M3 signal catalogues from `rules/m1_signals.yaml` and `rules/m3_signals.yaml` with the shared rule-catalogue loader. Each signal catalogue SHALL have a numeric `bias`, and each entry an id (`S1.<n>` in the M1 file, `S3.<n>` in the M3 file), a Polish name, a severity, a numeric `weight`, an `implemented` flag and its parameters; S1.4, S1.5, S3.3 and S3.4 SHALL also carry an `llm:` block in the format of `analytics-llm-p0`.

#### Scenario: Catalogues load
- **WHEN** both catalogues are loaded
- **THEN** M1 holds S1.1-S1.7 all implemented, and M3 holds S3.1-S3.8 with exactly S3.7 not implemented

#### Scenario: Malformed signal catalogue
- **WHEN** an entry has id `S3.2` in the M1 file, or a weight `high`, or the root has no `bias`
- **THEN** loading fails with an error naming the file and the entry

#### Scenario: Signal id in the M2 catalogue
- **WHEN** `m2_rules.yaml` holds an entry with id `S1.1`
- **THEN** loading fails with an error naming the entry

#### Scenario: Bad signal parameter
- **WHEN** a pattern list contains an invalid regex or an unknown parameter key
- **THEN** loading fails at startup, not on the first document

#### Scenario: Signal catalogue: further obligations
- **WHEN** this requirement is applied
- **THEN** Loading SHALL fail with an error naming the file and the entry on a duplicate or wrongly prefixed id, an unknown severity, a missing or non-numeric weight or bias, an unknown parameter key, or a regex that does not compile.
- **AND** The M2 catalogue SHALL keep accepting only `R…` ids.
- **AND** Only implemented signals SHALL run.

### Requirement: Signal evidence sources
Every signal result with non-null `evidence` SHALL quote a verbatim substring of one of the fields its rule declares as evidence fields: `text` for every rule, and for M1/M3 signals that quote metadata also `author.name`, `author.handle`, each `links[].href` and `url`. The explanation SHALL say where the quote was found when it is not `text`. A result whose quote is in none of its declared fields SHALL become `uncertain` with null evidence.

#### Scenario: Evidence check on the mocks
- **WHEN** M1/M3 run on the six M1/M3 mock documents
- **THEN** each non-null evidence is found verbatim in the field its result names

#### Scenario: Quote from a link
- **WHEN** S1.2 fires on the href `https://eurotrade-markets.example.com/pl/register?ref=JAN500`
- **THEN** its evidence is a substring of that href and the explanation says it is in a link

#### Scenario: Unverifiable quote
- **WHEN** a signal returns a quote that is in none of its declared fields
- **THEN** the result is `uncertain` and its evidence is null

#### Scenario: M2 rule quoting metadata
- **WHEN** an M2 rule returns the author handle as evidence and the handle is not in `text`
- **THEN** the result is `uncertain` and its evidence is null

#### Scenario: Signal evidence sources: further obligations
- **WHEN** this requirement is applied
- **THEN** M2 rules SHALL keep `text` as their only evidence field.
- **AND** Every result SHALL carry the catalogue's name and severity, and `method` `rule`, `llm` or `hybrid`.
