import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { handlers } from './handlers';

export const server = setupServer(...handlers('http://localhost/api'));

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  // Filter and selection state lives in the URL; never let one test's URL leak into the next.
  window.history.replaceState(null, '', '/');
});
afterAll(() => server.close());
