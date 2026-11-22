import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { iso } from '../../test/iso';
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

const payload = (id: string, title: string) => ({
  id,
  module: 'M2',
  score: 0.86,
  title,
  url: 'https://x.example',
  platform: 'web',
});

describe('AlertsPage', () => {
  afterEach(() => vi.useRealTimers());

  it('shows the connection state and a toast for a high-risk event', () => {
    render(<AlertsPage />, { wrapper: storeWrapper() });
    expect(screen.getByText('Łączenie…')).toBeInTheDocument();
    act(() => fake.fire('connect'));
    expect(screen.getByText('Na żywo')).toBeInTheDocument();
    act(() => fake.fire('finding.high_risk', payload('94f686c6-70c3-5ec9-9b6f-c97032c380c6', 'Obietnica 18% zysku')));
    expect(screen.getByText('Obietnica 18% zysku')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Pokaż' }));
    expect(window.location.search).toBe('?finding=94f686c6-70c3-5ec9-9b6f-c97032c380c6');
    expect(screen.queryByText('Obietnica 18% zysku')).toBeNull();
  });

  it('a toast under the pointer stays past its time and goes 20 seconds after the pointer leaves', () => {
    vi.useFakeTimers();
    render(<AlertsPage />, { wrapper: storeWrapper() });
    act(() => fake.fire('finding.high_risk', payload('00000000-0000-4000-8000-000000000001', 'Pod kursorem')));
    const toast = screen.getByRole('group', { name: `Wysokie ryzyko: ${iso('Pod kursorem')}` });
    fireEvent.mouseEnter(toast);
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByText('Pod kursorem')).toBeInTheDocument();
    fireEvent.mouseLeave(toast);
    act(() => vi.advanceTimersByTime(19_999));
    expect(screen.getByText('Pod kursorem')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByText('Pod kursorem')).toBeNull();
  });
});
