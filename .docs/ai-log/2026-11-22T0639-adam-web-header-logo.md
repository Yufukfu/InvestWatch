---
when: Sun 06:39
who: Adam
---

## What was done with AI

Designed the InvestWatch logo in Paper from the deck palette and the dashboard mockups, exported light and dark PNGs, then added the mark to the web header and favicon. Sized as a small `web/` tweak with no OpenSpec change (`IW_SKIP_SPEC=1`).

## Outcome / lesson

The full suite caught one thing the change broke: an existing XSS test asserted no `<img>` anywhere on the page, so it was narrowed to exclude the brand mark. A first PDF overlay carried an opaque grey plate; a visual check by a subagent caught it and the overlay was rebuilt with a transparent background.
