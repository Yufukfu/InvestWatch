import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AlertItem } from '../model';
import { AlertToasts } from './AlertToasts';

const alert = (over: Partial<AlertItem> = {}): AlertItem => ({ id: 'a', title: 'Płatne sygnały', module: 'M3', score: 0.93, ...over });

const handlers = () => ({ onOpen: vi.fn(), onDismiss: vi.fn(), onHold: vi.fn(), onRelease: vi.fn() });

describe('AlertToasts', () => {
  it('reads the announcement from the hook in a polite live line that is always present', () => {
    const { container, rerender } = render(<AlertToasts alerts={[]} announcement="" {...handlers()} />);
    const region = screen.getByRole('region', { name: 'Alerty' });
    expect(within(region).queryAllByRole('group')).toHaveLength(0);
    const live = container.querySelector('[aria-live="polite"]')!;
    expect(live).toHaveTextContent(/^$/);
    rerender(<AlertToasts alerts={[alert({ title: 'Nowy' })]} announcement="Wysokie ryzyko: Nowy" {...handlers()} />);
    expect(container.querySelector('[aria-live="polite"]')).toBe(live);
    expect(live).toHaveTextContent(/^Wysokie ryzyko: Nowy$/);
    expect(region.querySelectorAll('[aria-live]')).toHaveLength(1);
  });

  it('keeps the announcement when a toast is dismissed or opened', () => {
    const { container, rerender } = render(
      <AlertToasts alerts={[alert({ title: 'Nowy' }), alert({ id: 'b', title: 'Stary' })]} announcement="Wysokie ryzyko: Nowy" {...handlers()} />,
    );
    rerender(<AlertToasts alerts={[alert({ id: 'b', title: 'Stary' })]} announcement="Wysokie ryzyko: Nowy" {...handlers()} />);
    expect(container.querySelector('[aria-live="polite"]')).toHaveTextContent(/^Wysokie ryzyko: Nowy$/);
  });

  it('holds a toast on hover or focus and releases it only when neither is left', () => {
    const h = handlers();
    render(<AlertToasts alerts={[alert({ id: 'x' })]} announcement="" {...h} />);
    const toast = screen.getByRole('group');
    fireEvent.mouseEnter(toast);
    expect(h.onHold).toHaveBeenLastCalledWith('x');
    fireEvent.mouseLeave(toast);
    expect(h.onRelease).toHaveBeenLastCalledWith('x');
    const show = screen.getByRole('button', { name: 'Pokaż' });
    const close = screen.getByRole('button', { name: 'Zamknij: Płatne sygnały' });
    fireEvent.focus(show);
    expect(h.onHold).toHaveBeenCalledTimes(2);
    fireEvent.blur(show, { relatedTarget: close });
    expect(h.onRelease).toHaveBeenCalledTimes(1);
    fireEvent.blur(close, { relatedTarget: document.body });
    expect(h.onRelease).toHaveBeenCalledTimes(2);
  });

  it('keeps the toast held while keyboard focus is inside it after the pointer leaves', () => {
    const h = handlers();
    render(<AlertToasts alerts={[alert({ id: 'x' })]} announcement="" {...h} />);
    const toast = screen.getByRole('group');
    const show = screen.getByRole('button', { name: 'Pokaż' });
    fireEvent.focus(show);
    fireEvent.mouseEnter(toast);
    fireEvent.mouseLeave(toast);
    expect(h.onRelease).not.toHaveBeenCalled();
    fireEvent.blur(show, { relatedTarget: document.body });
    expect(h.onRelease).toHaveBeenCalledTimes(1);
  });

  it('releases the holds it still has when it unmounts, so a moved toast is not held forever', () => {
    const h = handlers();
    const { unmount } = render(<AlertToasts alerts={[alert({ id: 'x' })]} announcement="" {...h} />);
    fireEvent.mouseEnter(screen.getByRole('group'));
    expect(h.onRelease).not.toHaveBeenCalled();
    unmount();
    expect(h.onRelease).toHaveBeenCalledWith('x');
  });

  it('forgets the hover of a toast that went away, so it holds again when it comes back', () => {
    const h = handlers();
    const { rerender } = render(<AlertToasts alerts={[alert({ id: 'x' })]} announcement="" {...h} />);
    fireEvent.mouseEnter(screen.getByRole('group'));
    fireEvent.click(screen.getByRole('button', { name: 'Zamknij: Płatne sygnały' }));
    expect(h.onDismiss).toHaveBeenCalledWith('x');
    rerender(<AlertToasts alerts={[]} announcement="" {...h} />);
    rerender(<AlertToasts alerts={[alert({ id: 'x' })]} announcement="" {...h} />);
    fireEvent.mouseEnter(screen.getByRole('group'));
    expect(h.onHold).toHaveBeenCalledTimes(2);
  });

  it('shows label, title, module and score, in the given order, with a decimal comma', () => {
    render(<AlertToasts alerts={[alert(), alert({ id: 'b', title: 'Drugi', module: undefined, score: undefined })]} announcement="" {...handlers()} />);
    const toasts = screen.getAllByRole('group');
    expect(toasts).toHaveLength(2);
    expect(toasts[0]).toHaveTextContent('Wysokie ryzyko');
    expect(toasts[0]).toHaveTextContent('Płatne sygnały');
    expect(toasts[0]).toHaveTextContent('M3 · wynik 0,93');
    expect(toasts[1]).toHaveTextContent('Drugi');
    expect(toasts[1]).not.toHaveTextContent('wynik');
    expect(toasts[1].querySelector('.toast-meta')).toBeNull();
  });

  it('shows the score without a module and the module without a score', () => {
    render(<AlertToasts alerts={[alert({ module: undefined, score: 0.5 }), alert({ id: 'b', score: undefined })]} announcement="" {...handlers()} />);
    const [first, second] = screen.getAllByRole('group');
    expect(first.querySelector('.toast-meta')).toHaveTextContent(/^wynik 0,50$/);
    expect(second.querySelector('.toast-meta')).toHaveTextContent(/^M3$/);
  });

  it('opens and dismisses the toast that was clicked, by id, when several are shown', () => {
    const h = handlers();
    render(<AlertToasts alerts={[alert({ id: 'a', title: 'Pierwszy' }), alert({ id: 'b', title: 'Drugi' })]} announcement="" {...h} />);
    const [first, second] = screen.getAllByRole('group');
    fireEvent.click(within(second).getByRole('button', { name: 'Pokaż' }));
    expect(h.onOpen).toHaveBeenLastCalledWith('b');
    fireEvent.click(within(first).getByRole('button', { name: 'Zamknij: Pierwszy' }));
    expect(h.onDismiss).toHaveBeenLastCalledWith('a');
  });

  it('gives each close button its own accessible name', () => {
    render(<AlertToasts alerts={[alert({ id: 'a', title: 'Pierwszy' }), alert({ id: 'b', title: 'Drugi' })]} announcement="" {...handlers()} />);
    expect(screen.getByRole('button', { name: 'Zamknij: Pierwszy' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Zamknij: Drugi' })).toBeInTheDocument();
  });

  it('moves focus to the next toast when one is dismissed, not to the body', () => {
    render(<AlertToasts alerts={[alert({ id: 'a', title: 'Pierwszy' }), alert({ id: 'b', title: 'Drugi' })]} announcement="" {...handlers()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Zamknij: Pierwszy' }));
    const rest = screen.getByRole('group', { name: 'Wysokie ryzyko: Drugi' });
    expect(rest.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(within(rest).getByRole('button', { name: 'Pokaż' }));
  });

  it('moves focus to the next toast when one is opened, so the detail has a place to return to', () => {
    render(<AlertToasts alerts={[alert({ id: 'a', title: 'Pierwszy' }), alert({ id: 'b', title: 'Drugi' })]} announcement="" {...handlers()} />);
    fireEvent.click(screen.getAllByRole('button', { name: 'Pokaż' })[0]);
    expect(screen.getByRole('group', { name: 'Wysokie ryzyko: Drugi' }).contains(document.activeElement)).toBe(true);
  });

  it('moves focus to the toast region when the last toast goes', () => {
    render(<AlertToasts alerts={[alert({ id: 'a' })]} announcement="" {...handlers()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Zamknij: Płatne sygnały' }));
    expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Alerty' }));
  });

  it('renders the title as text and takes no focus on arrival', () => {
    const before = document.activeElement;
    const { container } = render(<AlertToasts alerts={[alert({ title: '<img src=x onerror=alert(1)>' })]} announcement="" {...handlers()} />);
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
    expect(document.activeElement).toBe(before);
  });
});
