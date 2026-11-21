import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { HealthBadge, type HealthState } from './HealthBadge';

describe('HealthBadge', () => {
  it.each<[HealthState, string]>([
    ['loading', 'Sprawdzanie…'],
    ['ok', 'System działa'],
    ['degraded', 'Częściowa awaria'],
    ['down', 'System nie działa'],
    ['unreachable', 'Brak połączenia z API'],
  ])('renders %s as "%s" from props, without a store', (state, label) => {
    render(<HealthBadge state={state} />);
    const badge = screen.getByRole('status');
    expect(badge).toHaveTextContent(label);
    expect(badge).toHaveClass(`badge-${state}`);
  });
});
