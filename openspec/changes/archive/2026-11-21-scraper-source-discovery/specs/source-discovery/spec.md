# Spec Delta

## Purpose

Propose new places to look for third-party investment content by mining the links of documents already collected, as inactive candidate sources that a human approves, without fetching anything or widening the URL guard on its own.

## ADDED Requirements

### Requirement: Candidates come from stored links only
Discovery SHALL read the outbound links of documents fetched within the last `--since` hours (default 168) from the database and SHALL NOT make any network request. It SHALL NOT modify or delete any `documents` or existing `sources` row.

#### Scenario: Link of a recent document becomes a candidate
- **WHEN** a document fetched an hour ago links to `https://finfluencer.example/oferta` and no source uses the host `finfluencer.example`
- **THEN** one new source row exists for `https://finfluencer.example/oferta`

#### Scenario: Old document is ignored
- **WHEN** the only document linking to a host was fetched before the `--since` window
- **THEN** no candidate is created for that host

#### Scenario: No network
- **WHEN** discovery runs with every outbound socket closed
- **THEN** it completes and reports its counts

### Requirement: Candidates are inactive and manual-only
Every candidate SHALL be inserted with `platform = web`, `source_kind = unknown`, `active = false`, `schedule_cron = null` and a `name` that starts with `[candidate] `. A candidate SHALL therefore never be collected, scheduled or added to the URL guard's allow-list until a human sets `active` through the sources API.

#### Scenario: Candidate row shape
- **WHEN** a candidate is inserted
- **THEN** `active` is false, `schedule_cron` is null, `source_kind` is `unknown`, `platform` is `web` and `name` starts with `[candidate] `

#### Scenario: Candidate is not collectable
- **WHEN** the scheduler or a manual scan looks at a fresh candidate
- **THEN** it is skipped under the existing rule that only active web sources are collected

### Requirement: Modules follow the linking sources
A candidate's `target_modules` SHALL be the union of the `target_modules` of the sources whose documents link to its host, and `["M1"]` when none of those documents has a source.

#### Scenario: Union of parents
- **WHEN** a host is linked from a document of a source with `["M2"]` and from one with `["M3"]`
- **THEN** the candidate's `target_modules` are `M2` and `M3`

#### Scenario: Orphan document
- **WHEN** the only linking document has no `source_id`
- **THEN** the candidate's `target_modules` are `["M1"]`

### Requirement: One candidate per new host, never a repeat
Discovery SHALL propose at most one candidate per host, using the most-linked URL of that host (ties broken by the lexicographically smaller URL), and SHALL NOT propose a host that any `sources` row already uses, active or not. Running it twice over the same data SHALL insert nothing the second time.

#### Scenario: Host already registered
- **WHEN** a source, active or inactive, already has a URL on the host
- **THEN** no candidate is created for it, so a candidate a human left inactive is not proposed again

#### Scenario: Several links, one host
- **WHEN** documents link to three URLs of one host
- **THEN** exactly one candidate exists and its URL is the most-linked of the three

#### Scenario: Rerun is idempotent
- **WHEN** discovery runs twice with no new documents
- **THEN** the second run inserts no row

### Requirement: Unsafe and noisy links are filtered out
Discovery SHALL drop a link that is not `http` or `https`, has credentials, an IP-literal or dotless host, a port other than the scheme default, or whitespace, control characters or a backslash. It SHALL drop hosts on its denylist: social platforms, link shorteners, share endpoints, and ad, analytics and tag-manager hosts. It SHALL strip the fragment and the `utm_*`, `fbclid` and `gclid` query parameters from the URL it stores.

#### Scenario: Social and shortener links are not candidates
- **WHEN** documents link to `https://www.facebook.com/x`, `https://t.me/channel`, `https://bit.ly/abc` and `https://x.com/u/status/1`
- **THEN** none of them becomes a candidate

#### Scenario: Unsafe URL shapes
- **WHEN** a document links to `http://127.0.0.1/a`, `https://user:pw@good.example/`, `https://good.example:8443/` or `https://localhost/`
- **THEN** none of them becomes a candidate

#### Scenario: Tracking noise stripped
- **WHEN** the most-linked URL is `https://good.example/a?utm_source=x&id=7#top`
- **THEN** the candidate URL is `https://good.example/a?id=7`

#### Scenario: Malformed link in stored data
- **WHEN** a stored `links` entry is not an object with a string `href`, or `links` is missing
- **THEN** that entry is skipped, discovery does not fail, and the remaining links are processed

### Requirement: A run is capped and reported
Discovery SHALL insert at most `--limit` candidates per run (default 20), choosing the most-linked hosts first, and SHALL log through the JSON logger the number of links read, hosts considered, candidates inserted and candidates skipped by cap. With `--dry-run` it SHALL log what it would insert and write nothing. It SHALL NOT write to the console with `print`.

#### Scenario: Cap applies
- **WHEN** 30 new hosts qualify and `--limit` is 20
- **THEN** the 20 most-linked hosts are inserted and the log reports 10 skipped by cap

#### Scenario: Dry run writes nothing
- **WHEN** discovery runs with `--dry-run` over data that would produce candidates
- **THEN** no `sources` row is inserted and the log lists the candidates it would have inserted

#### Scenario: Database unreachable
- **WHEN** `DATABASE_URL` is missing or the connection fails
- **THEN** the command exits non-zero with a logged error that contains no credentials and inserts nothing
