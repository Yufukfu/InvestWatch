// Build-time config only (Vite inlines VITE_* vars). Never put secrets here: everything is shipped to the browser.
// Defaults are same-origin paths, routed by the gateway, so one image works in every environment.
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api',
  eventsUrl: import.meta.env.VITE_EVENTS_URL ?? '/events',
} as const;
