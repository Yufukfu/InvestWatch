import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
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
    expect(await screen.findByText('Brak zgłoszeń dla wybranych filtrów')).toBeInTheDocument();
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
    fireEvent.click(await within(dialog).findByRole('radio', { name: 'Potwierdzone' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zapisz decyzję' }));
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
    fireEvent.click(await within(dialog).findByRole('radio', { name: 'Zamknięte' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zapisz decyzję' }));
    const alert = within(dialog).getByRole('alert');
    await waitFor(() => expect(alert).toHaveTextContent('Nie udało się zapisać zmiany: serwer odrzucił tę wartość.'));
    expect(within(dialog).getByText('transition not allowed')).toBeInTheDocument();
    expect(within(dialog).getByText('Nowe', { selector: 'dd' })).toBeInTheDocument();
  });

  function paged(seen: URLSearchParams[], hold?: { wait: boolean; release?: () => void }) {
    server.use(
      http.get('http://localhost/api/findings', async ({ request }) => {
        const p = new URL(request.url).searchParams;
        seen.push(p);
        if (hold?.wait && seen.length > 1) await new Promise<void>((r) => (hold.release = r));
        return HttpResponse.json({ ...findings, total: 60, page: Number(p.get('page') ?? 1), page_size: Number(p.get('page_size') ?? 25) });
      }),
    );
  }

  it('the pager, page size and sort headers send their parameters', async () => {
    const seen: URLSearchParams[] = [];
    paged(seen);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText('Strona 1 z 3');
    fireEvent.click(screen.getByRole('button', { name: 'Następna strona' }));
    await waitFor(() => expect(seen.at(-1)?.get('page')).toBe('2'));
    fireEvent.change(screen.getByLabelText('Na stronie'), { target: { value: '50' } });
    await waitFor(() => expect(seen.at(-1)?.get('page_size')).toBe('50'));
    expect(seen.at(-1)?.get('page')).toBe('1');
    fireEvent.click(screen.getByRole('button', { name: 'Wynik' }));
    await waitFor(() => expect(seen.at(-1)?.get('sort')).toBe('-score'));
    expect(window.location.search).toBe('?sort=-score&page_size=50');
  });

  it('platform, search and dates reach the request', async () => {
    const seen: URLSearchParams[] = [];
    paged(seen);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText('Strona 1 z 3');
    fireEvent.change(screen.getByLabelText('Platforma'), { target: { value: 'instagram' } });
    await waitFor(() => expect(seen.at(-1)?.get('platform')).toBe('instagram'));
    fireEvent.change(screen.getByLabelText('Od dnia'), { target: { value: '2026-11-20' } });
    await waitFor(() => expect(seen.at(-1)?.get('date_from')).toBe('2026-11-20T00:00:00Z'));
    fireEvent.change(screen.getByLabelText('Szukaj'), { target: { value: 'inwestor jan' } });
    await waitFor(() => expect(seen.at(-1)?.get('q')).toBe('inwestor jan'));
  });

  it('the first-page action on an empty page past the end goes to page 1', async () => {
    window.history.replaceState(null, '', '/?page=9');
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('http://localhost/api/findings', ({ request }) => {
        const p = new URL(request.url).searchParams;
        seen.push(p);
        return HttpResponse.json({ items: p.get('page') === '9' ? [] : findings.items, total: 9, page: 1, page_size: 25 });
      }),
    );
    render(<FindingsPage />, { wrapper: storeWrapper() });
    fireEvent.click(await screen.findByRole('button', { name: 'Wróć do pierwszej strony' }));
    await waitFor(() => expect(seen.at(-1)?.get('page')).toBe('1'));
    expect(await screen.findByText(findings.items[0].title)).toBeInTheDocument();
  });

  it.each(['Następna strona', 'sort'])('keyboard focus stays on %s while the next result loads', async (target) => {
    const seen: URLSearchParams[] = [];
    const hold = { wait: true, release: undefined as undefined | (() => void) };
    paged(seen, hold);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText('Strona 1 z 3');
    const control = target === 'sort' ? screen.getByRole('button', { name: 'Wynik' }) : screen.getByRole('button', { name: target });
    control.focus();
    fireEvent.click(control);
    await waitFor(() => expect(seen).toHaveLength(2));
    expect(control).toBeInTheDocument();
    expect(control).toHaveFocus();
    expect(screen.getByRole('table').parentElement).toHaveAttribute('aria-busy', 'true');
    act(() => hold.release?.());
    await waitFor(() => expect(screen.getByRole('table').parentElement).toHaveAttribute('aria-busy', 'false'));
    expect(control).toHaveFocus();
  });

  it('after a keyboard save, focus stays inside the dialog', async () => {
    let saved = { status: detail.status, note: detail.note as string | null };
    server.use(
      http.get('http://localhost/api/findings/:id', () => HttpResponse.json({ ...detail, ...saved })),
      http.patch('http://localhost/api/findings/:id', async ({ request }) => {
        saved = { ...saved, ...((await request.json()) as object) };
        return HttpResponse.json({ ...detail, ...saved });
      }),
    );
    window.history.replaceState(null, '', `/?finding=${detail.id}`);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(await within(dialog).findByRole('radio', { name: 'Zamknięte' }));
    const save = within(dialog).getByRole('button', { name: 'Zapisz decyzję' });
    save.focus();
    fireEvent.click(save);
    await waitFor(() => expect(within(dialog).getByText('Zamknięte', { selector: 'dd' })).toBeInTheDocument());
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(within(dialog).getByRole('status')).toHaveTextContent('Zapisano.');
  });

  describe('module switcher (one post, several modules)', () => {
    // The contract mocks hold one post with an M1 and an M3 finding; their details are built here
    // from the detail mock, each with its own rule, so the test can tell which module is shown.
    const shared = (i: (typeof findings.items)[number]) => findings.items.filter((x) => x.document_id === i.document_id).length > 1;
    const m1 = findings.items.find((i) => i.module === 'M1' && shared(i))!;
    const m3 = findings.items.find((i) => i.module === 'M3' && i.document_id === m1.document_id)!;
    const ruleOf = (id: string, name: string) => ({ ...detail.rules[0], rule_id: id, name, result: 'fail' as const });
    const details: Record<string, object> = {
      [m1.id]: { ...detail, ...m1, rules: [ruleOf('S1.1', 'Reklama firmy przez finfluencera')] },
      [m3.id]: { ...detail, ...m3, rules: [ruleOf('S3.1', 'Płatne sygnały transakcyjne')] },
    };

    function documentApi(opts: { siblings?: 'ok' | 'error' } = {}) {
      const seen: URLSearchParams[] = [];
      server.use(
        http.get('http://localhost/api/findings', ({ request }) => {
          const p = new URL(request.url).searchParams;
          seen.push(p);
          const doc = p.get('document_id');
          if (doc && opts.siblings === 'error') return HttpResponse.error();
          let items = doc ? findings.items.filter((i) => i.document_id === doc) : findings.items;
          if (p.get('module')) items = items.filter((i) => i.module === p.get('module'));
          return HttpResponse.json({ ...findings, items, total: items.length });
        }),
        http.get('http://localhost/api/findings/:id', ({ params }) =>
          details[params.id as string]
            ? HttpResponse.json(details[params.id as string] as Record<string, unknown>)
            : HttpResponse.json({ error: 'finding not found' }, { status: 404 }),
        ),
      );
      return seen;
    }

    it('switches from M1 to M3: URL, rules and focus on the switcher', async () => {
      documentApi();
      window.history.replaceState(null, '', `/?finding=${m1.id}`);
      render(<FindingsPage />, { wrapper: storeWrapper() });
      const dialog = await screen.findByRole('dialog');
      const nav = await within(dialog).findByRole('navigation', { name: 'Moduły tego materiału' });
      expect(within(nav).getByRole('button', { name: /M1/ })).toHaveAttribute('aria-current', 'true');
      expect(within(dialog).getByText('Reklama firmy przez finfluencera')).toBeInTheDocument();
      fireEvent.click(within(nav).getByRole('button', { name: /M3/ }));
      expect(window.location.search).toBe(`?finding=${m3.id}`);
      const next = await screen.findByRole('dialog');
      expect(await within(next).findByText('Płatne sygnały transakcyjne')).toBeInTheDocument();
      expect(within(next).queryByText('Reklama firmy przez finfluencera')).toBeNull();
      await waitFor(() => expect(within(next).getByRole('button', { name: /M3/ })).toHaveFocus());
      expect(within(next).getByRole('button', { name: /M3/ })).toHaveAttribute('aria-current', 'true');
    });

    it('opening a finding from the list keeps focus on Zamknij, not on the switcher', async () => {
      documentApi();
      render(<FindingsPage />, { wrapper: storeWrapper() });
      fireEvent.click(await screen.findByRole('button', { name: m1.title }));
      const dialog = await screen.findByRole('dialog');
      await within(dialog).findByRole('navigation', { name: 'Moduły tego materiału' });
      await new Promise((r) => setTimeout(r, 20));
      expect(within(dialog).getByRole('button', { name: 'Zamknij' })).toHaveFocus();
    });

    it('the back button returns to the M1 detail', async () => {
      documentApi();
      window.history.replaceState(null, '', `/?finding=${m1.id}`);
      render(<FindingsPage />, { wrapper: storeWrapper() });
      const nav = await screen.findByRole('navigation', { name: 'Moduły tego materiału' });
      fireEvent.click(within(nav).getByRole('button', { name: /M3/ }));
      expect(await screen.findByText('Płatne sygnały transakcyjne')).toBeInTheDocument();
      await act(async () => {
        window.history.back();
        await new Promise<void>((r) => window.addEventListener('popstate', () => r(), { once: true }));
      });
      expect(window.location.search).toBe(`?finding=${m1.id}`);
      expect(await screen.findByText('Reklama firmy przez finfluencera')).toBeInTheDocument();
    });

    it('shows no switcher when the document has only the open finding', async () => {
      window.history.replaceState(null, '', `/?finding=${detail.id}`);
      render(<FindingsPage />, { wrapper: storeWrapper() });
      expect(await screen.findByRole('heading', { level: 2, name: detail.title })).toBeInTheDocument();
      await new Promise((r) => setTimeout(r, 20));
      expect(screen.queryByRole('navigation', { name: 'Moduły tego materiału' })).toBeNull();
    });

    it('a failed sibling request hides only the switcher', async () => {
      const seen = documentApi({ siblings: 'error' });
      window.history.replaceState(null, '', `/?finding=${m1.id}`);
      render(<FindingsPage />, { wrapper: storeWrapper() });
      const dialog = await screen.findByRole('dialog');
      expect(await within(dialog).findByText('Reklama firmy przez finfluencera')).toBeInTheDocument();
      await waitFor(() => expect(seen.some((p) => p.has('document_id'))).toBe(true));
      await new Promise((r) => setTimeout(r, 20));
      expect(within(dialog).queryByRole('navigation', { name: 'Moduły tego materiału' })).toBeNull();
      expect(dialog).not.toHaveTextContent('Nie udało się');
      for (const radio of within(within(dialog).getByRole('radiogroup', { name: 'Status' })).getAllByRole('radio')) expect(radio).toBeEnabled();
    });

    it('a list filtered to M1 still offers M3 in the switcher', async () => {
      const seen = documentApi();
      window.history.replaceState(null, '', `/?module=M1&finding=${m1.id}`);
      render(<FindingsPage />, { wrapper: storeWrapper() });
      const nav = await screen.findByRole('navigation', { name: 'Moduły tego materiału' });
      expect(within(nav).getByRole('button', { name: /M3/ })).toBeInTheDocument();
      const sibling = seen.find((p) => p.has('document_id'))!;
      expect(sibling.get('document_id')).toBe(m1.document_id);
      expect(sibling.has('module')).toBe(false);
    });
  });
});

describe('FindingsPage keyboard shortcuts', () => {
  const press = (key: string, init: KeyboardEventInit = {}) => fireEvent.keyDown(document.body, { key, ...init });
  const settle = () => new Promise((resolve) => setTimeout(resolve, 60));
  const ids = findings.items.map((i) => i.id);

  // Records every PATCH and answers like the API: the changed fields applied to the detail mock.
  function recordPatches(over: Record<string, unknown> = {}) {
    const patches: { id: string; body: Record<string, unknown> }[] = [];
    server.use(
      http.get('http://localhost/api/findings/:id', () => HttpResponse.json({ ...detail, ...over })),
      http.patch('http://localhost/api/findings/:id', async ({ request, params }) => {
        const body = (await request.json()) as Record<string, unknown>;
        patches.push({ id: String(params.id), body });
        return HttpResponse.json({ ...detail, ...over, ...body });
      }),
    );
    return patches;
  }

  async function openDetail(over?: Record<string, unknown>) {
    const patches = recordPatches(over);
    window.history.replaceState(null, '', `/?finding=${detail.id}`);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    const dialog = await screen.findByRole('dialog');
    await within(dialog).findByRole('radiogroup', { name: 'Status' });
    return { patches, dialog };
  }

  it('J with nothing selected opens the first row; J and K then move within the loaded page', async () => {
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText(findings.items[0].title);
    press('j');
    expect(window.location.search).toBe(`?finding=${ids[0]}`);
    press('j');
    expect(window.location.search).toBe(`?finding=${ids[1]}`);
    press('k');
    expect(window.location.search).toBe(`?finding=${ids[0]}`);
  });

  it('K on the first row and K with nothing selected change nothing', async () => {
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText(findings.items[0].title);
    press('k');
    expect(window.location.search).toBe('');
    press('j');
    press('k');
    expect(window.location.search).toBe(`?finding=${ids[0]}`);
  });

  it('J on the last row stays and does not ask for another page', async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('http://localhost/api/findings', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json({ ...findings, total: 60 });
      }),
    );
    window.history.replaceState(null, '', `/?finding=${ids.at(-1)}`);
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText(findings.items[0].title);
    const requests = seen.length;
    press('j');
    await settle();
    expect(window.location.search).toBe(`?finding=${ids.at(-1)}`);
    expect(seen).toHaveLength(requests);
  });

  it('3 sets the open finding to confirmed, and it stays selected', async () => {
    const { patches } = await openDetail();
    press('3');
    await waitFor(() => expect(patches).toEqual([{ id: detail.id, body: { status: 'confirmed' } }]));
    expect(window.location.search).toBe(`?finding=${detail.id}`);
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveTextContent('Potwierdzone'));
  });

  it.each([
    ['1', 'in_review', 'new'],
    ['2', 'new', 'in_review'],
    ['4', 'new', 'false_positive'],
    ['5', 'new', 'closed'],
  ])('%s sets the status %s -> %s', async (key, from, to) => {
    const { patches } = await openDetail({ status: from });
    press(key);
    await waitFor(() => expect(patches).toEqual([{ id: detail.id, body: { status: to } }]));
  });

  it('still works with focus on a status radio: choosing a status does not make the radio a typing field', async () => {
    const { patches } = await openDetail();
    const radio = within(screen.getByRole('dialog')).getByRole('radio', { name: 'Nowe' });
    radio.focus();
    fireEvent.keyDown(radio, { key: '3' });
    await waitFor(() => expect(patches).toEqual([{ id: detail.id, body: { status: 'confirmed' } }]));
  });

  it('sends nothing when the finding already has that status', async () => {
    const { patches } = await openDetail({ status: 'confirmed' });
    press('3');
    await settle();
    expect(patches).toEqual([]);
  });

  it('sends nothing with no detail open', async () => {
    const patches = recordPatches();
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText(findings.items[0].title);
    press('1');
    press('3');
    await settle();
    expect(patches).toEqual([]);
  });

  it('ignores typing in a field and keys held with Ctrl, Meta or Alt', async () => {
    const { patches } = await openDetail();
    fireEvent.keyDown(screen.getByLabelText('Szukaj'), { key: '3' });
    fireEvent.keyDown(within(screen.getByRole('dialog')).getByLabelText('Notatka'), { key: '3' });
    press('3', { ctrlKey: true });
    press('3', { metaKey: true });
    press('3', { altKey: true });
    press('j', { ctrlKey: true });
    await settle();
    expect(patches).toEqual([]);
    expect(window.location.search).toBe(`?finding=${detail.id}`);
  });

  it('shows the same error as a mouse change when the PATCH fails, and the status stays the saved one', async () => {
    const { dialog } = await openDetail();
    // After openDetail, whose own PATCH handler would otherwise win.
    server.use(http.patch('http://localhost/api/findings/:id', () => HttpResponse.json({ error: 'transition not allowed' }, { status: 422 })));
    press('4');
    await waitFor(() =>
      expect(within(dialog).getByRole('alert')).toHaveTextContent('Nie udało się zapisać zmiany: serwer odrzucił tę wartość.'),
    );
    expect(within(dialog).getByText('Nowe', { selector: 'dd' })).toBeInTheDocument();
  });

  it('O opens the source of the selected finding in a new tab without opener access', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    await openDetail();
    press('o');
    expect(open).toHaveBeenCalledWith(detail.url, '_blank', 'noopener,noreferrer');
    open.mockRestore();
  });

  it('O does nothing for a source that is not http or https', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    await openDetail({ url: 'javascript:alert(1)' });
    press('o');
    expect(open).not.toHaveBeenCalled();
    open.mockRestore();
  });

  it('/ focuses the search field and does not type the slash', async () => {
    render(<FindingsPage />, { wrapper: storeWrapper() });
    await screen.findByText(findings.items[0].title);
    const notPrevented = press('/');
    expect(screen.getByLabelText('Szukaj')).toHaveFocus();
    expect(notPrevented).toBe(false);
  });

  it('Escape is left to the detail: it closes once and the shortcuts do nothing more', async () => {
    const { patches } = await openDetail();
    press('Escape');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(window.location.search).toBe('');
    await settle();
    expect(patches).toEqual([]);
  });
});
