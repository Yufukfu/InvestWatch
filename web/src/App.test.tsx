import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    expect(region).toHaveTextContent(`${summary.total} zgłoszeń`);
  });

  it('labels the tool and links the header to the three sections', async () => {
    renderApp();
    expect(screen.getByText('NARZĘDZIE NADZORCZE')).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Sekcje' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Przegląd', '#przeglad'],
      ['Zgłoszenia', '#zgloszenia'],
      ['Kalibracja', '#kalibracja'],
    ]);
    // Each anchor points at an element that exists as soon as the app is rendered, even before data arrives.
    for (const id of ['przeglad', 'zgloszenia', 'kalibracja']) {
      expect(document.getElementById(id), id).not.toBeNull();
    }
    await screen.findByRole('region', { name: 'Podsumowanie' });
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

  describe('triage', () => {
    // Records every GET /findings the page sends and answers with the fixture (or what `answer` says).
    function recordFindings(answer?: (p: URLSearchParams) => Response) {
      const seen: URLSearchParams[] = [];
      server.use(
        http.get('http://localhost/api/findings', ({ request }) => {
          const p = new URL(request.url).searchParams;
          seen.push(p);
          return answer?.(p) ?? HttpResponse.json(findings);
        }),
      );
      return seen;
    }

    it('clears the other filters, asks for new high-risk findings and opens the first one', async () => {
      window.history.replaceState(null, '', '/?page=3&module=M2&q=zysk&date_from=2026-11-01&date_to=2026-11-20');
      const seen = recordFindings();
      renderApp();
      fireEvent.click(await screen.findByRole('button', { name: 'Rozpocznij triage' }));
      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      const last = seen.at(-1)!;
      expect(last.get('status')).toBe('new');
      expect(last.get('risk_level')).toBe('high');
      expect(last.get('page')).toBe('1');
      for (const gone of ['module', 'q', 'date_from', 'date_to']) expect(last.has(gone), gone).toBe(false);
      // Newest first is the default sort and stays out of the URL; the one-shot flag does not stay either.
      expect(window.location.search).toBe(`?status=new&risk_level=high&finding=${findings.items[0].id}`);
    });

    it('opens no detail when the triage list is empty, and leaves no flag behind', async () => {
      const seen = recordFindings((p) =>
        p.get('risk_level') === 'high' ? HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 }) : HttpResponse.json(findings),
      );
      renderApp();
      fireEvent.click(await screen.findByRole('button', { name: 'Rozpocznij triage' }));
      expect(await screen.findByText('Żadne zgłoszenie nie pasuje do filtrów.')).toBeInTheDocument();
      expect(seen.at(-1)!.get('risk_level')).toBe('high');
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(window.location.search).toBe('?status=new&risk_level=high');
    });

    it('opens no detail when the triage request fails, and leaves no flag behind', async () => {
      recordFindings((p) => (p.get('risk_level') === 'high' ? HttpResponse.error() : HttpResponse.json(findings)));
      renderApp();
      fireEvent.click(await screen.findByRole('button', { name: 'Rozpocznij triage' }));
      expect(await screen.findByText('Nie udało się pobrać zgłoszeń.')).toBeInTheDocument();
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(window.location.search).toBe('?status=new&risk_level=high');
    });

    it('does not reopen a detail the user closed', async () => {
      recordFindings();
      renderApp();
      fireEvent.click(await screen.findByRole('button', { name: 'Rozpocznij triage' }));
      fireEvent.click(await screen.findByRole('button', { name: 'Zamknij' }));
      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
      expect(window.location.search).toBe('?status=new&risk_level=high');
    });

    it('is absent when the summary reports no high-risk findings', async () => {
      server.use(
        http.get('http://localhost/api/stats/summary', () =>
          HttpResponse.json({ ...summary, by_risk_level: { ...summary.by_risk_level, high: 0 } }),
        ),
      );
      renderApp();
      await screen.findByRole('region', { name: 'Podsumowanie' });
      expect(screen.queryByRole('button', { name: /triage/i })).toBeNull();
    });
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
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się pobrać zgłoszeń.');
  });
});
