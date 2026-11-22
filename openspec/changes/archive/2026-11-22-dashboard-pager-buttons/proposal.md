# Proposal

## Why

On page 1 the `Poprzednia` pager button is disabled and the shared `.btn:disabled` rule fades it to 55% opacity, so it looks a different colour from `Następna`. The user asked for the two buttons to look the same.

## What Changes

- The pager's disabled buttons keep the colours of the enabled ones; the disabled state stays in the `disabled` attribute (screen readers, no click, no focus) and the `not-allowed` cursor.
- Touches no contract, route or event. Owner: `web/`. Out of scope: other disabled buttons.

## Capabilities

### Modified Capabilities
- `web-design-system`: adds a requirement for the pager buttons' look.

## Impact

- `web/src/styles.css`, `web/src/styles.test.ts`.
