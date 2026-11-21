import { configureStore } from '@reduxjs/toolkit';
import type { ReactNode } from 'react';
import { Provider } from 'react-redux';
import { investWatchApi } from '../api/generated';

// A fresh store per call so RTK Query cache does not leak between tests.
export function makeStore() {
  return configureStore({
    reducer: { [investWatchApi.reducerPath]: investWatchApi.reducer },
    middleware: (getDefault) => getDefault().concat(investWatchApi.middleware),
  });
}

export function storeWrapper() {
  const store = makeStore();
  return function StoreWrapper({ children }: { children: ReactNode }) {
    return <Provider store={store}>{children}</Provider>;
  };
}
