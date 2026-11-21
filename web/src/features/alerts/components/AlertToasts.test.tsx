import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AlertItem } from '../model';
import { AlertToasts } from './AlertToasts';

const alert = (over: Partial<AlertItem> = {}): AlertItem => ({ id: 'a', title: 'Płatne sygnały', module: 'M3', score: 0.93, ...over });

describe('AlertToasts', () => {
  it('renders a polite live region that exists even when empty', () => {
    render(<AlertToasts alerts={[]} onOpen={vi.fn()} onDismiss={vi.fn()} />);
    const region = screen.getByRole('region', { name: 'Alerty' });
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(within(region).queryAllByRole('group')).toHaveLength(0);
  });

  it('shows label, title, module and score, in the given order', () => {
    render(<AlertToasts alerts={[alert(), alert({ id: 'b', title: 'Drugi', module: undefined, score: undefined })]} onOpen={vi.fn()} onDismiss={vi.fn()} />);
    const toasts = screen.getAllByRole('group');
    expect(toasts).toHaveLength(2);
    expect(toasts[0]).toHaveTextContent('Wysokie ryzyko');
    expect(toasts[0]).toHaveTextContent('Płatne sygnały');
    expect(toasts[0]).toHaveTextContent('M3 · wynik 0.93');
    expect(toasts[1]).toHaveTextContent('Drugi');
    expect(toasts[1]).not.toHaveTextContent('wynik');
    expect(toasts[1].querySelector('.toast-meta')).toBeNull();
  });

  it('shows the score without a module and the module without a score', () => {
    render(<AlertToasts alerts={[alert({ module: undefined, score: 0.5 }), alert({ id: 'b', score: undefined })]} onOpen={vi.fn()} onDismiss={vi.fn()} />);
    const [first, second] = screen.getAllByRole('group');
    expect(first.querySelector('.toast-meta')).toHaveTextContent(/^wynik 0\.50$/);
    expect(second.querySelector('.toast-meta')).toHaveTextContent(/^M3$/);
  });

  it('opens and dismisses by id', () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    render(<AlertToasts alerts={[alert({ id: 'x' })]} onOpen={onOpen} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole('button', { name: 'Pokaż' }));
    expect(onOpen).toHaveBeenCalledWith('x');
    fireEvent.click(screen.getByRole('button', { name: 'Zamknij alert' }));
    expect(onDismiss).toHaveBeenCalledWith('x');
  });

  it('renders the title as text and takes no focus', () => {
    const before = document.activeElement;
    const { container } = render(<AlertToasts alerts={[alert({ title: '<img src=x onerror=alert(1)>' })]} onOpen={vi.fn()} onDismiss={vi.fn()} />);
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
    expect(document.activeElement).toBe(before);
  });
});
