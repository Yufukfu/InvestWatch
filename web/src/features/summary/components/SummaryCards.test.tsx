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
    render(<SummaryCards summary={SUMMARY} onStartTriage={vi.fn()} />);
    const region = screen.getByRole('region', { name: 'Podsumowanie' });
    expect(within(region).getByText('72').parentElement).toHaveTextContent('72 zgłoszeń');
    expect(within(region).getByText('10', { selector: '.hero-value' }).parentElement).toHaveTextContent(
      '10 wysokiego ryzyka',
    );
    expect(region).toHaveTextContent('31 nowych');
  });

  it('lists the count of every module by its text label', () => {
    render(<SummaryCards summary={SUMMARY} onStartTriage={vi.fn()} />);
    const list = screen.getByRole('list', { name: 'Zgłoszenia według modułów' });
    const items = within(list).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual(['M1 40', 'M2 22', 'M3 10']);
  });

  it('offers triage as a button named without any count, and reports the click', () => {
    const onStartTriage = vi.fn();
    render(<SummaryCards summary={SUMMARY} onStartTriage={onStartTriage} />);
    const button = screen.getByRole('button', { name: 'Rozpocznij triage' });
    fireEvent.click(button);
    expect(onStartTriage).toHaveBeenCalledTimes(1);
  });

  it('offers no triage when there are no high-risk findings', () => {
    render(<SummaryCards summary={{ ...SUMMARY, highRisk: 0 }} onStartTriage={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /triage/i })).toBeNull();
  });

  it('renders nothing without data', () => {
    const { container } = render(<SummaryCards summary={undefined} onStartTriage={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
