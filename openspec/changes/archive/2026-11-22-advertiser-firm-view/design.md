# Design

## Context

`Finding.advertiser` (name, handle, profile_url, website) and `Finding.firm` (name, registry_id, authorized) are optional fields of the v1 contract (integration plan §4). M1 findings carry both when the analysis matched a firm. The issue settles the default: build the view client-side from `GET /findings`, no new endpoint.

## Decisions

1. **Client-side aggregation, capped.** `web/CLAUDE.md` says not to compute in `web/` what the backend owns. Grouping a list the API already returns is presentation, not a backend-owned value (no score or risk level is derived), and the issue chooses it explicitly. To keep the cost bounded the hook requests `module=M1&page_size=200&sort=-detected_at`, page 1, and pages 2 and 3 only when `total` says they exist. Cap: 3 pages, 600 findings, most recent first. The UI states `Na podstawie N z T zgłoszeń M1` and, when `T > N`, that older findings are left out. Not an ADR: it is reversible by swapping the hook for an aggregate endpoint later.
2. **Fixed number of hook calls.** RTK Query hooks cannot be called in a loop of variable length; the hook calls `useGetFindingsQuery` three times with `skip` for pages beyond `total`. Same cache and `findings` tag as the findings table, so `finding.created` invalidation refreshes it.
3. **Advertiser identity.** Key = lower-cased `handle`, else `profile_url`, else `website`, else `name`; a finding with none of these, or with no `advertiser`, is skipped. Firm key = `registry_id`, else lower-cased `name`; findings without a firm count toward the advertiser under "bez dopasowanej firmy". Items are de-duplicated by `id`, and items whose `module` is not `M1` are ignored (defensive against a backend that ignores the filter).
4. **Repeat advertiser** = 2 or more M1 findings. Shown as a text badge `Powtarzający się` plus a row accent.
5. **Layering (ADR 0204).** `data/useAdvertisers.ts` maps DTOs to `AdvertiserFinding` view models; the pure `aggregate.ts` groups them; `components/AdvertisersTable.tsx` is presentational; `AdvertisersPage.tsx` wires them. Advertiser name and handle are untrusted text: plain React text in `dir="auto"` elements; no links.

## Risks

- More than 600 M1 findings: the table covers only the most recent 600, stated in the UI.
- Same advertiser under two handles is two rows (no fuzzy matching).
