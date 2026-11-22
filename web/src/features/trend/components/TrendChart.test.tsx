import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
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

const xTicks = () =>
  Array.from(document.querySelectorAll('.recharts-xAxis-tick-labels .recharts-cartesian-axis-tick-value')).map(
    (el) => el.textContent,
  );

const linePaths = () => Array.from(document.querySelectorAll('path.recharts-line-curve'));

describe('TrendChart (props only, no store)', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('draws one series per module with a legend naming them and their totals', () => {
    setup();
    const items = within(screen.getByRole('list', { name: 'Legenda' })).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual(['M1 · Finfluencerzy4', 'M2 · Zgodność reklam3', 'M3 · Usługi bez zezwolenia1']);
  });

  it('says in a subtitle what the chart counts', () => {
    setup();
    expect(screen.getByText('Liczba wykrytych incydentów w czasie, według modułu')).toBeInTheDocument();
    expect(linePaths()).toHaveLength(3);
  });

  it('colours the series from tokens and keeps the risk red away from every module', () => {
    setup();
    const strokes = linePaths().map((el) => el.getAttribute('stroke'));
    expect(strokes).toEqual(['var(--accent)', 'var(--link)', 'var(--m3)']);
    for (const stroke of strokes) {
      expect(stroke).not.toMatch(/risk-high|sev-high|#/);
    }
  });

  it('tells series apart by dash pattern on the lines and the legend swatches, not colour alone', () => {
    setup();
    const swatches = Array.from(document.querySelectorAll('.trend-legend line'));
    for (const els of [linePaths(), swatches]) {
      expect(els.map((el) => el.getAttribute('stroke-dasharray'))).toEqual([null, '6 5', '2 4']);
    }
  });

  it('gives the chart an accessible name with totals per module and nothing focusable inside', () => {
    setup();
    const img = screen.getByRole('img', { name: 'Liczba zgłoszeń: M1 4, M2 3, M3 1' });
    // Recharts' keyboard layer puts tabindex=0 on the surface; the hidden tooltip wrapper has -1.
    expect(img.querySelectorAll('[tabindex]:not([tabindex="-1"]), button, a[href], input')).toHaveLength(0);
  });

  it('offers a table of every bucket as the text alternative', () => {
    setup();
    const table = screen.getByRole('table', { name: 'Trend zgłoszeń: dane' });
    const rows = within(table).getAllByRole('row').map((r) => r.textContent);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toBe('OkresM1M2M3');
    expect(rows[1]).toMatch(/120$/);
    expect(rows[2]).toMatch(/311$/);
  });

  it('treats a missing count as 0 and still renders', () => {
    setup({ points: [{ t: '2026-11-20T17:00:00Z', M1: 2 }, { t: '2026-11-20T18:00:00Z', M2: 1 }] });
    expect(screen.getByRole('img')).toHaveAccessibleName('Liczba zgłoszeń: M1 2, M2 1, M3 0');
    expect(linePaths()).toHaveLength(3);
  });

  it('shows the empty state for no points', () => {
    setup({ points: [] });
    expect(screen.getByText('Brak danych w wybranym okresie.')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('shows the empty state when every count is zero', () => {
    setup({ points: [{ t: '2026-11-20T17:00:00Z', M1: 0, M2: 0, M3: 0 }] });
    expect(screen.getByText('Brak danych w wybranym okresie.')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('shows the loading text as a status instead of a chart', () => {
    setup({ isLoading: true });
    expect(screen.getByRole('status')).toHaveTextContent('Ładowanie wykresu…');
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('shows the error text', () => {
    setup({ isError: true });
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać danych trendu.');
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('marks the active bucket pressed in a labelled group and reports a switch', () => {
    const { onBucketChange } = setup({ bucket: 'hour' });
    const group = screen.getByRole('group', { name: 'Przedział czasu' });
    expect(within(group).getByRole('button', { name: 'Godzina' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(group).getByRole('button', { name: 'Dzień' })).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'Dzień' }));
    expect(onBucketChange).toHaveBeenCalledWith('day');
  });

  it('labels hour buckets in local time, with the date at local midnight', () => {
    vi.stubEnv('TZ', 'Asia/Tokyo');
    // 15:00Z is 00:00 on 21 Nov in Tokyo; 17:00Z is 02:00.
    setup({ points: [{ t: '2026-11-20T15:00:00Z', M1: 1 }, { t: '2026-11-20T17:00:00Z', M1: 2 }] });
    const ticks = xTicks();
    expect(ticks).toEqual(['21 lis', '02:00']);
    expect(screen.queryByText('Dni liczone w czasie UTC.')).toBeNull();
    const rows = within(screen.getByRole('table')).getAllByRole('row');
    expect(rows[1]).toHaveTextContent('21 lis, 00:00');
  });

  it('shows the date and time of an hour bucket in the tooltip', () => {
    vi.stubEnv('TZ', 'Asia/Tokyo');
    setup({ tooltipIndex: 1 });
    expect(document.querySelector('.recharts-tooltip-label')).toHaveTextContent('21 lis, 03:00');
  });

  it.each(['America/Los_Angeles', 'Asia/Tokyo'])('labels a day bucket with its UTC date in %s', (tz) => {
    vi.stubEnv('TZ', tz);
    setup({ bucket: 'day', points: [{ t: '2026-11-20T00:00:00Z', M1: 1 }, { t: '2026-11-21T00:00:00Z', M1: 2 }] });
    const ticks = xTicks();
    expect(ticks).toEqual(['20 lis', '21 lis']);
    expect(screen.getByText('Dni liczone w czasie UTC.')).toBeInTheDocument();
  });
});

describe('TrendChart responsive path (no fixed size)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('draws the chart through ResponsiveContainer once it can measure its parent', async () => {
    class FakeResizeObserver {
      cb: ResizeObserverCallback;
      constructor(cb: ResizeObserverCallback) {
        this.cb = cb;
      }
      observe(target: Element) {
        this.cb([{ target, contentRect: { width: 500, height: 260 } } as ResizeObserverEntry], this as never);
      }
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal('ResizeObserver', FakeResizeObserver);
    setup({ size: undefined });
    expect(await screen.findByRole('img')).toBeInTheDocument();
    await waitFor(() => expect(linePaths()).toHaveLength(3));
  });
});
