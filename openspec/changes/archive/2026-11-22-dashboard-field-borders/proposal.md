# Proposal

## Why

PR #137 review: text fields (`input`, `select`, `textarea`) are identified only by their border, so a resting border below 3:1 (WCAG 1.4.11) leaves them hard to find, and main's inputs were set to 3:1 by an earlier review fix. Buttons and chips carry a text label and tolerate a soft border. The user accepted the reviewer's compromise ("as you suggest").

## What Changes

- Text fields (`input`, `select`, `textarea`, including the search, filters and the note field) go back to the 3:1 `--control-border` at rest.
- Buttons, chips, filter chips, the nav toggle, the bucket and segmented switches and the data-table button keep the soft `--field-border`.
- The spec's resting-border sentence is narrowed accordingly. Touches no contract, route or event. Owner: `web/`.

## Capabilities

### Modified Capabilities
- `web-design-system`: text fields keep 3:1 borders at rest; other controls may be softer.

## Impact

- `web/src/styles.css` and `web/src/styles.test.ts`.
