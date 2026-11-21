import { investWatchApi } from './generated';

// Cache rules the generated client cannot know (generated.ts is overwritten by `npm run api:generate`).
// enhanceEndpoints changes the same api object, so the generated hooks pick these up.
// A status change moves counts in /stats/summary and /stats/trend, and analyst labels
// (confirmed / false_positive) feed the calibration curve (integration-plan §5), so it also
// invalidates `stats` and `calibration`.
// A threshold save recomputes every risk_level and the curve's current point (web-dashboard rules).
export const api = investWatchApi.enhanceEndpoints({
  endpoints: {
    patchFindingsById: { invalidatesTags: ['findings', 'stats', 'calibration'] },
    putSettingsThresholds: { invalidatesTags: ['settings', 'findings', 'stats', 'calibration'] },
  },
});
