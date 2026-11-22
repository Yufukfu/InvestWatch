import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
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
    render(<SummaryCards summary={SUMMARY} />);
    const region = screen.getByRole('region', { name: 'Podsumowanie' });
    expect(within(region).getByText('72').parentElement).toHaveTextContent('72 zgłoszeń');
    expect(within(region).getByText('10', { selector: '.hero-value' }).parentElement).toHaveTextContent(
      '10 wysokiego ryzyka',
    );
    expect(region).toHaveTextContent('31 nowych');
  });

  it('lists the count of every module by its text label', () => {
    render(<SummaryCards summary={SUMMARY} />);
    const list = screen.getByRole('list', { name: 'Zgłoszenia według modułów' });
    const items = within(list).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual(['M1 40', 'M2 22', 'M3 10']);
  });

  it('renders nothing without data', () => {
    const { container } = render(<SummaryCards summary={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
