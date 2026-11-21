# Design

## Context

`Registry.from_csv` (`analytics/src/investwatch_analytics/registry.py`) reads `id, name, aliases, type, country, website_domains, source_url`. It requires `id` (a lowercase UUID), `name` and `type`, one of `brokerage_house`, `brokerage_bank`, `foreign_branch` or `foreign_no_branch`. List fields are separated by `|`. Matching tries, per firm, name or alias (0.95), page host on a firm domain (0.9) and fuzzy core-name match (ratio × 0.85 at ratio ≥ 88). It loops over every firm and compiles one regex per alias. The only registry today is `registry/seed.csv`: three fictional firms whose ids are the `registry_id`s in `contracts/mocks`. PR #26 (`analytics-worker`, with its review fixes) defaults `REGISTRY_CSV` to that seed in code (`config._DEFAULT_REGISTRY`) and in the image, and logs a `registry_seed` warning when it is in use.

What KNF actually publishes is recorded in `evidence.md`. In short, four list pages hold 760 records as server-rendered HTML cards, one `<table>` per firm with `th` labels, `?page=N` pagination, and no download, API, identifier or website field. Former names are in `<strike>`, and the no-branch list has free-text `Dodatkowe informacje` with trade names and domains. Reuse is allowed with the source and a link.

## Goals / Non-Goals

**Goals:**
- Use the real KNF register as the default registry, with ids that survive reloads.
- A loader whose failures never replace a good CSV with a bad one.
- Matching that stays correct (few false positives) and fast with about 750 firms.
- `seed.csv` and `contracts/mocks` untouched; tests keep using the seed.

**Non-Goals:**
- KNF public warnings (`registry_warnings`, S3.7). Domains are a regex away, but entity names in the free-text cells (numbered sub-entities, seats, platforms in one cell) need their own parser and their own false-positive review. Not trivial, so it gets its own change.
- Revoked licences (the KNF page "Firmy inwestycyjne, którym cofnięto zezwolenie…") and `FirmRef.authorized`: every firm loaded from the current lists is authorized, so `True` is now correct rather than a placeholder (skeleton follow-up #18 answered for this source).
- A `registry_firms` database table (plan §3). No consumer reads it: the API and web take the firm from the finding. The CSV is the source of truth.
- Investment firm agents (two more KNF lists): they are not "firma inwestycyjna" in the annex definition.
- Inflection of core names (`Banku Millennium`), apart from the legal-form words. The rest of skeleton follow-up #12 stays open.
- Scheduled refresh (Integration #3 schedules scans, not registry loads).

## Decisions

### 1. Parse the HTML pages with the standard library

The pages are the only format KNF offers (`evidence.md`, Format). The loader uses `urllib.request` with a timeout, a descriptive user agent and at most 2 requests per second, and parses with `html.parser`. It keys on the `#entityTable` container and the `th` label text, because the table classes are Tailwind utilities that a restyle changes. Labels map to fields per list (`Nazwa` or `Nazwa podmiotu` to the name, `Państwo macierzyste` to the country, `Dodatkowe informacje` to the notes). An unknown label is ignored. A missing name label fails the page.

Alternatives: `selectolax` or BeautifulSoup would mean a new dependency for a one-off tool that reads four layouts. A headless browser is not needed, because the records are in the initial HTML.

Pagination: follow `?page=N` from 1 and stop at the first page that adds no new record. KNF returns the last page for any larger `N`. The loader also stops at a cap of 100 pages, which fails the run because KNF never had that many. The summary page is fetched only to check that it still links the four list paths. If a link is missing, the run fails with `list_moved`.

### 2. Commit the generated CSV; never fetch at build or start-up

The options were (a) commit `knf.csv`, (b) generate it in the Docker build, or (c) generate it at worker start-up. Option (a) was chosen:

- The legal note allows reuse with attribution (`evidence.md`, Licence). Each row carries `source_url`, and `analytics/registry/README.md` names KNF with a link.
- Options (b) and (c) make `docker compose up` depend on knf.gov.pl being reachable and unchanged. That breaks the on-premise and offline demo, and makes builds non-reproducible. It also puts the worker on the network for a fetch it does not otherwise need. A layout change on KNF's side would then stop the build or the worker instead of failing one manual refresh.
- A committed file gives deterministic evaluation (plan §8) and reviewable diffs on refresh.

Refresh: `python -m investwatch_analytics.knf --out registry/knf.csv` by hand, then review and commit. The command prints a summary (counts per list, added, removed, renamed, dropped aliases). The snapshot is frozen at implementation time. `knf.meta.json` holds `fetched_at`, which the worker logs at start-up and `analytics/registry/README.md` states, so the UI can show it later. No age warning: the challenge requires periodic refresh of M1 output, not of the registry.

### 3. Firm id = uuid5(namespace, normalized current name), carried over on rename

KNF shows no identifier, so the name is the only key. Normalization is NFKC, casefold, whitespace collapsed, and quotes and trailing punctuation stripped. The namespace is `uuid5(NAMESPACE_URL, "https://www.knf.gov.pl/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych")`, a constant in code. The type is not part of the key, so a firm that moves from the no-branch list to the branch list keeps its id.

When KNF renames a firm, the new name gives a new id, unless KNF lists the old name in `<strike>`. If the loader is given the previous CSV (the default output path when it exists), it reuses the old id for a former name that had one. A rename without a struck name gets a new id, and the refresh summary lists it as one removed and one added firm.

uuid5 instead of the repository's v4 convention: a random id would change on every reload and orphan `findings.firm.registry_id`. The contract only requires the UUID pattern, so this is ADR 0311.

### 4. One firm per normalized name; type by precedence

Duplicates seen on KNF (`evidence.md`, Duplicates):
- The same name twice in one list (3 cases) becomes one firm. Aliases and domains are merged, and the summary counts the merge.
- The same name on two lists (7 cases, branch and no-branch) becomes one firm whose type follows the precedence `brokerage_house` > `brokerage_bank` > `foreign_branch` > `foreign_no_branch`, the strongest presence in Poland. `source_url` is that list's URL.
- Two different names with the same core (`X Ltd`, `X GmbH`) stay two firms. A core or alias shared by more than one firm is dropped from all of them (decision 5), so the matcher never picks one at random.

### 5. Aliases and their filters

Generated per firm, in this order:
1. The current name lines. A bank record has the bank and its brokerage unit on separate `<br>` lines: the name is the lines joined with ` – ` (as in the seed's `Bank Przykładowy S.A. – Biuro Maklerskie`), and each line is also an alias.
2. The core name (`core_name`) of each line. `_LEGAL_FORMS` grows to cover the forms seen on KNF: `GmbH`, `AG`, `SE`, `B.V.`, `N.V.`, `a.s.`, `s.r.o.`, `Ltd`, `Limited`, `LLC`, `plc`, `SAS`, `S.A.S.`, `AS`, `A/S`, `AB`, `Oy`, `S.p.A.`, `S.L.`, `S.à r.l.`, `Spółka Akcyjna`, `Oddział w Polsce`, `sp. k.`. The list is pinned by a parametrized test.
3. A bracketed abbreviation (`(PKO BP S.A.)` gives `PKO BP`).
4. `DM` forms for names with `Dom Maklerski` (`DM X`, `X DM`) and Polish case forms of the legal-form words only (`Domu Maklerskiego X`, `Biura Maklerskiego X`, `Domem Maklerskim X`).
5. Former names from `<strike>`. A struck run counts only when it covers a whole `<br>` line, because of the PEKAO artifact in `evidence.md`.
6. Trade names from `Dodatkowe informacje`: the comma-separated words after `nazwa handlowa` or `nazwy handlowe` (any case), up to the first domain or bracket.

Bracketed translation lines on the no-branch list (`(ang. Bitstamp Financial Services Ltd.)`) are aliases, not name lines.

Filters, applied after all firms are built: an alias needs at least 3 letters, and an alias made only of generic finance words (`knf/stoplist.txt`: `Capital`, `Markets`, `Europe`, `Financial`, `Securities`, …) is dropped. Short brands stay (`XTB`, `mBANK`, `PEKAO`, `Trigon`), because they are what ads use; the registry guards them when matching (decision 9). An alias claimed by several firms stays with the single firm of the highest type precedence (`XTB` stays with the Polish brokerage house `XTB S.A.`, not the Cypriot `XTB Ltd`), and it is dropped from all of them on a tie (`Admiral Markets`: two foreign firms without a branch). This was first planned as "drop every short single word and every shared alias". The snapshots showed that rule drops XTB, mBank, Pekao and Trigon, the most advertised Polish names. Dropped aliases are counted in the summary and listed with `--verbose`. The firm's full name is never dropped.

### 6. Domains

- No-branch list: host-like tokens in `Dodatkowe informacje` (`www.x.tld`, `x.tld/path`, `https://…`), normalized with the registry's `_normalize_domain`. Excluded are hosts that appear in any record's `Organ nadzoru` cell (the supervisors' sites), the m1-m3 social hosts, and hosts shared by two firms (dropped from both, reported).
- Other lists: no domains on KNF, so empty.
- Curated supplement `registry/knf_domains_manual.csv` (`name,website_domains,source_url,verified_by_human`) for the 38 domestic firms, keyed by normalized name and merged by the loader. These domains are an InvestWatch attribution aid, not KNF data. The agent drafts them only from official sites it can verify (the site names the firm's legal name and its brokerage activity, checked once by hand and never in tests). `source_url` is the page where that was seen, and every drafted row has `verified_by_human` `false` until Damian checks it. The meta file counts curated domains apart from KNF ones. A row whose name is not in the fetched register fails the run, so a renamed firm is noticed.

### 7. Failure handling: fail closed, never overwrite

The loader builds the whole registry in memory, validates it, and writes it through a temporary file and a rename. It exits non-zero and leaves the old files untouched when:
- a page cannot be fetched after 3 attempts with backoff (`fetch_failed`, naming the URL and status or error);
- the summary no longer links a list (`list_moved`);
- a list page has no `#entityTable` or no name label (`layout_changed`, naming the list and page);
- a list yields 0 records, or fewer than half of its count in the previous `knf.meta.json` (`count_dropped`, with both numbers; `--accept-drop` overrides after a human looks);
- the result fails `Registry.from_csv` (the loader round-trips its own output before the rename).

A country name missing from the Polish-to-ISO map leaves `country` empty and is counted, so it does not fail the run. One unparseable record is skipped and counted, and the run fails if more than 5% of a list is skipped.

### 8. Default registry and start-up

- `config._DEFAULT_REGISTRY` becomes `registry/knf.csv`. The image already copies `registry/` next to `src/` (PR #26), and the compose default for `REGISTRY_CSV` becomes that path.
- `uses_seed_registry` and its `registry_seed` warning stay. Tests that need the fictional firms pass `SEED` explicitly, as `test_registry.py`, `test_pipeline.py` and `test_rules.py` already do. `test_default_registry_path_is_seed` becomes `…_is_knf`.
- At start-up the worker logs `registry_loaded` with the path, firm count and, when `knf.meta.json` sits next to the CSV, `fetched_at`. It warns `registry_unverified` when the CSV is not the seed and has no meta file (a hand-made registry). There is no age warning. None of these stop the worker. A missing or malformed CSV still exits 2, as today.

### 9. Matching at real scale

With about 750 firms and 2-6 aliases each, `Registry.match` compiles about 3,000 patterns and runs fuzzy n-grams per firm for every document. Changes:
- **Name pass:** one compiled alternation per registry (aliases longest first, with the same word boundaries as `_alias_pattern`) and a map from alias to firm. A single `finditer` gives every name hit with its position, so the existing ranking (own domain, confidence, earliest, longest) is unchanged.
- **Short-word guard:** a core or alias of one word token and fewer than 8 letters (`EXT`, `XTB`, `Nova`) matches only as a capitalized word: its first letter in the text is upper case, or lower case only where the registry writes it so (`mBank`). It is never a fuzzy target. `bossa nova` and `next step` match nothing, while `Konto w XTB` matches `XTB S.A.`. A core shared by several firms is used bare only by the single firm of the highest type precedence, the same rule as the loader's (decision 5). Fuzzy runs only for the other cores, and only when no exact name hit exists for that firm. This closes skeleton follow-up #11 for the real registry. The seed's cores (`Alfa Inwestycje`, `Bank Przykładowy`, `EuroTrade Markets`) all have two words, so the existing scenarios hold. `analytics-m1-m3` compares a normalized author handle with name, core and aliases. Whichever change lands second applies the same guard there, so that `@ext` is not `EXT Ltd`.
- **Budget:** a test builds a registry from the saved fixtures (about 70 firms) replicated to 1,000 synthetic firms and matches a 20,000-character text. It must finish in under 1 s on CI, a loose bound that catches a quadratic regression without being flaky.
- Domain matching is unchanged: firms without domains never match by domain.

### 10. R1 checks the official name

ZASÓB R1 asks for "oficjalną nazwę firmy inwestycyjnej". Since the registry now holds former and trade names as aliases, a name match is no longer proof of the official name. `Registry.find_official_name(firm, text)` searches only the official forms: `name`, each ` – `-separated line of it, and their cores without legal forms. R1 passes on that. It is `uncertain` when only `find_name` (any alias) hits, explaining `W materiale użyto nazwy nieoficjalnej/dawnej: „<quote>”; oficjalna nazwa: <name>.` The CSV gains no column: every entry of `aliases` is unofficial by definition, and the official forms are derived from `name`. `find_name` and `match` keep their signatures for `analytics-m1-m3`.

### 11. Tests never touch the network

`fetch.py` exposes `fetch(url) -> str`, and the CLI takes a `fetcher` parameter. Unit tests pass a fake that serves saved snapshots from `tests/fixtures/knf/`. These are trimmed copies of real pages: page 1 of each list, the last no-branch page, the no-branch `?page=99` clamp case, and the summary page. The trimmed copies keep `#entityTable` and the pagination links verbatim and drop the navigation chrome. A failing-path fixture set is derived from them: a renamed label, a missing `entityTable`, an empty list, and a summary without one link. One optional live check (`pytest -m live`, skipped by default and on CI) fetches page 1 of each list and only asserts that the labels are still there.

## Risks / Trade-offs

- [KNF changes the markup] → decision 7 fails closed and keeps the committed CSV, and the optional live check shows it before a refresh.
- [Firms with no domain are matched by name only] → name matching covers firm pages and ads that name the firm. Link-host M1 detection (`analytics-m1-m3`) needs domains, which the curated supplement gives the domestic firms.
- [A drafted curated domain is wrong] → `verified_by_human` `false` and `source_url` on every row, so Damian checks them before relying on them. A wrong domain only routes a page to the wrong firm, and the finding shows the match method and confidence.
- [Generic aliases cause false M1/M2 routing] → the alias filters (decision 5) and the fuzzy guard (decision 9). The match confidence stays on the finding, so a reviewer sees weak matches. The gold set (plan §8) measures the rest.
- [A rename without a struck name changes the id] → the refresh summary lists it. Old findings keep their old `registry_id` and the firm name, and no foreign key exists to break.
- [The committed data goes stale] → the snapshot date in the meta file, the start-up log and `analytics/registry/README.md`, and the refresh command there.
- [~750 firms slow every document] → decision 9 and its budget test.
- [Conflicts with `analytics-m1-m3` in `registry.py`] → its edits are additive (new methods), while this change edits `_LEGAL_FORMS`, `__init__` and `match`. The second to land rebases, and both test suites run on the result.

## Migration Plan

1. Land after PR #26 and its review fixes, rebased on `main`.
2. The worker picks up `registry/knf.csv` by default, and no env change is needed. Rollback: set `REGISTRY_CSV=registry/seed.csv`, or revert the commit.
3. Existing findings keep their seed `registry_id`s. Re-scans produce findings with real ids, and the upsert on `(document_id, module)` replaces them.

## Resolved Questions

Answered by Damian on 2026-11-21, checked against the challenge documents:

1. **Curated domains for domestic firms:** yes, as `knf_domains_manual.csv` drafted by the agent from verifiable official sites, each row with `verified_by_human` `false` until Damian checks it (decision 6).
2. **Former names:** kept as aliases for matching. R1 passes only on the official name; an alias-only mention is `uncertain` with "w materiale użyto nazwy nieoficjalnej/dawnej" (decision 10).
3. **Stale warning:** none. The Opis only requires periodic refresh of M1 output (decision 8).
4. **Refresh before hand-in:** no. The snapshot is frozen at implementation time, and its date is in the start-up log and the README.
5. **Scope of types:** `type` stays faithful to the KNF list. M2 covers firms registered in Poland, including Polish branches of foreign firms, and foreign firms without a branch are M1 (Opis p.1). The annex definition of "zagraniczna firma inwestycyjna" includes foreign credit institutions, which stay on the foreign lists with their list's type.
