# Proposal

## Why

Resting borders of buttons, inputs, selects and chips use the 3:1 grey (`#8a919e`), which reads heavy next to the rest of the modern styling. The user asked for slightly lighter borders. The 3:1 grey is already the lightest compliant value, so a visibly lighter border is a decision to trade resting non-text contrast for look, and to make the interactive states carry the contrast instead.

## What Changes

- New token `--field-border` (soft grey) for the resting border of buttons, inputs, selects, textareas, chips, filter chips, the nav toggle, the bucket and segmented switches and the data-table button.
- `--control-border` (3:1) stays and is used on hover, on focus and for checked or selected controls; the 2px focus ring is unchanged.
- The spec's non-text contrast sentence is narrowed accordingly (see the delta). Text contrast (4.5:1) and the 44px targets are unchanged.
- Touches no contract, REST route or event. Owner: `web/`. Decision made by the user in the session (chose "soft border + stronger hover/focus" over keeping 3:1).

Out of scope: palette roles, layout, dark theme.

## Capabilities

### Modified Capabilities
- `web-design-system`: resting control borders may be softer than 3:1; hover, focus and selected states carry the 3:1 border.

## Impact

- `web/src/styles.css` (token and control rules) and `web/src/styles.test.ts`.
