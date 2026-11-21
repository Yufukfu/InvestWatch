import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { storeWrapper } from '../../test/store';
import { AlertsPage } from './AlertsPage';

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

describe('AlertsPage', () => {
  it('shows the connection state and a toast for a high-risk event', () => {
    render(<AlertsPage />, { wrapper: storeWrapper() });
    expect(screen.getByText('Łączenie…')).toBeInTheDocument();
    act(() => fake.fire('connect'));
    expect(screen.getByText('Na żywo')).toBeInTheDocument();
    act(() =>
      fake.fire('finding.high_risk', {
        id: '94f686c6-70c3-5ec9-9b6f-c97032c380c6',
        module: 'M2',
        score: 0.86,
        title: 'Obietnica 18% zysku',
        url: 'https://x.example',
        platform: 'web',
      }),
    );
    expect(screen.getByText('Obietnica 18% zysku')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Pokaż' }));
    expect(window.location.search).toBe('?finding=94f686c6-70c3-5ec9-9b6f-c97032c380c6');
    expect(screen.queryByText('Obietnica 18% zysku')).toBeNull();
  });
});
