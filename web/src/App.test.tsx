import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Provider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import findings from './test/fixtures/findings.json';
import summary from './test/fixtures/summary.json';
import { server } from './test/setup';
import { makeStore } from './test/store';

vi.mock('socket.io-client', async () => (await import('./test/inertSocket')).inertSocketModule);

// A fresh store per test so RTK Query cache does not leak between scenarios.
function renderApp() {
  const store = makeStore();
  return render(
    <Provider store={store}>
      <App />
    </Provider>,
  );
}

describe('App (against contract mocks)', () => {
  it('renders findings from the generated client as plain text', async () => {
    renderApp();
    expect(await screen.findByText(findings.items[0].title)).toBeInTheDocument();
    expect(await screen.findByText('System działa')).toBeInTheDocument();
    // Scoped: the trend section has its own data table.
    const table = document.querySelector<HTMLElement>('table.findings');
    expect(table).not.toBeNull();
    expect(within(table!).getAllByRole('row')).toHaveLength(findings.items.length + 1);
  });

  it('renders the summary counts next to the findings', async () => {
    renderApp();
    const region = await screen.findByRole('region', { name: 'Podsumowanie' });
    expect(region).toHaveTextContent(`${summary.total}Wszystkie zgłoszenia`);
  });

  it('renders the trend section (lazy-loaded) between summary and findings', async () => {
    renderApp();
    const trend = await screen.findByRole('region', { name: 'Trend zgłoszeń' });
    const summaryRegion = await screen.findByRole('region', { name: 'Podsumowanie' });
    expect(summaryRegion.compareDocumentPosition(trend) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const findingsTable = document.querySelector('table.findings');
    expect(findingsTable).not.toBeNull();
    expect(trend.compareDocumentPosition(findingsTable!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('mounts the calibration panel (lazy-loaded) after the findings', async () => {
    renderApp();
    const heading = await screen.findByRole('heading', { name: 'Kalibracja progów' });
    expect(await screen.findByRole('slider', { name: 'Próg dla M2' })).toBeInTheDocument();
    const findingsTable = document.querySelector('table.findings');
    expect(findingsTable).not.toBeNull();
    expect(findingsTable!.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('renders markup in scraped text literally, never as HTML', async () => {
    const payload = '<img src=x onerror=alert(1)>Zysk 20%';
    server.use(
      http.get('http://localhost/api/findings', () =>
        HttpResponse.json({ ...findings, items: [{ ...findings.items[0], title: payload }] }),
      ),
    );
    renderApp();
    expect(await screen.findByText(payload)).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
  });

  it('tells "system down" apart from "API unreachable"', async () => {
    server.use(http.get('http://localhost/api/health', () => HttpResponse.json({ status: 'down', services: {} })));
    renderApp();
    expect(await screen.findByText('System nie działa')).toBeInTheDocument();
    expect(screen.queryByText('Brak połączenia z API')).toBeNull();
  });

  it('shows an API-down state instead of crashing when the API is unreachable', async () => {
    server.use(
      http.get('http://localhost/api/health', () => HttpResponse.error()),
      http.get('http://localhost/api/findings', () => HttpResponse.error()),
      http.get('http://localhost/api/stats/summary', () => HttpResponse.error()),
    );
    renderApp();
    expect(await screen.findByText('Brak połączenia z API')).toBeInTheDocument();
    // The findings table and the advertiser section each show their own error alert.
    const alerts = await screen.findAllByRole('alert');
    expect(alerts.map((a) => a.textContent)).toEqual(
      expect.arrayContaining(['Nie udało się pobrać zgłoszeń.', 'Nie udało się pobrać danych o reklamodawcach.']),
    );
  });
});
