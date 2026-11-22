import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SummaryCards } from './SummaryCards';

const SUMMARY = {
  total: 72,
  highRisk: 10,
  newCount: 31,
  byModule: [
    { module: 'M1', count: 40 },
    { module: 'M2', count: 22 },
    { module: 'M3', count: 10 },
  ],
};

describe('SummaryCards (hero)', () => {
  it('shows the total and the high-risk count as figures with their labels, without a store', () => {
    render(<SummaryCards summary={SUMMARY} asOf="22.11.2026" onStartTriage={vi.fn()} />);
    const region = screen.getByRole('region', { name: 'Podsumowanie' });
    expect(region).toHaveTextContent('PRZEGLĄD · 22.11.2026');
    expect(within(region).getByText('72', { selector: '.hero-value' }).parentElement).toHaveTextContent(
      '72 zgłoszeń, z czego 10 wysokiego ryzyka',
    );
  });

  it('puts ", z czego" in its own element, so the phone layout can stack the two figures without it', () => {
    render(<SummaryCards summary={SUMMARY} asOf="22.11.2026" onStartTriage={vi.fn()} />);
    const sep = screen.getByText(', z czego');
    expect(sep).toHaveClass('hero-sep');
    expect(sep.parentElement).toHaveTextContent('zgłoszeń, z czego');
  });

  it('lists the new findings and every module with its name, the count first', () => {
    render(<SummaryCards summary={SUMMARY} asOf="22.11.2026" onStartTriage={vi.fn()} />);
    const list = screen.getByRole('list', { name: 'Wskaźniki' });
    const items = within(list).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual([
      '31Nowe, bez decyzji',
      '40M1 · Finfluencerzy',
      '22M2 · Zgodność reklam',
      '10M3 · Usługi bez zezwolenia',
    ]);
  });

  it('offers triage as a button named without any count, and reports the click', () => {
    const onStartTriage = vi.fn();
    render(<SummaryCards summary={SUMMARY} asOf="22.11.2026" onStartTriage={onStartTriage} />);
    const button = screen.getByRole('button', { name: 'Rozpocznij triage' });
    fireEvent.click(button);
    expect(onStartTriage).toHaveBeenCalledTimes(1);
  });

  it('offers no triage when there are no high-risk findings', () => {
    render(<SummaryCards summary={{ ...SUMMARY, highRisk: 0 }} asOf="22.11.2026" onStartTriage={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /triage/i })).toBeNull();
  });

  it('renders nothing without data', () => {
    const { container } = render(<SummaryCards summary={undefined} asOf="22.11.2026" onStartTriage={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
