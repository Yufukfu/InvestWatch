# Design

## Context

`Finding.advertiser` (name, handle, profile_url, website) and `Finding.firm` (name, registry_id, authorized) are optional fields of the v1 contract (integration plan §4). M1 findings carry both when the analysis matched a firm. The issue settles the default: build the view client-side from `GET /findings`, no new endpoint.

## Decisions

1. **Client-side aggregation, capped.** `web/CLAUDE.md` says not to compute in `web/` what the backend owns. Grouping a list the API already returns is presentation, not a backend-owned value (no score or risk level is derived), and the issue chooses it explicitly. To keep the cost bounded the hook requests `module=M1&page_size=200&sort=-detected_at`, page 1, and pages 2 and 3 only when `total` says they exist. Cap: 3 pages, 600 findings, most recent first. The UI states `Na podstawie N z T zgłoszeń M1` and, when `T > N`, that older findings are left out. Not an ADR: it is reversible by swapping the hook for an aggregate endpoint later.
2. **Fixed number of hook calls.** RTK Query hooks cannot be called in a loop of variable length; the hook calls `useGetFindingsQuery` three times with `skip` for pages beyond `total`. Same cache and `findings` tag as the findings table, so `finding.created` invalidation refreshes it.
3. **Advertiser identity.** Key = lower-cased `handle`, else `profile_url`, else `website`, else `name`; a finding with none of these, or with no `advertiser`, is skipped. Firm key = `registry_id`, else lower-cased `name`; findings without a firm count toward the advertiser under "bez dopasowanej firmy". Items are de-duplicated by `id`, and items whose `module` is not `M1` are ignored (defensive against a backend that ignores the filter).
4. **Repeat advertiser** = 2+ distinct matched firms or 5+ M1 findings (hen68's mockup legend; was 2+ findings before the extension). Shown as a text badge plus red counts and edges, never colour alone.
5. **Layering (ADR 0204).** `data/useAdvertisers.ts` maps DTOs to `AdvertiserFinding` view models; the pure `aggregate.ts` groups them; `components/AdvertisersTable.tsx` is presentational; `AdvertisersPage.tsx` wires them. Advertiser name and handle are untrusted text: plain React text in `dir="auto"` elements; no links.
6. **Graph without a chart library.** Recharts (the app's chart library) has no bipartite or Sankey layout that fits; the graph is inline SVG drawn by a pure layout function (`graph.ts`): advertisers in count order, firms ordered by the mean position of their advertisers (fewer crossings), edge width linear in the pair's count. Labels are HTML next to the SVG so untrusted text keeps its `dir="auto"` element; the `Tabela` view carries the same data for keyboard and screen-reader users. At most 12 advertisers are drawn; the rest are in the table.
7. **Filters are local, the relation is in the URL.** Filters narrow the already-loaded findings (no extra requests) and live in component state; the open relation is `rel_adv` / `rel_firm` in the search string, like the findings filters, so a link reopens it and the back button returns to the graph.

## Risks

- More than 600 M1 findings: the table covers only the most recent 600, stated in the UI.
- Same advertiser under two handles is two rows (no fuzzy matching).
