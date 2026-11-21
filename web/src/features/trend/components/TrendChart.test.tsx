import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TrendChart, type TrendChartProps } from './TrendChart';

const points = [
  { t: '2026-11-20T17:00:00Z', M1: 1, M2: 2, M3: 0 },
  { t: '2026-11-20T18:00:00Z', M1: 3, M2: 1, M3: 1 },
];

// jsdom has no ResizeObserver, so tests pass a fixed chart size (ADR 0203).
function setup(props: Partial<TrendChartProps> = {}) {
  const onBucketChange = vi.fn();
  render(
    <TrendChart
      points={points}
      bucket="hour"
      onBucketChange={onBucketChange}
      isLoading={false}
      isError={false}
      size={{ width: 500, height: 240 }}
      {...props}
    />,
  );
  return { onBucketChange };
}

describe('TrendChart (props only, no store)', () => {
  it('draws one series per module with a legend naming them', () => {
    setup();
    const legend = screen.getByRole('list', { name: 'Legenda' });
    expect(legend).toHaveTextContent('M1');
    expect(legend).toHaveTextContent('M2');
    expect(legend).toHaveTextContent('M3');
    expect(document.querySelectorAll('path.recharts-line-curve')).toHaveLength(3);
  });

  it('gives the chart an accessible name with totals per module', () => {
    setup();
    expect(screen.getByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 4, M2 3, M3 1');
  });

  it('treats a missing count as 0 and still renders', () => {
    setup({ points: [{ t: '2026-11-20T17:00:00Z', M1: 2 }, { t: '2026-11-20T18:00:00Z', M2: 1 }] });
    expect(screen.getByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 2, M2 1, M3 0');
    expect(document.querySelectorAll('path.recharts-line-curve')).toHaveLength(3);
  });

  it('shows the empty state for no points and for all-zero counts', () => {
    setup({ points: [] });
    expect(screen.getByText('Brak danych w wybranym okresie.')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('shows the empty state when every count is zero', () => {
    setup({ points: [{ t: '2026-11-20T17:00:00Z', M1: 0, M2: 0, M3: 0 }] });
    expect(screen.getByText('Brak danych w wybranym okresie.')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('shows loading and error texts instead of a chart', () => {
    setup({ isLoading: true });
    expect(screen.getByText('Ładowanie wykresu…')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('shows the error text', () => {
    setup({ isError: true });
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać danych trendu.');
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('marks the active bucket pressed and reports a switch', () => {
    const { onBucketChange } = setup({ bucket: 'hour' });
    expect(screen.getByRole('button', { name: 'Godzina' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Dzień' })).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'Dzień' }));
    expect(onBucketChange).toHaveBeenCalledWith('day');
  });
});
