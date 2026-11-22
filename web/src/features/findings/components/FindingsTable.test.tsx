import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FindingRow, FindingStatus } from '../model';
import { FindingsTable } from './FindingsTable';

const row = (over: Partial<FindingRow> = {}): FindingRow => ({
  id: '1',
  module: 'M2',
  title: 'Obietnica zysku',
  platform: 'instagram',
  score: 0.5,
  riskLevel: 'medium',
  status: 'in_review',
  detectedAt: '2026-11-21T15:00:00Z',
  documentId: 'doc-1',
  url: 'https://example.com/post/1',
  host: 'example.com',
  ...over,
});

const props = {
  total: 2,
  onFirstPage: vi.fn(),
  sort: '-detected_at' as const,
  onSort: vi.fn(),
  onSelect: vi.fn(),
  onReset: vi.fn(),
  selectedId: undefined,
  isLoading: false,
  isFetching: false,
  isError: false,
};

// The year sits in its own element, so match the <time> by its whole text.
const timeText = (text: string) => (_: string, el: Element | null) => el?.tagName === 'TIME' && el.textContent === text;

describe('FindingsTable', () => {
  it('renders one row per finding with Polish status and a two-decimal score, without a store', () => {
    render(<FindingsTable {...props} rows={[row(), row({ id: '2', title: 'Inny', score: 0.123, status: 'false_positive' })]} />);
    expect(screen.getAllByRole('row')).toHaveLength(3);
    expect(screen.getByText('Obietnica zysku')).toBeInTheDocument();
    expect(screen.getByText('0,12')).toBeInTheDocument();
    expect(screen.getByText('Fałszywy alarm')).toBeInTheDocument();
  });

  it.each([
    ['new', 'Nowe'],
    ['in_review', 'W analizie'],
    ['confirmed', 'Potwierdzone'],
    ['false_positive', 'Fałszywy alarm'],
    ['closed', 'Zamknięte'],
  ] as [FindingStatus, string][])('shows status %s as %s', (status, label) => {
    render(<FindingsTable {...props} rows={[row({ status })]} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it.each([
    ['high', 'Wysoki', 'risk-high'],
    ['medium', 'Średni', 'risk-medium'],
    ['low', 'Niski', 'risk-low'],
  ] as const)('shows risk %s as the text %s with its colour class', (riskLevel, text, cls) => {
    render(<FindingsTable {...props} rows={[row({ riskLevel })]} />);
    expect(screen.getByText(text)).toHaveClass('risk', cls);
  });

  it('shows a missing risk level as no data, not as low', () => {
    render(<FindingsTable {...props} rows={[row({ riskLevel: undefined })]} />);
    expect(screen.getByText('Brak danych')).toBeInTheDocument();
    expect(screen.queryByText('Niski')).toBeNull();
  });

  it('shows the detection time in UTC and the module name', () => {
    render(<FindingsTable {...props} rows={[row()]} />);
    expect(screen.getByText(timeText('21.11.2026 · 15:00'))).toBeInTheDocument();
    expect(screen.getByText('M2')).toHaveAttribute('title', 'Zgodność reklam');
  });

  it('renders markup in scraped text literally', () => {
    const { container } = render(<FindingsTable {...props} rows={[row({ title: '<img src=x onerror=alert(1)>' })]} />);
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
  });

  it('keeps the table in a horizontal scroll container', () => {
    render(<FindingsTable {...props} rows={[row()]} />);
    expect(screen.getByRole('table').parentElement).toHaveClass('table-scroll');
  });

  it('opens a finding from its title button and marks the selected row', () => {
    const onSelect = vi.fn();
    render(<FindingsTable {...props} rows={[row(), row({ id: '2', title: 'Drugi' })]} onSelect={onSelect} selectedId="2" />);
    fireEvent.click(screen.getByRole('button', { name: 'Obietnica zysku' }));
    expect(onSelect).toHaveBeenCalledWith('1');
    expect(screen.getByRole('button', { name: 'Drugi' }).closest('tr')).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('button', { name: 'Obietnica zysku' }).closest('tr')).not.toHaveAttribute('aria-current');
  });

  it('sorts by score and by time from the column headers', () => {
    const onSort = vi.fn();
    const { rerender } = render(<FindingsTable {...props} rows={[row()]} onSort={onSort} />);
    expect(screen.getByRole('columnheader', { name: /Wykryto/ })).toHaveAttribute('aria-sort', 'descending');
    fireEvent.click(screen.getByRole('button', { name: /Wykryto/ }));
    expect(onSort).toHaveBeenLastCalledWith('detected_at');
    fireEvent.click(screen.getByRole('button', { name: /Wynik/ }));
    expect(onSort).toHaveBeenLastCalledWith('-score');
    rerender(<FindingsTable {...props} rows={[row()]} onSort={onSort} sort="-score" />);
    expect(screen.getByRole('columnheader', { name: /Wynik/ })).toHaveAttribute('aria-sort', 'descending');
    expect(screen.getByRole('columnheader', { name: /Wykryto/ })).toHaveAttribute('aria-sort', 'none');
    fireEvent.click(screen.getByRole('button', { name: /Wynik/ }));
    expect(onSort).toHaveBeenLastCalledWith('score');
  });

  it('shows the count from total with Polish plural forms', () => {
    const { rerender } = render(<FindingsTable {...props} rows={[row()]} total={1} />);
    expect(screen.getByText('1 zgłoszenie')).toBeInTheDocument();
    rerender(<FindingsTable {...props} rows={[row()]} total={3} />);
    expect(screen.getByText('3 zgłoszenia')).toBeInTheDocument();
    rerender(<FindingsTable {...props} rows={[row()]} total={5} />);
    expect(screen.getByText('5 zgłoszeń')).toBeInTheDocument();
    rerender(<FindingsTable {...props} rows={[row()]} total={12} />);
    expect(screen.getByText('12 zgłoszeń')).toBeInTheDocument();
    rerender(<FindingsTable {...props} rows={[row()]} total={22} />);
    expect(screen.getByText('22 zgłoszenia')).toBeInTheDocument();
  });

  it('shows the empty state with a clear-filters action', () => {
    const onReset = vi.fn();
    render(<FindingsTable {...props} rows={[]} total={0} onReset={onReset} />);
    expect(screen.queryByRole('table')).toBeNull();
    const empty = screen.getByRole('status');
    expect(empty).toHaveTextContent('Brak zgłoszeń dla wybranych filtrów');
    fireEvent.click(within(empty).getByRole('button', { name: 'Wyczyść filtry' }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it('explains the empty state with a hint on what to change', () => {
    render(<FindingsTable {...props} rows={[]} total={0} />);
    expect(within(screen.getByRole('status')).getByText('Zmień zakres dat lub poziom ryzyka.')).toBeInTheDocument();
  });

  it('draws three decorative skeleton rows under the loading text, and marks the region busy', () => {
    render(<FindingsTable {...props} rows={undefined} isLoading />);
    const loading = screen.getByRole('status');
    expect(loading).toHaveAttribute('aria-busy', 'true');
    expect(loading).toHaveTextContent('Ładowanie…');
    const skeleton = loading.querySelector('.skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
    expect(skeleton?.children).toHaveLength(3);
  });

  it('shows loading and error states', () => {
    const { rerender } = render(<FindingsTable {...props} rows={undefined} isLoading />);
    expect(screen.getByText('Ładowanie…')).toBeInTheDocument();
    rerender(<FindingsTable {...props} rows={undefined} isError />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać zgłoszeń.');
  });

  it('shows the loading text while the first rows of a new query load', () => {
    render(<FindingsTable {...props} rows={undefined} isFetching />);
    expect(screen.getByText('Ładowanie…')).toBeInTheDocument();
  });

  it('marks the table busy while it refreshes', () => {
    const { rerender } = render(<FindingsTable {...props} rows={[row()]} isFetching />);
    expect(screen.getByRole('table').parentElement).toHaveAttribute('aria-busy', 'true');
    rerender(<FindingsTable {...props} rows={[row()]} />);
    expect(screen.getByRole('table').parentElement).toHaveAttribute('aria-busy', 'false');
  });

  it('a page past the end is not "no matches": it offers the first page', () => {
    const onFirstPage = vi.fn();
    render(<FindingsTable {...props} rows={[]} total={9} onFirstPage={onFirstPage} />);
    expect(screen.queryByText('Brak zgłoszeń dla wybranych filtrów')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent('Na tej stronie nie ma już zgłoszeń.');
    fireEvent.click(screen.getByRole('button', { name: 'Wróć do pierwszej strony' }));
    expect(onFirstPage).toHaveBeenCalledTimes(1);
  });

  it('shows platform, module and score in their cells', () => {
    render(<FindingsTable {...props} rows={[row({ platform: 'tiktok', module: 'M3', score: 0.456 })]} />);
    const cells = screen.getAllByRole('cell').map((c) => c.textContent);
    expect(cells).toContain('TikTok');
    expect(cells).toContain('M3');
    expect(cells).toContain('0,46');
  });

  it('shows the raw status for a value outside the contract', () => {
    render(<FindingsTable {...props} rows={[row({ status: 'archived' as FindingStatus })]} />);
    expect(screen.getByRole('cell', { name: 'archived' })).toBeInTheDocument();
  });

  it('shows the error alert instead of stale rows when a refetch failed', () => {
    render(<FindingsTable {...props} rows={[row()]} isError />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać zgłoszeń.');
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('keeps the table, not the loading text, while rows refresh', () => {
    render(<FindingsTable {...props} rows={[row()]} isFetching />);
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.queryByText('Ładowanie…')).toBeNull();
  });

  it('tints a high-risk row and still names the risk in text', () => {
    render(
      <FindingsTable
        {...props}
        rows={[row({ id: 'h', title: 'Wysokie', riskLevel: 'high' }), row({ id: 'm', title: 'Średnie', riskLevel: 'medium' })]}
      />,
    );
    const high = screen.getByText('Wysokie').closest('tr')!;
    const medium = screen.getByText('Średnie').closest('tr')!;
    expect(high).toHaveClass('row-high');
    expect(within(high).getByText('Wysoki')).toBeInTheDocument();
    expect(medium).not.toHaveClass('row-high');
  });

  it('renders the score and the detection time in the monospace class', () => {
    render(<FindingsTable {...props} rows={[row({ score: 0.93 })]} />);
    expect(screen.getByText('0,93').closest('.score')).toHaveClass('mono');
    expect(screen.getByText(timeText('21.11.2026 · 15:00')).closest('td')).toHaveClass('mono');
  });

  it('shows the detection time in UTC as day.month.year · hour:minute and says so on hover', () => {
    render(<FindingsTable {...props} rows={[row({ detectedAt: '2026-01-05T08:07:00Z' })]} />);
    const time = screen.getByText(timeText('05.01.2026 · 08:07'));
    expect(time.tagName).toBe('TIME');
    expect(time).toHaveAttribute('datetime', '2026-01-05T08:07:00Z');
    expect(time).toHaveAttribute('title', 'Czas UTC');
  });

  it('reads the time as UTC whatever the browser zone is, and shows an unparsable value as it came', () => {
    render(<FindingsTable {...props} rows={[row({ id: 'late', detectedAt: '2026-01-05T23:30:00Z' }), row({ id: 'bad', detectedAt: 'not-a-time' })]} />);
    expect(screen.getByText(timeText('05.01.2026 · 23:30'))).toBeInTheDocument();
    expect(screen.getByText('not-a-time')).toBeInTheDocument();
  });

  it('splits the year from the day and time, so a phone card can show dd.mm · hh:mm', () => {
    render(<FindingsTable {...props} rows={[row({ detectedAt: '2026-01-05T08:07:00Z' })]} />);
    const time = screen.getByText(timeText('05.01.2026 · 08:07'));
    const year = time.querySelector('.date-year');
    expect(year).toHaveTextContent('.2026');
    expect(time.textContent?.replace(year?.textContent ?? '', '')).toBe('05.01 · 08:07');
  });

  it('keeps platform, status and time as consecutive cells after the title, for the card meta line', () => {
    render(<FindingsTable {...props} rows={[row({ platform: 'instagram', status: 'new' })]} />);
    const cells = Array.from(screen.getAllByRole('row')[1].querySelectorAll('td'));
    expect(cells.map((td) => td.className.split(' ')[0])).toEqual([
      'col-risk', 'col-title', 'col-module', 'col-platform', 'col-score', 'col-status', 'col-date',
    ]);
    expect(cells[3]).toHaveTextContent('Instagram');
    expect(cells[5]).toHaveTextContent('Nowe');
  });

  it('marks each row with its risk level, so the score bar can take the level colour', () => {
    render(
      <FindingsTable
        {...props}
        rows={[
          row({ id: 'm', title: 'Średnie', riskLevel: 'medium' }),
          row({ id: 'l', title: 'Niskie', riskLevel: 'low' }),
        ]}
      />,
    );
    expect(screen.getByText('Średnie').closest('tr')).toHaveClass('row-medium');
    expect(screen.getByText('Niskie').closest('tr')).toHaveClass('row-low');
  });

  it('keeps table roles explicit, so the card layout on a phone is still a table for assistive technology', () => {
    render(<FindingsTable {...props} rows={[row()]} />);
    const table = screen.getByRole('table');
    expect(table).toHaveAttribute('role', 'table');
    for (const tr of Array.from(table.querySelectorAll('tr'))) expect(tr).toHaveAttribute('role', 'row');
    expect(Array.from(table.querySelectorAll('thead th')).map((th) => th.getAttribute('role'))).toEqual(
      Array(7).fill('columnheader'),
    );
    expect(Array.from(table.querySelectorAll('tbody td')).map((td) => td.getAttribute('role'))).toEqual(
      Array(7).fill('cell'),
    );
  });

  it.each([
    [11, '11 zgłoszeń'],
    [14, '14 zgłoszeń'],
    [21, '21 zgłoszeń'],
    [24, '24 zgłoszenia'],
    [112, '112 zgłoszeń'],
    [102, '102 zgłoszenia'],
  ])('uses the Polish plural for %i', (n, text) => {
    render(<FindingsTable {...props} rows={[row()]} total={n} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('shows the source host under the title as text', () => {
    render(<FindingsTable {...props} rows={[row({ host: 'example.com' })]} />);
    const title = screen.getByRole('button', { name: 'Obietnica zysku' }).closest('td') as HTMLElement;
    expect(within(title).getByText('example.com')).toBeInTheDocument();
    expect(within(title).queryByRole('link')).toBeNull();
  });

  it('shows no host when the URL is not http(s)', () => {
    render(<FindingsTable {...props} rows={[row({ host: undefined })]} />);
    const title = screen.getByRole('button', { name: 'Obietnica zysku' }).closest('td') as HTMLElement;
    expect(title.textContent).toBe('Obietnica zysku');
  });

  it('keeps M1 and M3 of one document as two rows with their own status', () => {
    render(
      <FindingsTable
        {...props}
        rows={[
          row({ id: 'a', module: 'M1', status: 'new' }),
          row({ id: 'b', module: 'M3', status: 'confirmed' }),
        ]}
      />,
    );
    expect(screen.getAllByRole('row')).toHaveLength(3);
    expect(screen.getByText('Nowe')).toBeInTheDocument();
    expect(screen.getByText('Potwierdzone')).toBeInTheDocument();
  });
});
