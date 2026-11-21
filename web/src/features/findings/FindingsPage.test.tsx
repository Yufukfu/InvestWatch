import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import detail from '../../test/fixtures/finding-detail.json';
import findings from '../../test/fixtures/findings.json';
import { server } from '../../test/setup';
import { storeWrapper } from '../../test/store';
import { FindingsPage } from './FindingsPage';

describe('FindingsPage', () => {
  it('shows the loading text, then the rows and count from the API', async () => {
    render(<FindingsPage />, { wrapper: storeWrapper() });
    expect(screen.getByText('Ładowanie…')).toBeInTheDocument();
    expect(await screen.findByText(findings.items[0].title)).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(findings.items.length + 1);
    expect(screen.getByText(`${findings.total} zgłoszeń`)).toBeInTheDocument();
  });

  it('a filter change sends the parameter and shows only what the backend returns', async () => {
    const seen: string[] = [];
    server.use(
      http.get('http://localhost/api/findings', ({ request }) => {
        const p = new URL(request.url).searchParams;
        seen.push(p.toString());
        const items = p.get('module') ? findings.items.filter((i) => i.module === p.get('module')) : findings.items;
        return HttpResponse.json({ ...findings, items, total: items.length });
      }),
    );
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText(findings.items[0].title);
    fireEvent.change(screen.getByLabelText('Moduł'), { target: { value: 'M3' } });
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(findings.items.filter((i) => i.module === 'M3').length + 1));
    expect(seen.at(-1)).toContain('module=M3');
    expect(window.location.search).toBe('?module=M3');
  });

  it('shows the empty state and clears the filters from it', async () => {
    window.history.replaceState(null, '', '/?module=M1');
    server.use(
      http.get('http://localhost/api/findings', ({ request }) =>
        new URL(request.url).searchParams.get('module')
          ? HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 })
          : HttpResponse.json(findings),
      ),
    );
    render(<FindingsPage />, { wrapper: storeWrapper() });
    expect(await screen.findByText('Żadne zgłoszenie nie pasuje do filtrów.')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /Wyczyść filtry/ })[0]);
    expect(await screen.findByText(findings.items[0].title)).toBeInTheDocument();
    expect(window.location.search).toBe('');
  });

  it('shows the error alert when the request fails, and the filters stay usable', async () => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.error()));
    render(<FindingsPage />, { wrapper: storeWrapper() });
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się pobrać zgłoszeń.');
    expect(screen.queryByText('Ładowanie…')).toBeNull();
    expect(screen.getByLabelText('Moduł')).toBeEnabled();
  });

  it('opens the detail from a row, puts it in the URL, and closes on Escape', async () => {
    render(<FindingsPage />, { wrapper: storeWrapper() });
    const row = findings.items.find((i) => i.id === detail.id)!;
    fireEvent.click(await screen.findByRole('button', { name: row.title }));
    expect(window.location.search).toBe(`?finding=${detail.id}`);
    const dialog = await screen.findByRole('dialog');
    expect(await screen.findByRole('heading', { level: 2, name: detail.title })).toBeInTheDocument();
    for (const r of detail.rules.filter((x) => x.result === 'fail' && x.legal_basis)) {
      expect(dialog).toHaveTextContent(r.legal_basis!);
    }
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(window.location.search).toBe('');
  });

  it('opens the detail from a deep link and shows not found for an unknown id', async () => {
    window.history.replaceState(null, '', `/?finding=${detail.id}`);
    const { unmount } = render(<FindingsPage />, { wrapper: storeWrapper() });
    expect(await screen.findByRole('heading', { level: 2, name: detail.title })).toBeInTheDocument();
    unmount();
    window.history.replaceState(null, '', '/?finding=00000000-0000-4000-8000-000000000000');
    render(<FindingsPage />, { wrapper: storeWrapper() });
    expect(await screen.findByText('To zgłoszenie nie istnieje.')).toBeInTheDocument();
  });

  it('changes the status: the detail and the row show what the API saved', async () => {
    let saved = { status: detail.status, note: detail.note as string | null };
    server.use(
      http.get('http://localhost/api/findings', () =>
        HttpResponse.json({ ...findings, items: findings.items.map((i) => (i.id === detail.id ? { ...i, ...saved } : i)) }),
      ),
      http.get('http://localhost/api/findings/:id', () => HttpResponse.json({ ...detail, ...saved })),
      http.patch('http://localhost/api/findings/:id', async ({ request }) => {
        saved = { ...saved, ...((await request.json()) as object) };
        return HttpResponse.json({ ...detail, ...saved });
      }),
    );
    window.history.replaceState(null, '', `/?finding=${detail.id}`);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    const dialog = await screen.findByRole('dialog');
    const select = await within(dialog).findByLabelText('Status');
    fireEvent.change(select, { target: { value: 'confirmed' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zapisz' }));
    await waitFor(() => expect(within(dialog).getByText('Potwierdzone', { selector: 'dd' })).toBeInTheDocument());
    expect(saved.status).toBe('confirmed');
    const row = screen.getByRole('button', { name: findings.items.find((i) => i.id === detail.id)!.title }).closest('tr')!;
    await waitFor(() => expect(row).toHaveTextContent('Potwierdzone'));
  });

  it('a rejected change shows the error and keeps the saved status', async () => {
    server.use(http.patch('http://localhost/api/findings/:id', () => HttpResponse.json({ error: 'transition not allowed' }, { status: 422 })));
    window.history.replaceState(null, '', `/?finding=${detail.id}`);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(await within(dialog).findByLabelText('Status'), { target: { value: 'closed' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zapisz' }));
    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent('Nie udało się zapisać zmiany: serwer odrzucił tę wartość.');
    expect(within(dialog).getByText('transition not allowed')).toBeInTheDocument();
    expect(within(dialog).getByText('Nowe', { selector: 'dd' })).toBeInTheDocument();
  });
});
