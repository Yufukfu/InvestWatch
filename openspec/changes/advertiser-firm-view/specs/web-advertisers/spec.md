## ADDED Requirements

### Requirement: Advertiser-to-firm table
The dashboard SHALL show a section listing the advertisers of M1 findings (`Finding.advertiser`, integration plan §4) with, per advertiser, the licensed firms (`Finding.firm`) it promotes and a finding count per firm, plus the advertiser's total finding count, sorted by total count descending. It SHALL be built from `GET /findings` with `module=M1`, without a new endpoint. Advertiser names and handles SHALL be rendered as plain text, each in a `dir="auto"` element.

#### Scenario: Table from the contract mock
- **WHEN** the backend answers `GET /findings` with `contracts/mocks/findings.json`
- **THEN** the section lists one row each for the M1 advertisers `Jan Inwestor`, `Marek Trader`, `Finanse z Kasią` and `Ekonomia na luzie` with their firms, and lists no M2 or M3 finding

#### Scenario: Grouping by advertiser and firm
- **WHEN** three M1 findings share the advertiser handle `@a`, two of them matched firm X and one firm Y
- **THEN** one row shows `@a` with total 3, firm X with count 2 and firm Y with count 1, and that row comes before an advertiser with one finding

#### Scenario: Finding without a firm or advertiser
- **WHEN** an M1 finding has an advertiser but no firm, and another has no advertiser
- **THEN** the first counts toward its advertiser under `bez dopasowanej firmy` and the second is not listed

#### Scenario: Request failed
- **WHEN** `GET /findings` fails
- **THEN** the section shows an error text and no table

#### Scenario: No advertisers
- **WHEN** no M1 finding has an advertiser
- **THEN** the section shows an empty-state text

### Requirement: Repeat advertisers highlighted
An advertiser with two or more M1 findings SHALL be marked with the text `Powtarzający się` in its row, not by colour alone; an advertiser with one finding SHALL NOT be marked.

#### Scenario: Repeat and single advertisers
- **WHEN** advertiser `@a` has 2 findings and `@b` has 1
- **THEN** the `@a` row shows `Powtarzający się` and the `@b` row does not

### Requirement: Bounded paging with a stated cap
The section SHALL request at most 3 pages of 200 findings (600), fetching page 2 or 3 only when the response `total` requires it, and SHALL state how many findings the table is based on out of `total`, and that older findings are left out when `total` exceeds what was loaded.

#### Scenario: One page is enough
- **WHEN** the first response has `total` 11
- **THEN** only page 1 is requested and the section states it is based on 11 of 11 findings

#### Scenario: Cap reached
- **WHEN** the first response has `total` 1000
- **THEN** pages 1, 2 and 3 are requested, page 4 is not, and the section states the 600-finding limit and that older findings are left out
