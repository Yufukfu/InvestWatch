# knf-registry-loader Specification

## Purpose

Load the real KNF register of investment firms (the four lists linked in annexes 1 and 2 of the challenge) into `analytics/registry/knf.csv`, the default registry analytics matches documents against. The loader runs by hand, fails closed on any fetch, layout or count problem, keeps firm ids stable across reloads, and writes provenance the worker logs at start-up.

## Requirements

### Requirement: Fetching the KNF lists
The loader SHALL read the four KNF list pages linked from the summary page in annexes 1 and 2: brokerage houses, banks conducting brokerage activity, branches of foreign investment firms, and foreign investment firms without a branch. It SHALL follow `?page=N` until a page repeats the previous one, send at most 2 requests per second, and retry at most 3 times. Unit tests SHALL use saved snapshots, never the network.

#### Scenario: All lists paginated
- **WHEN** a list's last page N is answered again for page N+1, as KNF does (the no-branch list had 36 pages, 712 records, on 2026-11-21)
- **THEN** the loader reads pages 1 to N, stops after page N+1, and keeps every record of pages 1 to N
- **AND** identical records on two different pages are both kept, for the merge step

#### Scenario: Page down
- **WHEN** a list page answers HTTP 503 or times out on all 3 attempts
- **THEN** the run exits non-zero with `fetch_failed` naming the URL and the status or error, and the existing `knf.csv` and `knf.meta.json` are unchanged
- **AND** a redirect off `https://www.knf.gov.pl/` and a response over 5 MB fail the same way

#### Scenario: List no longer linked
- **WHEN** the summary page no longer links one of the four list paths
- **THEN** the run exits non-zero with `list_moved` naming the missing path, and writes nothing

#### Scenario: Endless pagination
- **WHEN** every page returns new records beyond page 100
- **THEN** the run fails with `layout_changed` instead of fetching forever, while a list of exactly 100 pages is read

### Requirement: Parsing firm records
The loader SHALL read records from the `#entityTable` container, one `<table>` per firm, by their `th` label text and never by CSS class. The name SHALL be the name cell's lines that are not struck through, joined with ` – `. The type SHALL follow the list. The country SHALL be `PL` on the domestic lists and the ISO code of `Państwo macierzyste` on the foreign lists.

#### Scenario: Domestic brokerage house
- **WHEN** the brokerage-house snapshot holds `CERES DOM INWESTYCYJNY S.A.` with `<strike>EFIX DOM MAKLERSKI S.A.</strike>`
- **THEN** the record has name `CERES DOM INWESTYCYJNY S.A.`, type `brokerage_house`, country `PL`, and former name `EFIX DOM MAKLERSKI S.A.`

#### Scenario: Bank with a brokerage unit and a stray strike
- **WHEN** the bank snapshot holds `BANK PEKAO S.A. (BANK POLSKA KASA OPIEKI S.A.)` and a second line whose first letter sits inside a `<strike>` that also holds the `<br>`
- **THEN** the name ends with `Biuro Maklerskie PEKAO`, never with `iuro Maklerskie PEKAO`, and no former name is recorded
- **AND** a struck-through run counts as a former name only when it covers a whole line

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
Each firm id SHALL be the uuid5 of its normalized current name (NFKC, casefold, collapsed whitespace) in a fixed InvestWatch namespace, independent of the list, page and order. An id held by the previous CSV for the same name, or for a name KNF now shows as the firm's former name, SHALL be kept, unless another current firm holds it.

#### Scenario: Reload gives the same ids
- **WHEN** the loader runs twice on the same snapshots, once with the records in a different order
- **THEN** both CSVs have the same id for every firm

#### Scenario: Firm moves between lists
- **WHEN** a firm leaves the no-branch list and appears on the branch list with the same name
- **THEN** its id is unchanged and its type becomes `foreign_branch`

#### Scenario: Rename with a former name
- **WHEN** the previous CSV holds `EFIX DOM MAKLERSKI S.A.` and KNF now lists `CERES DOM INWESTYCYJNY S.A.` with that former name struck through
- **THEN** the firm keeps the previous id, and the summary reports one rename
- **AND** the next reload, whose previous CSV holds the new name with the carried id, keeps that id

### Requirement: One firm per name
Records with the same normalized name SHALL become one firm, whether from one list or two, with their aliases and domains merged. The type SHALL follow the precedence `brokerage_house`, `brokerage_bank`, `foreign_branch`, `foreign_no_branch`. The summary SHALL count every merge.

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
The loader SHALL generate aliases from each name line (the line, its core without legal forms, bracketed abbreviations, `DM` and Polish case forms of the legal-form words), from bracketed translation lines, former names, and trade names in `Dodatkowe informacje`. It SHALL drop aliases under 3 letters, aliases of only generic words, and shared aliases except for the single firm of the highest type. It SHALL never drop the full name.

#### Scenario: Bank brokerage unit and abbreviation
- **WHEN** the bank record is `POWSZECHNA KASA OSZCZĘDNOŚCI BANK POLSKI S.A. (PKO BP S.A.)` / `Biuro Maklerskie PKO Banku Polskiego`
- **THEN** the aliases include `PKO BP` and `Biuro Maklerskie PKO Banku Polskiego`

#### Scenario: Trade names
- **WHEN** `Dodatkowe informacje` reads `Nazwy handlowe: AccurateFX XGLOBAL AHMZTradeFX abftrade.com/eu`
- **THEN** the aliases include `AccurateFX`, `XGLOBAL` and `AHMZTradeFX`, and no alias contains a domain
- **AND** a trade name written in capitals only (`LONDON AND CAPITAL WEALTH MANAGEMENT EUROPE`) stays one alias and is never split into words

#### Scenario: Generic or short alias dropped
- **WHEN** a firm's alias is `EU`, a seat in brackets (`Cyprus`, `Niemcy`), a city, a function word, or consists only of stop-list words (`Europe`, `Capital Markets`)
- **THEN** that alias is dropped and counted, and the firm keeps its full name

#### Scenario: Short brand kept
- **WHEN** the register holds `XTB S.A.`, `mBANK S.A.` / `Biuro Maklerskie mBank` and `EXT Ltd`
- **THEN** the aliases include `XTB`, `mBANK` and `EXT` (the registry guards short aliases when matching)

#### Scenario: Shared alias stays with the Polish firm
- **WHEN** the brokerage house `XTB S.A.` and the foreign firm without a branch `XTB Ltd` both yield the alias `XTB`
- **THEN** `XTB S.A.` keeps `XTB`, `XTB Ltd` does not, and the summary counts one dropped shared alias
- **AND** an alias shared by firms of the same highest type is dropped from all of them

#### Scenario: Translation line
- **WHEN** a no-branch record's name cell reads `Bitstamp finančne storitve d.o.o.` / `(ang. Bitstamp Financial Services Ltd.)`
- **THEN** the name is `Bitstamp finančne storitve d.o.o.` and `Bitstamp Financial Services Ltd.` is an alias

### Requirement: Firm domains
The loader SHALL take `website_domains` from host-like tokens in the not-struck-through `Dodatkowe informacje`, excluding supervisor sites from `Organ nadzoru`, social hosts, and hosts shared by firms except the single highest-type one. It SHALL merge curated domains from `registry/knf_domains_manual.csv` by firm name. A firm without domains SHALL have an empty `website_domains`.

#### Scenario: Domains from trade-name notes
- **WHEN** `Dodatkowe informacje` of `50KCY LTD` lists `www.50k.trade [od 10.05.2024]` and, struck through, `www.50coins.com`
- **THEN** `website_domains` is `50k.trade`: struck-through (former) domains are never firm domains

#### Scenario: Supervisor site is not a firm domain
- **WHEN** `Organ nadzoru` holds `www.cysec.gov.cy`
- **THEN** neither `cysec.gov.cy` nor a subdomain of it is in any firm's `website_domains`

#### Scenario: Empty domains
- **WHEN** a brokerage house has no notes and no manual row
- **THEN** its `website_domains` cell is empty, and `Registry.from_csv` loads it with no domains

#### Scenario: Curated domain marked unverified
- **WHEN** a manual row for `mBANK S.A. – Biuro Maklerskie mBank` lists `mbank.pl` with `verified_by_human` `false`
- **THEN** the firm's `website_domains` holds `mbank.pl`, and `knf.meta.json` counts it as a curated, unverified domain
- **AND** each manual row has the columns `name, website_domains, source_url, verified_by_human`, a `source_url` on one of its domains, and `true` or `false`; curated domains are InvestWatch's, not KNF's

#### Scenario: Stale manual row
- **WHEN** `knf_domains_manual.csv` names a firm that is not in the fetched register
- **THEN** the run exits non-zero naming the row

#### Scenario: Conflicting manual rows
- **WHEN** two manual rows name the same firm, or give two firms the same domain or nested domains (`pekao.com.pl`, `ib.pekao.com.pl`), or a public suffix like `com.pl`
- **THEN** the run exits non-zero with `manual_row` naming the rows

### Requirement: Writing the registry
The loader SHALL write `knf.csv` with exactly the columns `id, name, aliases, type, country, website_domains, source_url`, sorted by type then name, and `knf.meta.json` with `fetched_at`, counts per list and the loader version. It SHALL load its output with `Registry.from_csv` before an atomic replace. It SHALL refuse a list with 0 records or under half of its previous count, unless `--accept-drop`.

#### Scenario: Output loads as a registry
- **WHEN** the loader runs on the saved snapshots
- **THEN** `Registry.from_csv` loads the CSV without error, and every row's `source_url` is a KNF list URL

#### Scenario: Count dropped
- **WHEN** the previous meta file says 712 no-branch records and the new run finds 300
- **THEN** the run exits non-zero with `count_dropped` naming the list and both counts, and the old files are unchanged

#### Scenario: Write interrupted
- **WHEN** writing or renaming the new files fails partway
- **THEN** the old `knf.csv` and `knf.meta.json` are still the matching pair, no temporary file is left, and the run exits non-zero with `write_failed`

#### Scenario: Seed never written
- **WHEN** `--out` names `registry/seed.csv`
- **THEN** the run exits non-zero and the seed is unchanged

### Requirement: Default registry and provenance at start-up
The default `REGISTRY_CSV`, in code and in the container, SHALL be `registry/knf.csv`, a snapshot frozen at implementation time. `registry/seed.csv` SHALL stay the fictional fixture whose ids match `contracts/mocks`. At start-up the worker SHALL log `registry_loaded` with the path, the firm count and the snapshot date from `knf.meta.json`. No provenance warning SHALL stop the worker.

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
