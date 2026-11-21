## ADDED Requirements

### Requirement: Fetching the KNF lists
The loader SHALL read the four KNF list pages linked from the summary page in annexes 1 and 2 (brokerage houses, banks conducting brokerage activity, branches of foreign investment firms, foreign investment firms without a branch). It SHALL follow `?page=N` from page 1 until a page adds no new record, and SHALL fail when the page count exceeds 100. It SHALL check that the summary page still links each of the four list paths. It SHALL send at most 2 requests per second with a timeout, and SHALL retry a failed request at most 3 times with backoff. Unit tests SHALL use saved page snapshots and never the network.

#### Scenario: All lists paginated
- **WHEN** a list's last page N is answered again for page N+1, as KNF does (the no-branch list had 36 pages, 712 records, on 2026-11-21)
- **THEN** the loader reads pages 1 to N, stops after page N+1, and keeps every record of pages 1 to N once

#### Scenario: Page down
- **WHEN** a list page answers HTTP 503 or times out on all attempts
- **THEN** the run exits non-zero with `fetch_failed` naming the URL and the status or error, and the existing `knf.csv` and `knf.meta.json` are unchanged

#### Scenario: List no longer linked
- **WHEN** the summary page no longer links one of the four list paths
- **THEN** the run exits non-zero with `list_moved` naming the missing path, and writes nothing

#### Scenario: Endless pagination
- **WHEN** every page returns new records up to page 101
- **THEN** the run fails with `layout_changed` instead of fetching forever

### Requirement: Parsing firm records
The loader SHALL find records in the `#entityTable` container, one `<table>` per firm, and SHALL read fields by their `th` label text, not by CSS classes. The name SHALL be the current (not struck-through) lines of the name cell, joined with ` – ` when there are several lines. A struck-through run SHALL count as a former name only when it covers a whole line. The type SHALL follow the list. The country SHALL be `PL` for the domestic lists and the ISO 3166-1 alpha-2 code of `Państwo macierzyste` for the foreign lists, or empty when the country name is unknown.

#### Scenario: Domestic brokerage house
- **WHEN** the brokerage-house snapshot holds `CERES DOM INWESTYCYJNY S.A.` with `<strike>EFIX DOM MAKLERSKI S.A.</strike>`
- **THEN** the record has name `CERES DOM INWESTYCYJNY S.A.`, type `brokerage_house`, country `PL`, and former name `EFIX DOM MAKLERSKI S.A.`

#### Scenario: Bank with a brokerage unit and a stray strike
- **WHEN** the bank snapshot holds `BANK PEKAO S.A. (BANK POLSKA KASA OPIEKI S.A.)` and a second line whose first letter sits inside a `<strike>` that also holds the `<br>`
- **THEN** the name ends with `Biuro Maklerskie PEKAO`, never with `iuro Maklerskie PEKAO`, and no former name is recorded

#### Scenario: Foreign firm without a branch
- **WHEN** the no-branch snapshot holds `Admiral Markets AS` with `Państwo macierzyste` `Estonia`
- **THEN** the record has type `foreign_no_branch` and country `EE`

#### Scenario: Format changed
- **WHEN** a list page has no `#entityTable`, or its tables have no `Nazwa` / `Nazwa podmiotu` label
- **THEN** the run exits non-zero with `layout_changed` naming the list and page, and writes nothing

#### Scenario: Unknown country
- **WHEN** `Państwo macierzyste` is a name missing from the country map
- **THEN** the firm is kept with an empty country, and the summary counts it

#### Scenario: Malformed record
- **WHEN** one table on a page has an empty name cell
- **THEN** that record is skipped and counted, and the run fails only when more than 5% of a list is skipped

### Requirement: Stable firm ids
Each firm id SHALL be the uuid5 of its normalized current name (NFKC, casefold, collapsed whitespace) in a fixed InvestWatch namespace. The id SHALL NOT depend on the list, the page or the order. When the previous CSV holds an id for a name that KNF now shows as the firm's former name, the firm SHALL keep that id.

#### Scenario: Reload gives the same ids
- **WHEN** the loader runs twice on the same snapshots, once with the records in a different order
- **THEN** both CSVs have the same id for every firm

#### Scenario: Firm moves between lists
- **WHEN** a firm leaves the no-branch list and appears on the branch list with the same name
- **THEN** its id is unchanged and its type becomes `foreign_branch`

#### Scenario: Rename with a former name
- **WHEN** the previous CSV holds `EFIX DOM MAKLERSKI S.A.` and KNF now lists `CERES DOM INWESTYCYJNY S.A.` with that former name struck through
- **THEN** the firm keeps the previous id, and the summary reports one rename

### Requirement: One firm per name
Records with the same normalized name SHALL become one firm, whether they come from the same list or from two lists. Their aliases and domains SHALL be merged. The type SHALL follow the precedence `brokerage_house`, `brokerage_bank`, `foreign_branch`, `foreign_no_branch`. The summary SHALL count every merge.

#### Scenario: Duplicate name in one list
- **WHEN** the no-branch list holds `GBR Capital GmbH` twice
- **THEN** the CSV has one `GBR Capital GmbH` row with the union of both records' aliases and domains

#### Scenario: Same firm on two lists
- **WHEN** `IG Europe GmbH` is on both the branch list and the no-branch list
- **THEN** the CSV has one row with type `foreign_branch` and the branch list's `source_url`

#### Scenario: Same core, different legal names
- **WHEN** the register holds `Alpha Capital Ltd` and `Alpha Capital GmbH`
- **THEN** they are two firms with different ids, and neither keeps the shared alias `Alpha Capital`

### Requirement: Generated aliases
The loader SHALL generate aliases from each name line: the line itself, its core name without legal forms, a bracketed abbreviation, the `DM` forms and the Polish case forms of the legal-form words (`Domu Maklerskiego …`), the former names, and the trade names listed in `Dodatkowe informacje`. It SHALL drop an alias with fewer than 4 letters, a single-word alias on the generic stop-list, and an alias that two firms share. It SHALL never drop the firm's full name.

#### Scenario: Bank brokerage unit and abbreviation
- **WHEN** the bank record is `POWSZECHNA KASA OSZCZĘDNOŚCI BANK POLSKI S.A. (PKO BP S.A.)` / `Biuro Maklerskie PKO Banku Polskiego`
- **THEN** the aliases include `PKO BP` and `Biuro Maklerskie PKO Banku Polskiego`

#### Scenario: Trade names
- **WHEN** `Dodatkowe informacje` reads `Nazwy handlowe: AccurateFX XGLOBAL … www.xglobalmarkets.com`
- **THEN** the aliases include the listed trade names, and no alias contains a domain

#### Scenario: Generic or short alias dropped
- **WHEN** a firm's core name is `EXT` or the single stop-list word `Capital`
- **THEN** that alias is dropped and counted, and the firm keeps its full name

### Requirement: Firm domains
The loader SHALL take a firm's `website_domains` from host-like tokens in its `Dodatkowe informacje`, normalized like `Registry` does. It SHALL exclude hosts that appear in any record's `Organ nadzoru` cell, social-platform hosts, and hosts that two firms share. A firm without domains SHALL have an empty `website_domains`. Domains from `registry/knf_domains_manual.csv` (columns `name, website_domains, source_url, verified_by_human`) SHALL be merged by normalized name. They are curated by the team, not published by KNF, so each row SHALL name the firm's official page it was checked on and SHALL carry `verified_by_human` `true` or `false`, and the meta file SHALL count curated domains apart from KNF ones. A manual row whose name is not in the register SHALL fail the run.

#### Scenario: Domains from trade-name notes
- **WHEN** `Dodatkowe informacje` lists `www.50k.trade [od 10.05.2024] www.50coins.com`
- **THEN** `website_domains` is `50k.trade|50coins.com`

#### Scenario: Supervisor site is not a firm domain
- **WHEN** `Organ nadzoru` holds `www.cysec.gov.cy`
- **THEN** `cysec.gov.cy` is in no firm's `website_domains`

#### Scenario: Empty domains
- **WHEN** a brokerage house has no notes and no manual row
- **THEN** its `website_domains` cell is empty, and `Registry.from_csv` loads it with no domains

#### Scenario: Curated domain marked unverified
- **WHEN** a manual row for `mBANK S.A. – Biuro Maklerskie mBank` lists `mbank.pl` with `verified_by_human` `false`
- **THEN** the firm's `website_domains` holds `mbank.pl`, and `knf.meta.json` counts it as a curated, unverified domain

#### Scenario: Stale manual row
- **WHEN** `knf_domains_manual.csv` names a firm that is not in the fetched register
- **THEN** the run exits non-zero naming the row

### Requirement: Writing the registry
The loader SHALL write `knf.csv` with exactly the columns `id, name, aliases, type, country, website_domains, source_url`, sorted by type and then name, with list fields separated by `|`. It SHALL write `knf.meta.json` with `fetched_at` (UTC ISO-8601), the record and firm count per list, the source URLs and the loader version. It SHALL load its own output with `Registry.from_csv` before replacing the old files, and replace them with an atomic rename. It SHALL refuse to write when a list's record count is 0 or less than half of the count in the previous meta file, unless `--accept-drop` is given.

#### Scenario: Output loads as a registry
- **WHEN** the loader runs on the saved snapshots
- **THEN** `Registry.from_csv` loads the CSV without error, and every row's `source_url` is a KNF list URL

#### Scenario: Count dropped
- **WHEN** the previous meta file says 712 no-branch records and the new run finds 300
- **THEN** the run exits non-zero with `count_dropped` naming the list and both counts, and the old files are unchanged

#### Scenario: Write interrupted
- **WHEN** writing the new CSV fails partway
- **THEN** the old `knf.csv` is still complete and loadable

### Requirement: Default registry and provenance at start-up
The default `REGISTRY_CSV`, in code and in the container, SHALL be `registry/knf.csv`, a snapshot frozen at implementation time and refreshed only by running the loader by hand. `registry/seed.csv` SHALL stay the fictional fixture whose ids match `contracts/mocks`, and the loader SHALL never write it. At start-up the worker SHALL log `registry_loaded` with the registry path, the firm count and, when `knf.meta.json` sits next to the CSV, its `fetched_at` as the snapshot date, so that it can be shown to users later. It SHALL warn `registry_seed` when the seed is in use, and `registry_unverified` when a non-seed CSV has no meta file. It SHALL NOT warn about the snapshot's age. None of these warnings SHALL stop the worker.

#### Scenario: Default is the real registry
- **WHEN** the worker starts without `REGISTRY_CSV`
- **THEN** it loads `registry/knf.csv` and logs `registry_loaded` with its firm count and snapshot date, and does not log `registry_seed`

#### Scenario: Seed chosen explicitly
- **WHEN** `REGISTRY_CSV` points to `registry/seed.csv`
- **THEN** the worker starts and logs the `registry_seed` warning

#### Scenario: Old snapshot
- **WHEN** `knf.meta.json` says `fetched_at` is 45 days before now
- **THEN** the worker starts, logs `registry_loaded` with that date, and logs no warning about its age

#### Scenario: Hand-made registry without provenance
- **WHEN** `REGISTRY_CSV` points to a CSV that is not the seed and has no `knf.meta.json` next to it
- **THEN** the worker starts and logs `registry_unverified`
