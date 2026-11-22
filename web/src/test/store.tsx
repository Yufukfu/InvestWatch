import { configureStore } from '@reduxjs/toolkit';
import type { ReactNode } from 'react';
import { Provider } from 'react-redux';
import { api as investWatchApi } from '../api/enhanced';
import { trackRunning } from './inflight';

// A fresh store per call so RTK Query cache does not leak between tests. Its requests still in flight
// when the test ends are awaited by the shared afterEach (inflight.ts), so they do not leak either.
export function makeStore() {
  const store = configureStore({
    reducer: { [investWatchApi.reducerPath]: investWatchApi.reducer },
    middleware: (getDefault) => getDefault().concat(investWatchApi.middleware),
  });
  trackRunning(() => [
    ...store.dispatch(investWatchApi.util.getRunningQueriesThunk()),
    ...store.dispatch(investWatchApi.util.getRunningMutationsThunk()),
  ]);
  return store;
}

export function storeWrapper() {
  const store = makeStore();
  return function StoreWrapper({ children }: { children: ReactNode }) {
    return <Provider store={store}>{children}</Provider>;
  };
}
