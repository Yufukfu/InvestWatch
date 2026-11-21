import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import summary from './mocks/fixtures/summary.json';
import { makeStore } from './test/store';

// A lazy chunk that cannot load (stale tab after a redeploy): reading the export rejects the import.
vi.mock('./features/trend/TrendPage', () => ({
  get TrendPage() {
    throw new Error('chunk failed to load');
  },
}));

describe('App when the trend chunk fails to load', () => {
  it('shows the trend error and keeps the rest of the dashboard', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <Provider store={makeStore()}>
        <App />
      </Provider>,
    );
    expect(await screen.findByRole('alert', {}, { timeout: 4000 })).toHaveTextContent('Nie udało się pobrać danych trendu.');
    const region = await screen.findByRole('region', { name: 'Podsumowanie' });
    expect(region).toHaveTextContent(`${summary.total}Wszystkie zgłoszenia`);
  });
});
