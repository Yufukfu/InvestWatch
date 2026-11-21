// Types only: health is a flat DTO, so no mapper (ADR 0204). The type lives here so the data hook
// does not have to import from a component.
// "unreachable" = no answer from the API; "down" = the API answered that the system is down.
export type HealthState = 'loading' | 'ok' | 'degraded' | 'down' | 'unreachable';
