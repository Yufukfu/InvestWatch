import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { M2Coverage } from './M2Coverage';

function fill(container: HTMLElement): HTMLElement | null {
  return container.querySelector('.coverage-bar > span');
}

describe('M2Coverage', () => {
  it('states both counts and the percentage as text, and fills the bar to the same share', () => {
    const { container } = render(<M2Coverage coverage={{ total: 4, registryMatched: 3 }} />);
    const region = screen.getByRole('region', { name: /Pokrycie rejestrem KNF/ });
    expect(region).toHaveTextContent('3 z 4 zgłoszeń M2 dopasowano do rejestru KNF (75%)');
    expect(container.querySelector('.coverage-bar')).toHaveAttribute('aria-hidden', 'true');
    expect(fill(container)).toHaveStyle({ width: '75%' });
  });

  it('rounds the percentage and uses the singular genitive for one finding', () => {
    const { container, rerender } = render(<M2Coverage coverage={{ total: 3, registryMatched: 2 }} />);
    expect(screen.getByRole('region')).toHaveTextContent('2 z 3 zgłoszeń M2 dopasowano do rejestru KNF (67%)');
    expect(fill(container)).toHaveStyle({ width: '67%' });
    rerender(<M2Coverage coverage={{ total: 1, registryMatched: 1 }} />);
    expect(screen.getByRole('region')).toHaveTextContent('1 z 1 zgłoszenia M2 dopasowano do rejestru KNF (100%)');
    expect(fill(container)).toHaveStyle({ width: '100%' });
  });

  it('never draws past the ends for counts out of range', () => {
    const { container, rerender } = render(<M2Coverage coverage={{ total: 2, registryMatched: 5 }} />);
    expect(fill(container)).toHaveStyle({ width: '100%' });
    rerender(<M2Coverage coverage={{ total: 2, registryMatched: -1 }} />);
    expect(fill(container)).toHaveStyle({ width: '0%' });
  });

  it('says brak danych and draws no fill when the server has no coverage', () => {
    const { container } = render(<M2Coverage coverage={undefined} />);
    expect(screen.getByRole('region', { name: /Pokrycie rejestrem KNF/ })).toHaveTextContent('brak danych');
    expect(fill(container)).toBeNull();
  });

  it('says there are no M2 findings and draws no fill when total is 0', () => {
    const { container } = render(<M2Coverage coverage={{ total: 0, registryMatched: 0 }} />);
    expect(screen.getByRole('region')).toHaveTextContent('Brak zgłoszeń M2.');
    expect(screen.getByRole('region')).not.toHaveTextContent('%');
    expect(fill(container)).toBeNull();
  });
});
