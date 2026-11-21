import { configureStore } from '@reduxjs/toolkit';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Provider } from 'react-redux';
import { describe, expect, it } from 'vitest';
import { investWatchApi } from '../../api/generated';
import trend from '../../test/fixtures/trend.json';
import { server } from '../../test/setup';
import { TrendPage } from './TrendPage';

function renderPage() {
  const store = configureStore({
    reducer: { [investWatchApi.reducerPath]: investWatchApi.reducer },
    middleware: (getDefault) => getDefault().concat(investWatchApi.middleware),
  });
  render(
    <Provider store={store}>
      <TrendPage />
    </Provider>,
  );
  return store;
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

  it('renders the contract mock (default handlers) with its totals per module', async () => {
    renderPage();
    const sum = (k: 'M1' | 'M2' | 'M3') => trend.points.reduce((n, p) => n + p[k], 0);
    expect(await screen.findByRole('img')).toHaveAccessibleName(
      `Liczba zgłoszeń: M1 ${sum('M1')}, M2 ${sum('M2')}, M3 ${sum('M3')}`,
    );
  });

  it('never shows the hourly totals under Dzień while the day response is pending', async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('http://localhost/api/stats/trend', async ({ request }) => {
        if (new URL(request.url).searchParams.get('bucket') === 'day') {
          await gate;
          return HttpResponse.json({ bucket: 'day', points: [{ t: '2026-11-20T00:00:00Z', M1: 5, M2: 0, M3: 0 }] });
        }
        return HttpResponse.json({ bucket: 'hour', points: [{ t: '2026-11-20T17:00:00Z', M1: 2, M2: 1, M3: 0 }] });
      }),
    );
    renderPage();
    expect(await screen.findByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 2, M2 1, M3 0');
    fireEvent.click(screen.getByRole('button', { name: 'Dzień' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Ładowanie wykresu…');
    expect(screen.queryByRole('img')).toBeNull();
    release();
    expect(await screen.findByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 5, M2 0, M3 0');
  });

  it('keeps the chart on screen while the same bucket refetches (stats invalidated)', async () => {
    let calls = 0;
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('http://localhost/api/stats/trend', async () => {
        calls += 1;
        if (calls > 1) await gate;
        return HttpResponse.json({ bucket: 'hour', points: [{ t: '2026-11-20T17:00:00Z', M1: calls, M2: 0, M3: 0 }] });
      }),
    );
    const store = renderPage();
    expect(await screen.findByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 1, M2 0, M3 0');
    act(() => {
      store.dispatch(investWatchApi.util.invalidateTags(['stats']));
    });
    await waitFor(() => expect(calls).toBe(2));
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.getByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 1, M2 0, M3 0');
    release();
    await waitFor(() => expect(screen.getByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 2, M2 0, M3 0'));
  });

  it('draws the day points exactly as the backend returns them under Dzień', async () => {
    // Two hourly-looking points on the same UTC day: the web app must not re-aggregate what the backend sent.
    const day = [
      { t: '2026-11-20T00:00:00Z', M1: 3, M2: 1, M3: 0 },
      { t: '2026-11-20T00:00:00Z', M1: 2, M2: 0, M3: 4 },
      { t: '2026-11-21T00:00:00Z', M1: 0, M2: 7, M3: 1 },
    ];
    server.use(
      http.get('http://localhost/api/stats/trend', ({ request }) =>
        new URL(request.url).searchParams.get('bucket') === 'day'
          ? HttpResponse.json({ bucket: 'day', points: day })
          : HttpResponse.json(trend),
      ),
    );
    renderPage();
    await screen.findByRole('img');
    fireEvent.click(screen.getByRole('button', { name: 'Dzień' }));
    await screen.findByText('Dni liczone w czasie UTC.');
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(rows.map((r) => Array.from(r.querySelectorAll('td')).map((td) => Number(td.textContent)))).toEqual(
      day.map((p) => [p.M1, p.M2, p.M3]),
    );
  });
});
