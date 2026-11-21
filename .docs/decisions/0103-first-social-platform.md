# 0103. First social platform

- Status: proposed
- Date: 2026-11-21
- Deciders: (human, module A with C; to be filled in)

Agent draft: Context and criteria only. No candidate was researched, so there is no evidence on access or terms yet; the decision and its rationale are for a human.

## Context

Team decision: collect from one social platform first, more only if time allows. The contract's `platform` enum allows `facebook|instagram|tiktok|youtube|x|forum|other` (`.docs/integration-plan.md` §3). `scraper-v1` covers web only; a social collector would be its own OpenSpec change. Social documents also fill `author` (name, handle, profile URL, followers).

## Options considered

Candidates from the contract enum: `facebook`, `instagram`, `tiktok`, `youtube`, `x`, `forum`. For each, a human or a follow-up research task should record, with a source link:

1. Is public content readable without a login, and through an official or JSON endpoint (ladder step 1)?
2. Does it need Playwright, or `blocks`/screenshots for the visual rules?
3. How much of the UKNF-relevant risky investment content (the challenge brief) appears there?
4. Terms, rate limits and legal risk for on-premise collection.

## Decision

(to be written by a human)

## Consequences

(to be written by a human)
