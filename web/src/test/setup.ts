import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { handlers } from './handlers';

// findBy* and waitFor give up after 1 s by default. A flow with two round trips (PATCH, then the refetch
// it triggers) does not fit in that under load (issue #60), so every async query waits up to 5 s.
// Tests that pin "this happens at once" pass their own shorter timeout.
configure({ asyncUtilTimeout: 5_000 });

export const server = setupServer(...handlers('http://localhost/api'));

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  // Filter and selection state lives in the URL; never let one test's URL leak into the next.
  if (typeof window !== 'undefined') window.history.replaceState(null, '', '/');
});
afterAll(() => server.close());
