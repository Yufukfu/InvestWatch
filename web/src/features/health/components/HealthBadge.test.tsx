import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { HealthState } from '../model';
import { HealthBadge } from './HealthBadge';

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

  it('shows the raw value for a status outside the contract instead of an empty badge', () => {
    render(<HealthBadge state={'maintenance' as HealthState} />);
    expect(screen.getByRole('status')).toHaveTextContent('maintenance');
  });
});
