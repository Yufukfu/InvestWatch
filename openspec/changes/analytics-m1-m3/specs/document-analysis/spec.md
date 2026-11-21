## MODIFIED Requirements

### Requirement: Routing to modules
Analytics SHALL run M2 for documents with `source_kind` `firm_own`, whether or not the registry matches a firm. It SHALL run M1 for `third_party` and `unknown` documents when the registry matches a firm (by text, page host or link host), and M3 when it does not. Each document SHALL go to exactly one module. An M3 document whose advisory signals S3.2, S3.3, S3.4 and S3.5 are all `pass` SHALL produce no finding and log the reason `no_signals` (starting product rule, design Open Question 1). The reason `module_not_implemented` SHALL no longer be logged for `third_party` or `unknown` documents.

#### Scenario: Firm's own page
- **WHEN** a `firm_own` document is analyzed
- **THEN** exactly one M2 finding is returned

#### Scenario: Firm's own page without a registry match
- **WHEN** a `firm_own` document matches no registry firm
- **THEN** exactly one M2 finding is returned and no M3 finding

#### Scenario: Third-party post about a registered firm
- **WHEN** the mock document `3c41441c…` (`third_party`, names EuroTrade) is analyzed
- **THEN** exactly one finding is returned, with `module` M1

#### Scenario: Unknown-source page of an unregistered entity
- **WHEN** the mock document `007bbcee…` (`unknown`, no registry firm) is analyzed
- **THEN** exactly one finding is returned, with `module` M3

#### Scenario: Unmatched post without advisory signals
- **WHEN** the mock document `8721cb75…` (`third_party`, educational, no registry firm) is analyzed
- **THEN** no finding is returned and the log names the reason `no_signals`

#### Scenario: Empty text is still skipped before routing
- **WHEN** a `third_party` document has whitespace-only `text`
- **THEN** no finding is returned and the log names the reason `empty_text`

## ADDED Requirements

### Requirement: Registry match on link hosts for third-party content
For `third_party` and `unknown` documents, when neither the text nor the page host matches a registry firm, analytics SHALL compare the host of each `links[].href` with the firms' `website_domains` (equal or subdomain), and a hit SHALL match that firm with confidence 0.9, quoting the href. A malformed or non-http(s) href SHALL be skipped without error. `firm_own` documents SHALL keep the text-and-page-host match only.

#### Scenario: Referral link to a firm domain
- **WHEN** a `third_party` post names no firm and links to `https://eurotrade-markets.example.com/pl/register?ref=X`
- **THEN** the EuroTrade firm is matched by link host and the document is routed to M1

#### Scenario: Malformed link
- **WHEN** a `third_party` post has a link with href `not a url`, advisory vocabulary and no other match
- **THEN** analysis succeeds, no firm is matched, and the document is routed to M3

#### Scenario: Social platform page host
- **WHEN** a post on `https://www.instagram.com/p/…` names no firm and has no links
- **THEN** no firm is matched

### Requirement: Signal catalogue
Analytics SHALL load the M1 and M3 signal catalogues from `rules/m1_signals.yaml` and `rules/m3_signals.yaml` with the shared rule-catalogue loader. Each signal catalogue SHALL have a numeric `bias`, and each entry an id (`S1.<n>` in the M1 file, `S3.<n>` in the M3 file), a Polish name, a severity, a numeric `weight`, an `implemented` flag and its parameters; S1.4, S1.5, S3.3 and S3.4 SHALL also carry an `llm:` block in the format of `analytics-llm-p0`. Loading SHALL fail with an error naming the file and the entry on a duplicate or wrongly prefixed id, an unknown severity, a missing or non-numeric weight or bias, an unknown parameter key, or a regex that does not compile. The M2 catalogue SHALL keep accepting only `R…` ids. Only implemented signals SHALL run.

#### Scenario: Catalogues load
- **WHEN** both catalogues are loaded
- **THEN** M1 holds S1.1-S1.6 all implemented, and M3 holds S3.1-S3.7 with exactly S3.7 not implemented

#### Scenario: Malformed signal catalogue
- **WHEN** an entry has id `S3.2` in the M1 file, or a weight `high`, or the root has no `bias`
- **THEN** loading fails with an error naming the file and the entry

#### Scenario: Signal id in the M2 catalogue
- **WHEN** `m2_rules.yaml` holds an entry with id `S1.1`
- **THEN** loading fails with an error naming the entry

#### Scenario: Bad signal parameter
- **WHEN** a pattern list contains an invalid regex or an unknown parameter key
- **THEN** loading fails at startup, not on the first document

### Requirement: Signal evidence sources
Every signal result with non-null `evidence` SHALL quote a verbatim substring of one of the fields its rule declares as evidence fields: `text` for every rule, and for M1/M3 signals that quote metadata also `author.name`, `author.handle`, each `links[].href` and `url`. The explanation SHALL say where the quote was found when it is not `text`. A result whose quote is in none of its declared fields SHALL become `uncertain` with null evidence. M2 rules SHALL keep `text` as their only evidence field. Every result SHALL carry the catalogue's name and severity, and `method` `rule`, `llm` or `hybrid`.

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

### Requirement: Advertiser on M1 and M3 findings
M1 and M3 findings SHALL carry `advertiser` in the `Finding` v1 shape (`.docs/integration-plan.md` §4). `name` SHALL be `author.name`, else `author.handle`, else the page host. `handle` and `profile_url` SHALL come from `author`; a `profile_url` that is not an absolute http(s) URL SHALL become null without failing the finding. `website` SHALL be the page origin when the document has no author. Strings SHALL be trimmed and cut to 200 characters. `in_registry` SHALL be true only when the author's profile host, a non-social page host or the normalized handle belongs to a registry firm. `on_warning_list` SHALL be null while S3.7 is not implemented. M2 findings SHALL keep `advertiser` null.

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

### Requirement: LLM seam and rules-only degradation for signals
M1 and M3 SHALL run their signals through the shared `run_rules` with the judge that `analyze` receives (the seam of `analytics-llm-p0`) and their module context. Only S1.4, S1.5, S3.3 and S3.4 SHALL carry an `llm:` block, so no other signal is ever sent to the LLM or changed by a verdict. S1.4 SHALL ask the LLM only when its rules result is `pass`. S1.5, S3.3 and S3.4 SHALL ask whenever they apply. Without a judge, or when the judge gives no verdict for a check, the rules-only result SHALL stand, and `model.llm` SHALL be null unless at least one verdict was merged.

#### Scenario: No judge
- **WHEN** a `third_party` document is analyzed without a judge
- **THEN** the finding has `model.llm` null and no result with `method` `llm` or `hybrid`

#### Scenario: Judge without verdicts
- **WHEN** a fake judge returns an outcome with no verdicts (endpoint down)
- **THEN** the same findings as without a judge are returned

#### Scenario: Judge confirms a required signal
- **WHEN** a fake judge returns S3.4 `fail` with the verified quote `Codziennie mówię, co kupić, a co sprzedać.` for mock `cdbf5306…`
- **THEN** S3.4 is `fail` with `method` `hybrid`, `model.llm` is the judge's model name, and the score is at least 0.7

#### Scenario: Deterministic signal is never asked
- **WHEN** the mock document `3c41441c…` is analyzed with a fake judge that records its checks
- **THEN** the checks hold S1.5 only (S1.4 is a rules `fail`), and S1.2 stays `fail` with `method` `rule`

#### Scenario: Call to action found by the LLM
- **WHEN** a post has no call-to-action phrase and a fake judge returns S1.4 `fail` with a verified quote
- **THEN** S1.4 is `fail` with `method` `llm`
