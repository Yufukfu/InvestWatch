import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Provider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { config } from './config';
import findings from './test/fixtures/findings.json';
import summary from './test/fixtures/summary.json';
import { server } from './test/setup';
import { makeStore } from './test/store';

vi.mock('socket.io-client', async () => (await import('./test/inertSocket')).inertSocketModule);

// A fresh store per test so RTK Query cache does not leak between scenarios.
// `page` is the hash of the sub-page to start on; without it the overview shows (an empty hash).
function renderApp(page?: string) {
  if (page) window.location.hash = page;
  const store = makeStore();
  return render(
    <Provider store={store}>
      <App />
    </Provider>,
  );
}

describe('App (against contract mocks)', () => {
  it('renders findings from the generated client as plain text', async () => {
    renderApp('zgloszenia');
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
    expect(region).toHaveTextContent(`${summary.total} zgłoszeń, z czego`);
  });

  it('opens the section menu from a hamburger button and closes it after a link is chosen', () => {
    renderApp();
    const toggle = screen.getByRole('button', { name: 'Menu' });
    const nav = screen.getByRole('navigation', { name: 'Sekcje' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    const exportRegion = screen.getByRole('group', { name: 'Eksport raportu' });
    expect(toggle.getAttribute('aria-controls')?.split(' ')).toEqual([nav.id, exportRegion.id]);
    expect(nav.id).not.toBe('');
    expect(exportRegion.id).not.toBe('');
    expect(exportRegion).not.toHaveClass('header-export-open');
    expect(nav).not.toHaveClass('app-nav-open');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(nav).toHaveClass('app-nav-open');
    expect(exportRegion).toHaveClass('header-export-open');
    fireEvent.click(within(nav).getByRole('link', { name: 'Zgłoszenia' }));
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(nav).not.toHaveClass('app-nav-open');
    fireEvent.click(toggle);
    fireEvent.click(toggle);
    expect(nav).not.toHaveClass('app-nav-open');
  });

  it('labels the tool and links the header to the four sections', async () => {
    renderApp();
    expect(screen.getByText('NARZĘDZIE NADZORCZE')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'InvestWatch' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Sekcje' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Przegląd', '#przeglad'],
      ['Zgłoszenia', '#zgloszenia'],
      ['Powiązania', '#powiazania'],
      ['Kalibracja', '#kalibracja'],
    ]);
    // The first section is current until the user follows another link.
    expect(links.map((a) => a.getAttribute('aria-current'))).toEqual(['location', null, null, null]);
    fireEvent.click(links[3]);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await waitFor(() => expect(links.map((a) => a.getAttribute('aria-current'))).toEqual([null, null, null, 'location']));
  });

  describe('sub-pages', () => {
    it('opens the detail for a finding link that has no hash, and writes the hash without a history entry', async () => {
      window.history.replaceState(null, '', `/?finding=${findings.items[0].id}`);
      const length = window.history.length;
      renderApp();
      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      expect(window.location.hash).toBe('#zgloszenia');
      expect(window.history.length).toBe(length);
      const nav = screen.getByRole('navigation', { name: 'Sekcje' });
      expect(within(nav).getByRole('link', { name: 'Zgłoszenia' })).toHaveAttribute('aria-current', 'location');
    });

    it('shows the findings table for a filter-only link that has no hash', async () => {
      window.history.replaceState(null, '', '/?module=M1&sort=-score');
      renderApp();
      await screen.findByText(findings.items[0].title);
      expect(document.querySelector('table.findings')).not.toBeNull();
      expect(screen.queryByRole('region', { name: 'Podsumowanie' })).toBeNull();
    });

    it('keeps the page a hash names, even when the query string addresses findings', async () => {
      window.history.replaceState(null, '', `/?finding=${findings.items[0].id}#kalibracja`);
      renderApp();
      expect(await screen.findByRole('heading', { name: 'Ile alarmów, a ile przeoczeń?' })).toBeInTheDocument();
      expect(window.location.hash).toBe('#kalibracja');
    });

    it('stays on the overview for a query string with no findings parameter', async () => {
      window.history.replaceState(null, '', '/?utm=x');
      renderApp();
      expect(await screen.findByRole('region', { name: 'Podsumowanie' })).toBeInTheDocument();
      expect(window.location.hash).toBe('');
    });

    it('shows the summary and the trend, and nothing else, on the overview', async () => {
      renderApp();
      expect(await screen.findByRole('region', { name: 'Podsumowanie' })).toBeInTheDocument();
      expect(await screen.findByRole('region', { name: 'Trend zgłoszeń' })).toBeInTheDocument();
      expect(document.querySelector('table.findings')).toBeNull();
      expect(screen.queryByRole('heading', { name: 'Ile alarmów, a ile przeoczeń?' })).toBeNull();
    });

    it('shows only the findings on #zgloszenia', async () => {
      renderApp('zgloszenia');
      await screen.findByText(findings.items[0].title);
      expect(screen.queryByRole('region', { name: 'Podsumowanie' })).toBeNull();
      expect(screen.queryByRole('region', { name: 'Trend zgłoszeń' })).toBeNull();
      expect(screen.queryByRole('heading', { name: 'Ile alarmów, a ile przeoczeń?' })).toBeNull();
    });

    it('shows only the calibration panel on #kalibracja', async () => {
      renderApp('kalibracja');
      expect(await screen.findByRole('heading', { name: 'Ile alarmów, a ile przeoczeń?' })).toBeInTheDocument();
      expect(await screen.findByRole('slider', { name: 'Próg dla M2' })).toBeInTheDocument();
      expect(document.querySelector('table.findings')).toBeNull();
      expect(screen.queryByRole('region', { name: 'Podsumowanie' })).toBeNull();
    });

    it('falls back to the overview for an unknown hash', async () => {
      renderApp('nieznana');
      expect(await screen.findByRole('region', { name: 'Podsumowanie' })).toBeInTheDocument();
      const nav = screen.getByRole('navigation', { name: 'Sekcje' });
      expect(within(nav).getByRole('link', { name: 'Przegląd' })).toHaveAttribute('aria-current', 'location');
    });

    it('switches page when a header link is followed, and moves focus to the main region at the top', async () => {
      const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
      renderApp();
      await screen.findByRole('region', { name: 'Podsumowanie' });
      const nav = screen.getByRole('navigation', { name: 'Sekcje' });
      window.location.hash = 'kalibracja';
      expect(await screen.findByRole('heading', { name: 'Ile alarmów, a ile przeoczeń?' })).toBeInTheDocument();
      expect(screen.queryByRole('region', { name: 'Podsumowanie' })).toBeNull();
      expect(within(nav).getByRole('link', { name: 'Kalibracja' })).toHaveAttribute('aria-current', 'location');
      expect(screen.getByRole('main')).toHaveFocus();
      expect(scrollTo).toHaveBeenCalledWith(0, 0);
      scrollTo.mockRestore();
    });

    it('does not steal focus on the first render', async () => {
      renderApp('kalibracja');
      await screen.findByRole('slider', { name: 'Próg dla M2' });
      expect(screen.getByRole('main')).not.toHaveFocus();
    });
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
      // The overview is named, otherwise the filters in the URL would open the findings page.
      renderApp('przeglad');
      fireEvent.click(await screen.findByRole('button', { name: 'Rozpocznij triage' }));
      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      expect(window.location.hash).toBe('#zgloszenia');
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
      expect(await screen.findByText('Brak zgłoszeń dla wybranych filtrów')).toBeInTheDocument();
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
    renderApp('zgloszenia');
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
    renderApp('zgloszenia');
    expect(await screen.findByText('Brak połączenia z API')).toBeInTheDocument();
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się pobrać zgłoszeń.');
  });

  it('opens the Powiązania page from its hash, between Zgłoszenia and Kalibracja', async () => {
    renderApp('powiazania');
    const nav = screen.getByRole('navigation', { name: 'Sekcje' });
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual(['Przegląd', 'Zgłoszenia', 'Powiązania', 'Kalibracja']);
    expect(within(nav).getByRole('link', { name: 'Powiązania' })).toHaveAttribute('aria-current', 'location');
    expect(within(nav).getByRole('link', { name: 'Zgłoszenia' })).not.toHaveAttribute('aria-current');
    expect(await screen.findByRole('heading', { name: 'POWIĄZANIA · M1 · FINFLUENCERZY I FIRMY Z REJESTRU' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Podsumowanie' })).toBeNull();
  });
});

describe('Eksportuj raport in the header', () => {
  const exportLink = () => within(screen.getByRole('banner')).getByRole('link', { name: /^Eksportuj raport/ });

  it('on the findings page exports the current URL filters, and follows a filter change', async () => {
    window.history.replaceState(null, '', '/?module=M2&risk_level=high&sort=-score&page=2#zgloszenia');
    renderApp('zgloszenia');
    await screen.findByText(findings.items[0].title);
    expect(screen.getAllByRole('link', { name: /Eksportuj raport/ })).toHaveLength(1);
    expect(exportLink()).toHaveAttribute('href', `${config.apiBaseUrl}/findings/export?module=M2&risk_level=high&sort=-score`);
    expect(exportLink()).toHaveAttribute('download');
    expect(screen.getByRole('banner')).toHaveTextContent(/CSV, maks\. 10\s000 wierszy/);
    expect(screen.getByRole('banner')).not.toHaveTextContent(/bez filtrów/);
    fireEvent.change(screen.getByLabelText('Moduł'), { target: { value: 'M3' } });
    await waitFor(() =>
      expect(exportLink()).toHaveAttribute('href', `${config.apiBaseUrl}/findings/export?module=M3&risk_level=high&sort=-score`),
    );
  });

  it('warns when the findings list total is above the cap, and not at the cap', async () => {
    let total = 12000;
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.json({ ...findings, total })));
    const first = renderApp('zgloszenia');
    expect(await within(screen.getByRole('banner')).findByText(/tylko pierwsze 10\s000 z 12\s000/)).toBeInTheDocument();
    first.unmount();
    total = 10000;
    renderApp('zgloszenia');
    await screen.findByText(findings.items[0].title);
    expect(screen.getByRole('banner')).not.toHaveTextContent(/tylko pierwsze/);
  });

  it('drops the truncation warning when a later list request fails', async () => {
    server.use(
      http.get('http://localhost/api/findings', ({ request }) =>
        new URL(request.url).searchParams.get('module') ? HttpResponse.error() : HttpResponse.json({ ...findings, total: 12000 }),
      ),
    );
    renderApp('zgloszenia');
    expect(await within(screen.getByRole('banner')).findByText(/tylko pierwsze/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Moduł'), { target: { value: 'M3' } });
    await screen.findByText('Nie udało się pobrać zgłoszeń.');
    expect(screen.getByRole('banner')).not.toHaveTextContent(/tylko pierwsze/);
  });

  it('on another page exports every finding with the default filters and says so', async () => {
    let listCalls = 0;
    server.use(
      http.get('http://localhost/api/findings', () => {
        listCalls += 1;
        return HttpResponse.json({ ...findings, total: 12000 });
      }),
    );
    window.history.replaceState(null, '', '/?module=M2#przeglad');
    renderApp('przeglad');
    await screen.findByRole('region', { name: 'Podsumowanie' });
    expect(exportLink()).toHaveAttribute('href', `${config.apiBaseUrl}/findings/export?sort=-detected_at`);
    expect(screen.getByRole('banner')).toHaveTextContent(/Wszystkie zgłoszenia, bez filtrów/);
    expect(screen.getByRole('banner')).not.toHaveTextContent(/tylko pierwsze/);
    expect(listCalls).toBe(0);
  });

  it('stays available with the current filters when the list fails', async () => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.error()));
    window.history.replaceState(null, '', '/?module=M1#zgloszenia');
    renderApp('zgloszenia');
    await screen.findByText('Nie udało się pobrać zgłoszeń.');
    expect(exportLink()).toHaveAttribute('href', `${config.apiBaseUrl}/findings/export?module=M1&sort=-detected_at`);
    expect(screen.getByRole('banner')).toHaveTextContent(/CSV, maks\. 10\s000 wierszy/);
  });
});

