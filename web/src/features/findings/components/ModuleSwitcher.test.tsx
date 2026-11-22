import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ModuleOption } from '../model';
import { ModuleSwitcher } from './ModuleSwitcher';

const m1: ModuleOption = { id: 'a', module: 'M1', riskLevel: 'high' };
const m3: ModuleOption = { id: 'b', module: 'M3', riskLevel: 'medium' };

describe('ModuleSwitcher', () => {
  it('lists each module with its risk as text and marks the open one', () => {
    render(<ModuleSwitcher options={[m1, m3]} currentId="a" onSelect={() => {}} />);
    const nav = screen.getByRole('navigation', { name: 'Moduły tego materiału' });
    expect(nav).toBeInTheDocument();
    const current = screen.getByRole('button', { name: /M1/ });
    expect(current).toHaveTextContent('M1');
    expect(current).toHaveTextContent('Wysoki');
    expect(current).toHaveAttribute('aria-current', 'true');
    const other = screen.getByRole('button', { name: /M3/ });
    expect(other).toHaveTextContent('Średni');
    expect(other).not.toHaveAttribute('aria-current');
  });

  it('shows "Brak danych" for a module without a risk level', () => {
    render(<ModuleSwitcher options={[m1, { ...m3, riskLevel: undefined }]} currentId="a" onSelect={() => {}} />);
    expect(screen.getByRole('button', { name: /M3/ })).toHaveTextContent('Brak danych');
  });

  it('selects another module, and does nothing for the open one', () => {
    const onSelect = vi.fn();
    render(<ModuleSwitcher options={[m1, m3]} currentId="a" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: /M1/ }));
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /M3/ }));
    expect(onSelect).toHaveBeenCalledWith('b');
  });

  it('renders nothing for a single module', () => {
    const { container } = render(<ModuleSwitcher options={[m1]} currentId="a" onSelect={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('moves focus to the open module when asked', async () => {
    render(<ModuleSwitcher options={[m1, m3]} currentId="b" onSelect={() => {}} autoFocus />);
    await waitFor(() => expect(screen.getByRole('button', { name: /M3/ })).toHaveFocus());
  });

  it('moves focus once the siblings arrive after mounting', async () => {
    const { rerender } = render(<ModuleSwitcher options={[m3]} currentId="b" onSelect={() => {}} autoFocus />);
    await act(() => new Promise((r) => setTimeout(r, 10)));
    rerender(<ModuleSwitcher options={[m1, m3]} currentId="b" onSelect={() => {}} autoFocus />);
    await waitFor(() => expect(screen.getByRole('button', { name: /M3/ })).toHaveFocus());
  });

  it('moves focus only once, not again when the siblings reload', async () => {
    const { rerender } = render(<ModuleSwitcher options={[m1, m3]} currentId="b" onSelect={() => {}} autoFocus />);
    await waitFor(() => expect(screen.getByRole('button', { name: /M3/ })).toHaveFocus());
    (document.activeElement as HTMLElement).blur();
    rerender(<ModuleSwitcher options={[m3]} currentId="b" onSelect={() => {}} autoFocus />);
    await act(() => new Promise((r) => setTimeout(r, 10)));
    rerender(<ModuleSwitcher options={[m1, m3]} currentId="b" onSelect={() => {}} autoFocus />);
    await act(() => new Promise((r) => setTimeout(r, 10)));
    expect(document.body).toHaveFocus();
  });

  it('leaves focus alone by default', async () => {
    render(<ModuleSwitcher options={[m1, m3]} currentId="b" onSelect={() => {}} />);
    await new Promise((r) => setTimeout(r, 10));
    expect(document.body).toHaveFocus();
  });
});
