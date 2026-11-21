import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import { App } from './App';
import { config } from './config';
import { store } from './store';
import './styles.css';

async function enableMocks() {
  // Dev-only: the import is dropped from production builds.
  if (!import.meta.env.DEV || !config.useMocks) return;
  try {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledFrame: 'bypass', quiet: true });
  } catch (error) {
    // Some embedded browsers block Service Workers: keep rendering against the live API instead of a blank page.
    // oxlint-disable-next-line no-console -- dev-only diagnostic, stripped from production builds
    console.warn('[mocks] MSW unavailable, using the live API', error);
  }
}

await enableMocks();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </StrictMode>,
);
