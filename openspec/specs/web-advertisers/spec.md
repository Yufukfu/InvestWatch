# web-advertisers Specification

## Purpose

The Powiązania page of the dashboard (`web/`, owners in `.github/CODEOWNERS`): who promotes which licensed firm in M1 findings, as a graph or a table with a drill-down per relation (hen68's mockups, issue #72), built in the browser from `GET /findings?module=M1` with a stated paging cap, repeat advertisers marked by text.

## Requirements

### Requirement: Powiązania page
The dashboard SHALL have a page `Powiązania` at hash `#powiazania`, linked in the header navigation between `Zgłoszenia` and `Kalibracja` and marked `aria-current` while open, loaded on first visit. It SHALL open with the eyebrow `POWIĄZANIA · M1 · FINFLUENCERZY I FIRMY Z REJESTRU` and the sentence `<N> reklamodawców promuje <M> licencjonowanych firm, w tym <R> powtarzających się` (Polish plurals) over the filtered advertisers, where `<N>` counts only advertisers with at least one matched firm.

#### Scenario: Page from its hash
- **WHEN** the dashboard opens with `#powiazania`
- **THEN** the page shows the eyebrow and the KPI sentence, and the `Powiązania` link has `aria-current`

#### Scenario: KPI counts
- **WHEN** advertiser `@a` has findings for firms X and Y, `@b` for X, and `@c` only without a firm
- **THEN** the sentence states 2 advertisers (not `@c`, which promotes no licensed firm), 2 firms and 1 repeat advertiser

### Requirement: Advertiser-to-firm table
The page SHALL offer a `Tabela` view listing the advertisers of M1 findings (`Finding.advertiser`, integration plan §4) with, per advertiser, the licensed firms (`Finding.firm`) it promotes and a finding count per firm, plus the advertiser's total, sorted by total descending. It SHALL be built from `GET /findings` with `module=M1`, without a new endpoint. Advertiser names, handles and firm names SHALL be plain text, each in a `dir="auto"` element.

#### Scenario: Table from the contract mock
- **WHEN** the backend answers `GET /findings` with `contracts/mocks/findings.json`
- **THEN** the table lists one row each for the M1 advertisers `Jan Inwestor`, `Marek Trader`, `Finanse z Kasią` and `Ekonomia na luzie` with their firms, and lists no M2 or M3 finding

#### Scenario: Grouping by advertiser and firm
- **WHEN** three M1 findings share the advertiser handle `@a`, two of them matched firm X and one firm Y
- **THEN** one row shows `@a` with total 3, firm X with count 2 and firm Y with count 1, and that row comes before an advertiser with one finding

#### Scenario: Finding without a firm or advertiser
- **WHEN** an M1 finding has an advertiser but no firm, and another has no advertiser
- **THEN** the first counts toward its advertiser under `bez dopasowanej firmy` and the second is not listed

#### Scenario: Request failed
- **WHEN** `GET /findings` fails
- **THEN** the page shows an error text and no graph or table

#### Scenario: No advertisers
- **WHEN** no M1 finding passes the filters
- **THEN** the page shows an empty-state text

### Requirement: Repeat advertisers highlighted
An advertiser that promotes two or more distinct matched firms, or has five or more M1 findings, SHALL be a repeat advertiser: marked with the text `Powtarzający się` in the table, its count and edges drawn red; in the side table, as in the mockup, by its red firm count with the legend and a visually hidden `(powtarzający się)`. Any other advertiser SHALL NOT be marked.

#### Scenario: Two firms
- **WHEN** advertiser `@a` has one finding for firm X and one for firm Y, and `@b` has two findings for firm X
- **THEN** `@a` is marked as repeat and `@b` is not

#### Scenario: Five findings
- **WHEN** advertiser `@a` has 5 findings for one firm and `@b` has 4 findings without a firm
- **THEN** `@a` is marked as repeat and `@b` is not

### Requirement: Client-side filters
The page SHALL filter the loaded findings in the browser by period (`Ostatnie 7 / 30 / 90 dni`, `Wszystko`, on `detected_at`, default `Ostatnie 30 dni`), risk level as returned by the API (`Wszystkie`, `Wysokie`, `Średnie`, `Niskie`), minimum findings per advertiser, and `Tylko powtarzający się`, and SHALL switch between `Graf` and `Tabela` with buttons that expose their pressed state. The KPI sentence, graph and tables SHALL follow the filters.

#### Scenario: Risk filter
- **WHEN** the risk filter is set to `Niskie` on the contract mock
- **THEN** the sentence states 0 advertisers and 0 firms, because the only advertiser left has no matched firm

#### Scenario: Repeat only
- **WHEN** `Tylko powtarzający się` is checked and no advertiser repeats
- **THEN** the page shows the empty-state text

### Requirement: Advertiser graph
The `Graf` view SHALL draw advertisers with a matched firm (at most 12) on the left and registry firms on the right, each with its finding count, joined by one curved edge per pair whose thickness grows with the pair's finding count, with a legend. It SHALL be inline SVG with an accessible name, labels as HTML text in `dir="auto"` elements, and a side table `Najczęstsi reklamodawcy` of the same advertisers whose rows highlight the advertiser's edges.

#### Scenario: Edge per pair
- **WHEN** `@a` has 3 findings for firm X and 1 for firm Y
- **THEN** the graph draws an edge `@a`–X with count 3 thicker than the edge `@a`–Y with count 1

#### Scenario: Highlight from the side table
- **WHEN** the analyst picks `@b` in the side table
- **THEN** the edges of `@b` are drawn on top and the other repeat edges fade, and a link opens all findings of `@b`

### Requirement: Relation page
Selecting an edge, a firm in the table, or an advertiser link SHALL open the relation page on `#powiazania` with `rel_adv` (advertiser key) and optional `rel_firm` (firm key) in the URL. It SHALL show `← Powiązania`, `WYBRANA RELACJA`, the count, the advertiser and firm, the other firms of the advertiser with counts, and its findings newest first with risk text, title, platform, score and time; a row opens the finding detail on `#zgloszenia`.

#### Scenario: Round trip
- **WHEN** the analyst clicks the edge `@marek_trader` → `Alfa Inwestycje Dom Maklerski S.A.` and then `← Powiązania`
- **THEN** the URL first carries `rel_adv` and `rel_firm` and the relation page lists that finding, then the URL drops both and the graph shows again

#### Scenario: Shared link
- **WHEN** the dashboard opens with `?rel_adv=h:@marek_trader#powiazania`
- **THEN** the relation page shows all findings of that advertiser

#### Scenario: Open a finding
- **WHEN** the analyst clicks a finding title on the relation page
- **THEN** the URL carries `finding=<id>` without `rel_adv` or `rel_firm` and the findings page opens

### Requirement: Bounded paging with a stated cap
The page SHALL request at most 3 pages of 200 findings (600), fetching page 2 or 3 only when the response `total` requires it, SHALL show nothing partial until every needed page has arrived, and SHALL state how many findings it is based on out of `total`, and that older findings are left out when `total` exceeds what was loaded.

#### Scenario: One page is enough
- **WHEN** the first response has `total` 11
- **THEN** only page 1 is requested and the page states it is based on 11 of 11 findings

#### Scenario: Cap reached
- **WHEN** the first response has `total` 1000
- **THEN** pages 1, 2 and 3 are requested, page 4 is not, and the page states the 600-finding limit and that older findings are left out
