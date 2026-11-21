import { configureStore } from '@reduxjs/toolkit';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Provider } from 'react-redux';
import { describe, expect, it } from 'vitest';
import { investWatchApi } from '../../api/generated';
import { server } from '../../test/setup';
import { TrendPage } from './TrendPage';

function renderPage() {
  const store = configureStore({
    reducer: { [investWatchApi.reducerPath]: investWatchApi.reducer },
    middleware: (getDefault) => getDefault().concat(investWatchApi.middleware),
  });
  return render(
    <Provider store={store}>
      <TrendPage />
    </Provider>,
  );
}

describe('TrendPage (against contract mocks)', () => {
  it('shows loading, then the chart for the hourly bucket by default', async () => {
    const buckets: (string | null)[] = [];
    server.use(
      http.get('http://localhost/api/stats/trend', ({ request }) => {
        buckets.push(new URL(request.url).searchParams.get('bucket'));
        return HttpResponse.json({ bucket: 'hour', points: [{ t: '2026-11-20T17:00:00Z', M1: 2, M2: 1, M3: 0 }] });
      }),
    );
    renderPage();
    expect(screen.getByText('Ładowanie wykresu…')).toBeInTheDocument();
    expect(await screen.findByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 2, M2 1, M3 0');
    expect(screen.getByRole('button', { name: 'Godzina' })).toHaveAttribute('aria-pressed', 'true');
    expect(buckets).toEqual(['hour']);
  });

  it('requests daily buckets after the user switches to Dzień', async () => {
    const buckets: (string | null)[] = [];
    server.use(
      http.get('http://localhost/api/stats/trend', ({ request }) => {
        buckets.push(new URL(request.url).searchParams.get('bucket'));
        return HttpResponse.json({ bucket: 'day', points: [{ t: '2026-11-20T00:00:00Z', M1: 1, M2: 1, M3: 1 }] });
      }),
    );
    renderPage();
    await screen.findByRole('img');
    fireEvent.click(screen.getByRole('button', { name: 'Dzień' }));
    expect(screen.getByRole('button', { name: 'Dzień' })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(buckets).toEqual(['hour', 'day']));
  });

  it('shows an error text when the API is unreachable', async () => {
    server.use(http.get('http://localhost/api/stats/trend', () => HttpResponse.error()));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się pobrać danych trendu.');
  });
});
