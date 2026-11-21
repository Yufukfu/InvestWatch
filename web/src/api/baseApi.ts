import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { config } from '../config';

// Empty base API; endpoints are injected by the generated client (generated.ts).
export const baseApi = createApi({
  reducerPath: 'investWatchApi',
  baseQuery: fetchBaseQuery({
    baseUrl: config.apiBaseUrl,
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  }),
  endpoints: () => ({}),
});
