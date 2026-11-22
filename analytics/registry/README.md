# Firm registry

Analytics matches documents against the CSV named by `REGISTRY_CSV`. The default is `knf.csv`, the real KNF register. Columns: `id, name, aliases, type, country, website_domains, source_url`; list fields are separated by `|`.

| File | What it is |
|---|---|
| `knf.csv` | The real register of investment firms. **Snapshot of 2026-11-21 (`fetched_at` 2026-11-21T20:49:58Z in `knf.meta.json`)**, frozen at implementation time: 749 firms from the four lists of annexes 1 and 2 (28 brokerage houses, 10 banks conducting brokerage activity, 10 branches of foreign investment firms, 701 foreign investment firms without a branch). |
| `knf.meta.json` | Provenance written with it: `fetched_at` (the snapshot date the worker logs as `registry_loaded`), records and firms per list, curated and unverified domain counts, loader version. |
| `knf_domains_manual.csv` | Curated domains for 31 Polish firms, which KNF lists without a website. These are InvestWatch's attribution aid, not KNF data. Every row names the page it was checked on (`source_url`) and carries `verified_by_human`: an agent drafted each row from the firm's homepage, and Damian checked all 31 by hand on 2026-11-22, so all are `true`. A new row starts as `false` until a human checks it. |
| `seed.csv` | Four **fictional** firms: the three whose `registry_id`s match `contracts/mocks/` and one foreign firm without a Polish branch for the M1 Polish-targeting tests. A test fixture only; tests name it explicitly, and the worker logs a `registry_seed` warning if it is used. No firm has a `source_url`, so `Registry.demo` is true and M3 findings say "(dane demonstracyjne)"; every `knf.csv` row has one. |

Source: Komisja Nadzoru Finansowego, [www.knf.gov.pl](https://www.knf.gov.pl), the lists under "Podmioty rynku kapitałowego / Firmy inwestycyjne". The KNF legal note allows reuse with the source named and a link. Each row's `source_url` is its KNF list.

What the loader derives, and why: ids are uuid5 of the normalized name, kept across reloads and renames (ADR [0311](../../.docs/decisions/0311-knf-registry-source-and-ids.md)). Aliases are generated from legal forms, bank brokerage units, abbreviations, former names and trade names, without generic words, cities or aliases shared with another firm. Domains come from KNF's notes on foreign firms and from the curated file. The requirements are in `openspec/specs/knf-registry-loader/spec.md`, the design and evidence in `openspec/changes/archive/2026-11-21-analytics-knf-registry/`.

## Refresh (by hand, never at build or start-up)

```bash
cd analytics
python -m investwatch_analytics.knf          # writes registry/knf.csv and registry/knf.meta.json
```

The run keeps the previous ids, merges `knf_domains_manual.csv`, and logs a summary (firms added, removed, renamed, dropped aliases). It changes nothing when a page is down, the layout changed, a list lost more than half of its records (`--accept-drop` after checking the page), or the output would not load. Review the diff and commit both files. `pytest -m live` checks the live pages' layout without writing anything.
