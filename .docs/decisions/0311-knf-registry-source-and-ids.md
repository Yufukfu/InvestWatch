# 0311. KNF registry: source, committed CSV and stable ids

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written for Damian (change `analytics-knf-registry`); accepted by: pending approval of the PR

## Context

Analytics matches documents against `analytics/registry/seed.csv`, three fictional firms, so R1 and the M1/M3 routing mean nothing on real pages (`.docs/analytics-plan.md` §3; Kacper's review of PR #26). The challenge defines an investment firm by the five KNF lists linked in annexes 1 and 2. What those pages offer was checked on 2026-11-21 (`openspec/changes/analytics-knf-registry/evidence.md`). They are server-rendered HTML cards (one `<table>` per firm, `th` labels, `?page=N` pagination) with 760 records over four lists. There is no XLSX, CSV, JSON or API, no register number, KRS, NIP or LEI, and no firm website field. The KNF legal note allows reuse with the source and a link to `www.knf.gov.pl`. Firm ids end up in `findings.firm.registry_id`, which the contract types as any UUID (`contracts/schemas/finding.schema.json`). The repository convention is UUID v4 (`CLAUDE.md`, Conventions).

## Options considered

Where the real registry comes from at run time:

1. **Commit the generated `registry/knf.csv` and refresh by hand** with a loader CLI. The legal note permits it with attribution. Builds and start-up need no network, the evaluation is deterministic, and a refresh is a reviewable diff.
2. **Generate in the Docker build.** `docker compose up` would then depend on knf.gov.pl being reachable and on its markup being unchanged. Builds would not be reproducible, and an offline demo would fail.
3. **Generate at worker start-up.** Same dependency, plus a network fetch in a service that otherwise only talks to Postgres, Redis and the LLM, and a crash loop when KNF changes its layout.

Firm id:

1. **uuid5 of the normalized current name** in a fixed namespace, carried over from the previous CSV when KNF lists the old name in `<strike>`. The same name always gives the same id.
2. **uuid4 per load.** Follows the convention, but every reload would change every id and orphan stored `registry_id`s.
3. **uuid5 of a KNF identifier.** The best key, but none is published on the lists (evidence, Fields).

## Decision

Option 1 for the source and option 1 for the id. The loader (`python -m investwatch_analytics.knf`) parses the HTML lists with the standard library and writes `analytics/registry/knf.csv` in the columns `Registry.from_csv` reads, plus `knf.meta.json` (fetch time, counts, sources). Both files are committed. On any fetch, layout or count failure the loader fails without writing (change design, decision 7). The code and container default of `REGISTRY_CSV` becomes `registry/knf.csv`, and `seed.csv` stays the test and mock fixture. Registry ids are uuid5, a deliberate exception to the v4 convention, because a registry id must be the same on every reload and KNF gives no identifier to derive it from.

## Consequences

- The default registry is real with no network at build or run time. The snapshot is frozen at implementation time; its date (`fetched_at` in the meta file) is logged at start-up and stated in the registry README, and a refresh is a manual loader run.
- A KNF rename without a struck former name yields a new id. Old findings keep the old id and the firm name. The refresh summary lists such cases.
- A KNF markup change breaks only the manual refresh, never the running system. The parser then needs an update.
- Domestic firms have no domain on KNF, so domain matching for them needs the optional hand-curated supplement (`knf_domains_manual.csv`).
- Revisit if KNF publishes a dataset with identifiers (then derive uuid5 from the identifier) or if the KNF public warnings list is added (`registry_warnings`, its own change).
