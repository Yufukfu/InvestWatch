import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FindingFilters } from '../model';
import { FindingsFilters } from './FindingsFilters';

const base: FindingFilters = { status: [], sort: '-detected_at', page: 1, pageSize: 25 };

function setup(filters: Partial<FindingFilters> = {}) {
  const onChange = vi.fn();
  const onReset = vi.fn();
  const view = render(<FindingsFilters filters={{ ...base, ...filters }} onChange={onChange} onReset={onReset} />);
  return { onChange, onReset, ...view };
}

describe('FindingsFilters', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('has a labelled control for every filter', () => {
    setup();
    for (const label of ['Szukaj', 'Moduł', 'Poziom ryzyka', 'Platforma', 'Minimalny wynik', 'Od dnia', 'Do dnia']) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    expect(screen.getByRole('group', { name: 'Status' })).toBeInTheDocument();
  });

  it('shows the current values', () => {
    setup({ module: 'M2', riskLevel: 'high', status: ['new'], scoreMin: 0.7, dateFrom: '2026-11-20' });
    expect(screen.getByLabelText('Moduł')).toHaveValue('M2');
    expect(screen.getByLabelText('Poziom ryzyka')).toHaveValue('high');
    expect(screen.getByLabelText('Minimalny wynik')).toHaveValue('0.7');
    expect(screen.getByLabelText('Od dnia')).toHaveValue('2026-11-20');
    expect(screen.getByRole('checkbox', { name: 'Nowe' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Zamknięte' })).not.toBeChecked();
  });

  it('reports a select change, and an empty choice clears the filter', () => {
    const { onChange } = setup({ module: 'M1' });
    fireEvent.change(screen.getByLabelText('Poziom ryzyka'), { target: { value: 'low' } });
    expect(onChange).toHaveBeenLastCalledWith({ riskLevel: 'low' });
    fireEvent.change(screen.getByLabelText('Moduł'), { target: { value: '' } });
    expect(onChange).toHaveBeenLastCalledWith({ module: undefined });
    fireEvent.change(screen.getByLabelText('Minimalny wynik'), { target: { value: '0.5' } });
    expect(onChange).toHaveBeenLastCalledWith({ scoreMin: 0.5 });
  });

  it('toggles statuses as a multi-select', () => {
    const { onChange } = setup({ status: ['new'] });
    fireEvent.click(screen.getByRole('checkbox', { name: 'W analizie' }));
    expect(onChange).toHaveBeenLastCalledWith({ status: ['new', 'in_review'] });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Nowe' }));
    expect(onChange).toHaveBeenLastCalledWith({ status: [] });
  });

  it('sends the search once typing pauses', () => {
    const { onChange } = setup();
    const box = screen.getByLabelText('Szukaj');
    fireEvent.change(box, { target: { value: 'in' } });
    fireEvent.change(box, { target: { value: 'inwestor' } });
    act(() => vi.advanceTimersByTime(299));
    expect(onChange).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ q: 'inwestor' });
  });

  it('does not resend a search that equals the current one', () => {
    const { onChange } = setup({ q: 'jan' });
    act(() => vi.advanceTimersByTime(1000));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('follows an external reset of the search', () => {
    const { rerender } = setup({ q: 'jan' });
    expect(screen.getByLabelText('Szukaj')).toHaveValue('jan');
    rerender(<FindingsFilters filters={base} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByLabelText('Szukaj')).toHaveValue('');
  });

  it('offers to clear only when a filter is active, with the active count', () => {
    setup();
    expect(screen.queryByRole('button', { name: /Wyczyść filtry/ })).toBeNull();
    screen.getByLabelText('Moduł'); // rendered
  });

  it('clears all filters', () => {
    const { onReset } = setup({ module: 'M1', status: ['new', 'closed'] });
    const btn = screen.getByRole('button', { name: 'Wyczyść filtry (3)' });
    fireEvent.click(btn);
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
