import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SummaryCards } from './SummaryCards';

describe('SummaryCards', () => {
  it('renders three labelled counts from props, without a store', () => {
    render(<SummaryCards summary={{ total: 9, highRisk: 6, newCount: 3 }} />);
    const region = screen.getByRole('region', { name: 'Podsumowanie' });
    expect(region).toHaveTextContent('9Wszystkie zgłoszenia');
    expect(region).toHaveTextContent('6Wysokie ryzyko');
    expect(region).toHaveTextContent('3Nowe');
  });

  it('renders nothing without data', () => {
    const { container } = render(<SummaryCards summary={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
