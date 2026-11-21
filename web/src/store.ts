import { configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { api as investWatchApi } from './api/enhanced';

export const store = configureStore({
  reducer: { [investWatchApi.reducerPath]: investWatchApi.reducer },
  middleware: (getDefault) => getDefault().concat(investWatchApi.middleware),
});

setupListeners(store.dispatch);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
