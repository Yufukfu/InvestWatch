import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AlertItem } from '../model';
import { AlertToasts } from './AlertToasts';

const alert = (over: Partial<AlertItem> = {}): AlertItem => ({ id: 'a', title: 'Płatne sygnały', module: 'M3', score: 0.93, ...over });

describe('AlertToasts', () => {
  it('announces only the newest label and title in a polite live line that is always present', () => {
    const { container, rerender } = render(<AlertToasts alerts={[]} onOpen={vi.fn()} onDismiss={vi.fn()} />);
    const region = screen.getByRole('region', { name: 'Alerty' });
    expect(within(region).queryAllByRole('group')).toHaveLength(0);
    const live = container.querySelector('[aria-live="polite"]')!;
    expect(live).toHaveTextContent(/^$/);
    rerender(<AlertToasts alerts={[alert({ title: 'Nowy' }), alert({ id: 'b', title: 'Stary' })]} onOpen={vi.fn()} onDismiss={vi.fn()} />);
    expect(container.querySelector('[aria-live="polite"]')).toBe(live);
    expect(live).toHaveTextContent(/^Wysokie ryzyko: Nowy$/);
    expect(region.querySelectorAll('[aria-live]')).toHaveLength(1);
  });

  it('holds a toast on hover or focus and releases it when both leave', () => {
    const onHold = vi.fn();
    const onRelease = vi.fn();
    render(<AlertToasts alerts={[alert({ id: 'x' })]} onOpen={vi.fn()} onDismiss={vi.fn()} onHold={onHold} onRelease={onRelease} />);
    const toast = screen.getByRole('group');
    fireEvent.mouseEnter(toast);
    expect(onHold).toHaveBeenLastCalledWith('x');
    fireEvent.mouseLeave(toast);
    expect(onRelease).toHaveBeenLastCalledWith('x');
    const show = screen.getByRole('button', { name: 'Pokaż' });
    const close = screen.getByRole('button', { name: 'Zamknij alert' });
    fireEvent.focus(show);
    expect(onHold).toHaveBeenCalledTimes(2);
    fireEvent.blur(show, { relatedTarget: close });
    expect(onRelease).toHaveBeenCalledTimes(1);
    fireEvent.blur(close, { relatedTarget: document.body });
    expect(onRelease).toHaveBeenCalledTimes(2);
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
