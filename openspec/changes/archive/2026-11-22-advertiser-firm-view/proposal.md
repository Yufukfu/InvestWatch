# Proposal

## Why

UKNF's M1 goal is to verify the cooperation between a licensed firm and the third parties (finfluencers, affiliates) who advertise it. Findings already carry `advertiser` and the matched `firm` (integration plan §4), but the dashboard only lists findings one by one, so an analyst cannot see who promotes which firm, or who does it repeatedly (issue #72).

## What Changes

- A new dashboard section "Reklamodawcy i firmy (M1)": a table with one row per advertiser, the licensed firms it promotes with a finding count per firm, and the advertiser's total finding count. Rows are sorted by finding count; an advertiser with two or more findings is highlighted as a repeat advertiser (text label plus colour, never colour alone).
- Built in the browser from the existing `GET /findings?module=M1`, paged with `page_size=200` up to a fixed cap of 3 pages (600 findings). The section states how many findings it is based on and says when the cap cut the list.
- Lowest-effort version from the issue (table, not a graph). Added as one section in `App.tsx`; no other shared file changes.

Out of scope: a graph view, an aggregate endpoint (needs the team's OK, issue #72), M3 advertisers (they offer advice, they do not promote a licensed firm), filters on the section.

Module: `web/` (owner per `.github/CODEOWNERS`). Touches no contract, REST route or event: it reads `GET /findings` as it is (`contracts/openapi.yaml` unchanged).

## Capabilities

### New Capabilities

- `web-advertisers`: the advertiser-to-firm table for M1.

### Modified Capabilities

## Impact

- Code: new `web/src/features/advertisers/` (data hook, aggregation, presentational table), one section added to `web/src/App.tsx`, a few CSS rules in `web/src/styles.css`.
- Requests: up to 3 extra `GET /findings` calls on page load (one in the mock and in any dataset under 200 M1 findings). They share the `findings` tag, so real-time invalidation refreshes them like the findings table.
