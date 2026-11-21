# Spec Delta

## Purpose
The vetted set of web sources the scraper starts with for modules M1, M2 and M3, and the idempotent, validated way they are inserted into `sources`, so every environment starts from the same reviewed list.

## ADDED Requirements

### Requirement: Seed file is validated before any write
The seed command SHALL read the entries from the tracked seed file and validate all of them before inserting any. An entry is valid only when `platform` is `web`, `source_kind` is `firm_own` or `third_party`, `target_modules` is a non-empty set drawn from `M1`, `M2`, `M3`, the URL is an `https` URL with a host, `schedule_cron` is a valid five-field cron expression or null, and no other entry has the same URL. A single invalid entry SHALL abort the run with a message naming the entry, and no row SHALL be written.

#### Scenario: Valid file
- **WHEN** every entry satisfies the rules
- **THEN** the command proceeds to insert

#### Scenario: Invalid entry aborts the whole run
- **WHEN** one entry has `target_modules = []` and the others are valid
- **THEN** the command exits with an error naming that entry and no row is inserted

#### Scenario: Duplicate URL
- **WHEN** two entries share a URL
- **THEN** the command exits with an error naming both and no row is inserted

#### Scenario: Invalid cron
- **WHEN** an entry has `schedule_cron = "every day"`
- **THEN** the command exits with an error naming that entry

### Requirement: Seeding is idempotent and never overwrites
The seed command SHALL insert an entry only when no `sources` row has the same URL, and SHALL leave an existing row unchanged, including rows the dashboard has edited or deactivated. Running it twice, or two runs at the same time, SHALL leave exactly one row per URL. It SHALL report how many entries it inserted and how many were already present.

#### Scenario: First run
- **WHEN** the command runs against an empty `sources` table
- **THEN** one row per entry exists with the entry's name, `platform = web`, URL, `source_kind`, `target_modules`, `schedule_cron` and `active = true`

#### Scenario: Second run
- **WHEN** the command runs again unchanged
- **THEN** no row is added and the report says every entry was already present

#### Scenario: Dashboard edit survives
- **WHEN** a seeded row was set to `active = false` or given another `schedule_cron` in the dashboard and the command runs again
- **THEN** that row keeps its edited values

#### Scenario: Concurrent runs
- **WHEN** two seed commands run at the same time against an empty table
- **THEN** exactly one row per URL exists afterwards

#### Scenario: Database unreachable
- **WHEN** the database cannot be reached
- **THEN** the command exits non-zero with a message that does not contain the connection string or credentials

### Requirement: Every module has a real source
The seed file SHALL contain at least one active entry for each of `M1`, `M2` and `M3`, and every entry SHALL carry the `source_kind` that matches who publishes the page: `firm_own` for a page published by a firm registered with the KNF, `third_party` for any other publisher. Entries whose only purpose is a negative control SHALL say so in their name or a comment in the seed file.

#### Scenario: Module coverage
- **WHEN** the seed file is loaded
- **THEN** each of `M1`, `M2` and `M3` appears in the `target_modules` of at least one entry

#### Scenario: Registered firm's own page
- **WHEN** an entry points at a page published by a KNF-registered firm
- **THEN** its `source_kind` is `firm_own` and its modules include `M2`

### Requirement: Seed URLs are final URLs
An entry's URL SHALL be the URL the site serves directly, not one that redirects to another URL. The opt-in live check SHALL fetch every entry's URL once through the production fetch path and fail for an entry whose final URL differs from its URL, whose status is not 200, or whose text is empty. The live check SHALL be deselected by default and outside CI, and SHALL make at most one request per entry.

#### Scenario: Stable page
- **WHEN** the live check fetches an entry that answers 200 with text and no redirect
- **THEN** that entry passes

#### Scenario: Page moved
- **WHEN** an entry's URL answers with a redirect to another path
- **THEN** the check fails for that entry and names both URLs

#### Scenario: Blocked or refused
- **WHEN** a fetch is blocked, or robots.txt refuses the URL
- **THEN** the check fails for that entry with the engine's reason and makes no further request to it

### Requirement: Seed hosts need no extra allow-list entries
Every seeded host SHALL be allowed because it is the host of a collectable source row, without an entry in `FETCH_EXTRA_HOSTS`. A redirect to another host SHALL stay refused.

#### Scenario: Seeded host is allowed
- **WHEN** the target guard is built from the seeded rows and a URL on a seeded host is checked
- **THEN** it is allowed

#### Scenario: Redirect to an unlisted host
- **WHEN** a seeded page redirects to a host that no source row names
- **THEN** the guard refuses the hop and the job records a job error instead of a document

### Requirement: Optional render marker is read, not stored
An entry MAY carry `render = true` to mark a page that needs `blocks` and screenshots. The seed loader SHALL expose the flag to other code, the seed command SHALL NOT write it to `sources`, and an entry without it SHALL behave as `render = false`.

#### Scenario: Render flag exposed
- **WHEN** the loader reads an entry with `render = true`
- **THEN** the loaded entry reports `render = true` and the inserted row has no extra column or value for it

#### Scenario: Flag absent
- **WHEN** an entry has no `render` key
- **THEN** the loaded entry reports `render = false`

### Requirement: Real positives for M3 are chosen by a human
The seed file SHALL NOT contain an M3 positive case (a page of an entity suspected of unauthorised investment advice) until a human has chosen it from the KNF public warnings list and recorded the choice in the change. Until then M3 is covered by negative controls only, and the seed command SHALL still pass validation.

#### Scenario: No positive chosen yet
- **WHEN** the seed file has M3 entries that are all marked as negative controls
- **THEN** validation passes and the run reports the M3 positives as pending
