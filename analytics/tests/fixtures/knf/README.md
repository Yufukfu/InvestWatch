# KNF page snapshots

Trimmed copies of the real KNF pages, fetched read-only on 2026-11-21 (change `analytics-knf-registry`, see `openspec/changes/analytics-knf-registry/evidence.md`). Each list page keeps the `<div id="entityTable">` block verbatim, pagination included. The site's navigation, scripts and styles are dropped and replaced by a minimal `<html>` shell. `summary.html` keeps only the summary page's links into the investment-firm section.

| File | Source (under `https://www.knf.gov.pl/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych`) |
|---|---|
| `summary.html` | the section page itself |
| `banks.html` | `/Banki_prowadzace_dzialalnosc_maklerska` |
| `dm_p1.html`, `dm_p2.html` | `/domy_maklerskie`, `?page=2` |
| `branches.html` | `/notyfikowane_firmy_inwestycyjne_oddzialy` |
| `nobranch_p1.html`, `nobranch_p2.html`, `nobranch_p36.html` | `/notyfikowane_zagraniczne_firmy_inwestycyjne`, `?page=2`, `?page=36` (the last page; `?page=99` returned the same records) |

Tests serve these through `tests/knf_fixtures.py` (`FakeFetcher`). They never fetch the network. The failure cases (renamed label, missing container, blank names, summary without a link) are derived from these files inside the tests.

Source: Komisja Nadzoru Finansowego, www.knf.gov.pl (reuse with the source named, per the KNF legal note).
