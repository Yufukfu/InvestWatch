import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { AlertsPage } from './features/alerts/AlertsPage';
import { FindingsPage } from './features/findings/FindingsPage';
import detail from './test/fixtures/finding-detail.json';
import findings from './test/fixtures/findings.json';
import { server } from './test/setup';
import { storeWrapper } from './test/store';

// Wiring test with a fake socket (see `fake` below), not a real socket.io connection: it proves that
// events reach the cache and the DOM through the same hook the app mounts. The real connection is
// checked by hand against the mock server (`web/README.md`).

type Handler = (payload?: unknown) => void;
const fake = vi.hoisted(() => {
  const handlers = new Map<string, Handler[]>();
  const socket = {
    on: (e: string, fn: Handler) => {
      handlers.set(e, [...(handlers.get(e) ?? []), fn]);
      return socket;
    },
    disconnect: () => undefined,
  };
  return { socket, fire: (e: string, p?: unknown) => (handlers.get(e) ?? []).forEach((fn) => fn(p)) };
});
vi.mock('socket.io-client', () => ({ io: () => fake.socket }));

function renderBoth() {
  return render(
    <>
      <AlertsPage />
      <FindingsPage />
    </>,
    { wrapper: storeWrapper() },
  );
}

describe('alerts and the findings workspace together', () => {
  it('a status change from another tab shows in the row without a list refetch', async () => {
    let listCalls = 0;
    server.use(
      http.get('http://localhost/api/findings', () => {
        listCalls += 1;
        return HttpResponse.json(findings);
      }),
    );
    renderBoth();
    const target = findings.items.find((i) => i.status === 'new')!;
    const row = (await screen.findByRole('button', { name: target.title })).closest('tr')!;
    expect(row).toHaveTextContent('Nowe');
    act(() => fake.fire('finding.updated', { id: target.id, status: 'confirmed' }));
    await waitFor(() => expect(row).toHaveTextContent('Potwierdzone'));
    expect(listCalls).toBe(1);
  });

  it('Pokaż on a high-risk toast opens the detail panel', async () => {
    renderBoth();
    await screen.findByRole('button', { name: findings.items[0].title });
    act(() =>
      fake.fire('finding.high_risk', { id: detail.id, module: detail.module, score: detail.score, title: detail.title, url: detail.url, platform: 'web' }),
    );
    const toast = screen.getByRole('group', { name: `Wysokie ryzyko: ${detail.title}` });
    fireEvent.click(within(toast).getByRole('button', { name: 'Pokaż' }));
    expect(await screen.findByRole('heading', { level: 2, name: detail.title })).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: `Wysokie ryzyko: ${detail.title}` })).toBeNull();
  });

  it('the app mounts the alerts in its header: a high-risk event shows a toast there', async () => {
    render(<App />, { wrapper: storeWrapper() });
    await screen.findByRole('button', { name: findings.items[0].title });
    act(() =>
      fake.fire('finding.high_risk', { id: detail.id, module: 'M1', score: 0.91, title: 'Alert z nagłówka', url: detail.url, platform: 'web' }),
    );
    expect(screen.getByRole('group', { name: 'Wysokie ryzyko: Alert z nagłówka' })).toBeInTheDocument();
  });
});
